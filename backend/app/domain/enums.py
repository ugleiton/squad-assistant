from enum import Enum


class ChatProviderType(str, Enum):
    slack = "slack"
    mattermost = "mattermost"


class ReviewState(str, Enum):
    awaiting_review = "awaiting_review"
    in_review = "in_review"
    resolved = "resolved"
    merged = "merged"
    closed = "closed"


class DeliveryMode(str, Enum):
    bot = "bot"
    webhook = "webhook"


class RotationMode(str, Enum):
    none = "none"
    daily = "daily"
    weekly = "weekly"


DEFAULT_REVIEW_EMOJIS: dict[str, str] = {
    ReviewState.awaiting_review.value: "hourglass_flowing_sand",
    ReviewState.in_review.value: "mag",
    ReviewState.resolved.value: "white_check_mark",
    ReviewState.merged.value: "rocket",
    ReviewState.closed.value: "heavy_check_mark",  # gray check
}

DEFAULT_REVIEW_FEATURES: dict[str, bool] = {
    "mark_status": True,
    "mention_squad": True,
    "pipeline_messages": True,
    "merge_messages": True,
    "mark_resolved": True,
}
