"""Database models. Works on SQLite and PostgreSQL (JSON columns are portable)."""

from datetime import UTC, date, datetime
from datetime import time as dtime
from enum import Enum

from sqlalchemy import JSON, Column, UniqueConstraint
from sqlmodel import Field, SQLModel


def utcnow() -> datetime:
    return datetime.now(UTC)


class ChatProviderType(str, Enum):
    slack = "slack"
    mattermost = "mattermost"


class ChatConnection(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    name: str
    provider: ChatProviderType
    base_url: str | None = None  # Mattermost server URL; ignored for Slack
    bot_token: str | None = None  # stored encrypted
    bot_user_id: str | None = None


class GitLabConnection(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    name: str
    base_url: str = "https://gitlab.com"
    access_token: str | None = None  # stored encrypted


class Squad(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    name: str


class Member(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    name: str
    chat_user_id: str | None = None  # Slack user id (U123...) or Mattermost user id
    chat_username: str | None = None  # Mattermost username (used for @mentions)
    gitlab_username: str | None = None


class SquadMember(SQLModel, table=True):
    squad_id: int = Field(foreign_key="squad.id", primary_key=True)
    member_id: int = Field(foreign_key="member.id", primary_key=True)


class ReviewState(str, Enum):
    awaiting_review = "awaiting_review"
    in_review = "in_review"
    resolved = "resolved"
    merged = "merged"
    closed = "closed"


DEFAULT_REVIEW_EMOJIS = {
    ReviewState.awaiting_review.value: "hourglass_flowing_sand",
    ReviewState.in_review.value: "mag",
    ReviewState.resolved.value: "white_check_mark",
    ReviewState.merged.value: "rocket",
    ReviewState.closed.value: "heavy_check_mark",  # gray check
}

DEFAULT_REVIEW_FEATURES = {
    "mark_status": True,
    "mention_squad": True,
    "pipeline_messages": True,
    "merge_messages": True,
    "mark_resolved": True,
}


class ReviewAssistant(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    name: str
    enabled: bool = True
    language: str = "en"
    chat_connection_id: int = Field(foreign_key="chatconnection.id")
    channel_id: str
    gitlab_connection_id: int = Field(foreign_key="gitlabconnection.id")
    # GitLab project paths or numeric ids, e.g. ["group/app", "1234"]
    gitlab_projects: list[str] = Field(default_factory=list, sa_column=Column(JSON))
    squad_ids: list[int] = Field(default_factory=list, sa_column=Column(JSON))
    webhook_token_hash: str | None = None
    scan_interval_minutes: int = 5
    scan_lookback_hours: int = 72
    emojis: dict = Field(
        default_factory=lambda: dict(DEFAULT_REVIEW_EMOJIS), sa_column=Column(JSON)
    )
    features: dict = Field(
        default_factory=lambda: dict(DEFAULT_REVIEW_FEATURES), sa_column=Column(JSON)
    )
    last_scan_at: datetime | None = None


class ReviewThread(SQLModel, table=True):
    __table_args__ = (UniqueConstraint("review_assistant_id", "chat_thread_id"),)

    id: int | None = Field(default=None, primary_key=True)
    review_assistant_id: int = Field(foreign_key="reviewassistant.id", index=True)
    chat_thread_id: str
    chat_author_id: str | None = None
    gitlab_project: str = Field(index=True)
    mr_iid: int = Field(index=True)
    mr_url: str
    state: ReviewState = ReviewState.awaiting_review
    squad_notified: bool = False
    marked_emoji: str | None = None  # emoji currently applied by the bot
    last_pipeline_status: str | None = None
    created_at: datetime = Field(default_factory=utcnow)
    updated_at: datetime = Field(default_factory=utcnow)


class ReviewEvent(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    review_thread_id: int = Field(foreign_key="reviewthread.id", index=True)
    type: str
    payload: dict = Field(default_factory=dict, sa_column=Column(JSON))
    created_at: datetime = Field(default_factory=utcnow)


class DeliveryMode(str, Enum):
    bot = "bot"
    webhook = "webhook"


class RotationMode(str, Enum):
    none = "none"
    daily = "daily"
    weekly = "weekly"


class DailyAssistant(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    name: str
    enabled: bool = True
    language: str = "en"
    timezone: str = "UTC"
    squad_id: int | None = Field(default=None, foreign_key="squad.id")
    delivery: DeliveryMode = DeliveryMode.bot
    chat_connection_id: int | None = Field(default=None, foreign_key="chatconnection.id")
    channel_id: str | None = None
    # Incoming webhook URL (Slack or Mattermost), stored encrypted
    webhook_url: str | None = None
    lead_time_minutes: int = 10
    rotation_mode: RotationMode = RotationMode.daily
    meeting_url: str | None = None
    # Optional custom template; placeholders: {minutes} {time} {facilitator} {meeting_url}
    message_template: str | None = None


class DailySchedule(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    daily_assistant_id: int = Field(foreign_key="dailyassistant.id", index=True)
    weekday: int  # 0 = Monday ... 6 = Sunday
    time: dtime


class DailyParticipant(SQLModel, table=True):
    daily_assistant_id: int = Field(foreign_key="dailyassistant.id", primary_key=True)
    member_id: int = Field(foreign_key="member.id", primary_key=True)
    order: int = 0
    active: bool = True


class DailyRotationState(SQLModel, table=True):
    daily_assistant_id: int = Field(foreign_key="dailyassistant.id", primary_key=True)
    current_member_id: int | None = Field(default=None, foreign_key="member.id")
    period_key: str | None = None  # "2026-11-27" (daily) or "2026-W48" (weekly)


class DailyRun(SQLModel, table=True):
    __table_args__ = (UniqueConstraint("daily_assistant_id", "scheduled_for"),)

    id: int | None = Field(default=None, primary_key=True)
    daily_assistant_id: int = Field(foreign_key="dailyassistant.id", index=True)
    scheduled_for: datetime  # start of the daily, in UTC
    facilitator_id: int | None = Field(default=None, foreign_key="member.id")
    sent_at: datetime = Field(default_factory=utcnow)


__all__ = [
    "ChatConnection",
    "ChatProviderType",
    "GitLabConnection",
    "Squad",
    "Member",
    "SquadMember",
    "ReviewAssistant",
    "ReviewThread",
    "ReviewEvent",
    "ReviewState",
    "DailyAssistant",
    "DailySchedule",
    "DailyParticipant",
    "DailyRotationState",
    "DailyRun",
    "DeliveryMode",
    "RotationMode",
    "date",
]
