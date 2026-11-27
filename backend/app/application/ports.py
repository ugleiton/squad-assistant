"""Ports: interfaces the application layer depends on. Infrastructure provides the adapters."""

from abc import ABC, abstractmethod
from datetime import datetime
from typing import Protocol

from ..domain.entities import (
    ChatMessage,
    DailyAssistant,
    DailySchedule,
    Member,
    MergeRequestStatus,
    ReviewAssistant,
    ReviewThread,
    RotationState,
)


class ChatProvider(ABC):
    """Common interface for Slack and Mattermost. Emoji names are given without colons."""

    supports_threads: bool = True
    bot_user_id: str | None = None

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

    async def get_bot_user_id(self) -> str | None:
        """User id the bot posts as, so its own replies can be ignored."""
        return self.bot_user_id

    async def aclose(self) -> None:  # pragma: no cover
        return None


class GitLabGateway(Protocol):
    async def merge_request_status(self, project: str, iid: int) -> MergeRequestStatus: ...


class Translator(Protocol):
    def __call__(self, lang: str | None, key: str, **params: object) -> str: ...


class ReviewRepository(Protocol):
    def get_assistant(self, assistant_id: int) -> ReviewAssistant | None: ...

    def list_enabled_assistants(self) -> list[ReviewAssistant]: ...

    def mark_scanned(self, assistant_id: int, at: datetime) -> None: ...

    def find_thread(self, assistant_id: int, chat_thread_id: str) -> ReviewThread | None: ...

    def open_threads(self, assistant_id: int) -> list[ReviewThread]: ...

    def threads_for_mr(self, assistant_id: int, iid: int) -> list[ReviewThread]: ...

    def save_thread(self, thread: ReviewThread) -> ReviewThread: ...

    def add_event(self, thread_id: int, type: str, payload: dict) -> None: ...

    def squad_members(self, squad_ids: list[int]) -> list[tuple[int, Member]]:
        """(squad_id, member) pairs for the given squads."""
        ...


class DailyRepository(Protocol):
    def list_enabled_assistants(self) -> list[DailyAssistant]: ...

    def schedules(self, assistant_id: int) -> list[DailySchedule]: ...

    def participants(self, assistant_id: int) -> list[Member]:
        """Active participants, in rotation order."""
        ...

    def rotation_state(self, assistant_id: int) -> RotationState: ...

    def save_rotation_state(self, assistant_id: int, state: RotationState) -> None: ...

    def run_exists(self, assistant_id: int, scheduled_for: datetime) -> bool: ...

    def add_run(
        self, assistant_id: int, scheduled_for: datetime, facilitator_id: int | None
    ) -> None: ...
