from datetime import time

from pydantic import BaseModel, Field

from ...domain.enums import ChatProviderType, DeliveryMode, RotationMode


class ChatConnectionIn(BaseModel):
    name: str
    provider: ChatProviderType
    base_url: str | None = None
    bot_token: str | None = Field(default=None, description="Write-only")
    bot_user_id: str | None = None


class ChatConnectionOut(BaseModel):
    id: int
    name: str
    provider: ChatProviderType
    base_url: str | None
    bot_user_id: str | None
    has_token: bool


class GitLabConnectionIn(BaseModel):
    name: str
    base_url: str = "https://gitlab.com"
    access_token: str | None = Field(default=None, description="Write-only")


class GitLabConnectionOut(BaseModel):
    id: int
    name: str
    base_url: str
    has_token: bool


class MemberIn(BaseModel):
    name: str
    chat_user_id: str | None = None
    chat_username: str | None = None
    gitlab_username: str | None = None


class SquadIn(BaseModel):
    name: str
    member_ids: list[int] = []


class SquadOut(BaseModel):
    id: int
    name: str
    member_ids: list[int]


class ReviewAssistantIn(BaseModel):
    name: str
    enabled: bool = True
    language: str = "en"
    chat_connection_id: int
    channel_id: str
    gitlab_connection_id: int
    gitlab_projects: list[str] = []
    squad_ids: list[int] = []
    scan_interval_minutes: int = Field(default=5, ge=1)
    scan_lookback_hours: int = Field(default=72, ge=1)
    emojis: dict[str, str] | None = None
    features: dict[str, bool] | None = None


class ReviewAssistantOut(ReviewAssistantIn):
    id: int
    webhook_url: str
    emojis: dict[str, str]
    features: dict[str, bool]


class WebhookCredentials(BaseModel):
    webhook_url: str
    webhook_token: str = Field(description="Shown only once. Paste it in GitLab as Secret token.")


class ScheduleIn(BaseModel):
    weekday: int = Field(ge=0, le=6, description="0 = Monday")
    time: time


class ParticipantIn(BaseModel):
    member_id: int
    order: int = 0
    active: bool = True


class DailyAssistantIn(BaseModel):
    name: str
    enabled: bool = True
    language: str = "en"
    timezone: str = "UTC"
    squad_id: int | None = None
    delivery: DeliveryMode = DeliveryMode.bot
    chat_connection_id: int | None = None
    channel_id: str | None = None
    webhook_url: str | None = Field(default=None, description="Write-only")
    lead_time_minutes: int = Field(default=10, ge=0)
    rotation_mode: RotationMode = RotationMode.daily
    meeting_url: str | None = None
    message_template: str | None = None
    schedules: list[ScheduleIn] = []
    participants: list[ParticipantIn] = []


class DailyAssistantOut(DailyAssistantIn):
    id: int
    has_webhook_url: bool
    current_facilitator_id: int | None = None
