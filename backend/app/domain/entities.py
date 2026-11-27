"""Domain entities: plain dataclasses with no framework or database dependencies."""

from dataclasses import dataclass, field
from datetime import UTC, datetime, time

from .enums import (
    DEFAULT_REVIEW_EMOJIS,
    DEFAULT_REVIEW_FEATURES,
    DeliveryMode,
    ReviewState,
    RotationMode,
)


def utcnow() -> datetime:
    return datetime.now(UTC)


@dataclass
class Member:
    id: int | None
    name: str
    chat_user_id: str | None = None
    chat_username: str | None = None
    gitlab_username: str | None = None


@dataclass
class ChatMessage:
    id: str  # Slack ts / Mattermost post id
    user_id: str | None
    text: str
    created_at: datetime
    reply_count: int = 0


@dataclass
class MergeRequestStatus:
    state: str  # opened | merged | closed | locked
    approved: bool
    user_notes_count: int
    unresolved_discussions: int
    web_url: str
    resolvable_discussions: int = 0
    author_username: str | None = None


@dataclass
class ReviewAssistant:
    id: int | None
    name: str
    chat_connection_id: int
    channel_id: str
    gitlab_connection_id: int
    enabled: bool = True
    language: str = "en"
    gitlab_projects: list[str] = field(default_factory=list)
    squad_ids: list[int] = field(default_factory=list)
    webhook_token_hash: str | None = None
    scan_interval_minutes: int = 5
    scan_lookback_hours: int = 72
    emojis: dict[str, str] = field(default_factory=lambda: dict(DEFAULT_REVIEW_EMOJIS))
    features: dict[str, bool] = field(default_factory=lambda: dict(DEFAULT_REVIEW_FEATURES))
    last_scan_at: datetime | None = None

    def feature(self, name: str) -> bool:
        return bool(self.features.get(name, DEFAULT_REVIEW_FEATURES.get(name, True)))

    def emoji_for(self, state: ReviewState) -> str | None:
        return self.emojis.get(state.value) or None

    def is_scan_due(self, now: datetime) -> bool:
        if not self.enabled:
            return False
        if self.last_scan_at is None:
            return True
        last = self.last_scan_at
        if last.tzinfo is None:
            last = last.replace(tzinfo=UTC)
        return (now - last).total_seconds() >= self.scan_interval_minutes * 60


@dataclass
class ReviewThread:
    id: int | None
    review_assistant_id: int
    chat_thread_id: str
    gitlab_project: str
    mr_iid: int
    mr_url: str
    chat_author_id: str | None = None
    state: ReviewState = ReviewState.awaiting_review
    squad_notified: bool = False
    marked_emoji: str | None = None
    last_pipeline_status: str | None = None
    created_at: datetime = field(default_factory=utcnow)
    updated_at: datetime = field(default_factory=utcnow)

    @property
    def is_open(self) -> bool:
        return self.state not in (ReviewState.merged, ReviewState.closed)


@dataclass
class DailySchedule:
    weekday: int  # 0 = Monday ... 6 = Sunday
    time: time


@dataclass
class DailyAssistant:
    id: int | None
    name: str
    enabled: bool = True
    language: str = "en"
    timezone: str = "UTC"
    delivery: DeliveryMode = DeliveryMode.bot
    chat_connection_id: int | None = None
    channel_id: str | None = None
    lead_time_minutes: int = 10
    rotation_mode: RotationMode = RotationMode.daily
    meeting_url: str | None = None
    message_template: str | None = None


@dataclass
class RotationState:
    current_member_id: int | None = None
    period_key: str | None = None
