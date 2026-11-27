from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime


@dataclass
class ChatMessage:
    id: str  # Slack ts / Mattermost post id
    user_id: str | None
    text: str
    created_at: datetime
    reply_count: int = 0


class ChatProvider(ABC):
    """Common interface for Slack and Mattermost. Emoji names are given without colons."""

    supports_threads: bool = True

    @abstractmethod
    async def list_messages(self, channel_id: str, since: datetime) -> list[ChatMessage]:
        """Top-level messages in a channel created after `since` (UTC)."""

    @abstractmethod
    async def list_replies(self, channel_id: str, thread_id: str) -> list[ChatMessage]:
        """Replies of a thread, without the root message."""

    @abstractmethod
    async def add_reaction(self, channel_id: str, message_id: str, emoji: str) -> None: ...

    @abstractmethod
    async def remove_reaction(self, channel_id: str, message_id: str, emoji: str) -> None: ...

    @abstractmethod
    async def post_message(
        self, channel_id: str | None, text: str, thread_id: str | None = None
    ) -> str | None: ...

    @abstractmethod
    def mention(self, user_id: str | None, username: str | None = None) -> str: ...

    async def aclose(self) -> None:  # pragma: no cover
        return None
