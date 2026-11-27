from datetime import datetime

import httpx

from .base import ChatMessage, ChatProvider


class IncomingWebhookProvider(ChatProvider):
    """Posts through a Slack/Mattermost incoming webhook. Only `post_message` is supported,
    so it fits daily reminders but not review tracking."""

    supports_threads = False

    def __init__(self, url: str, provider: str = "slack", client: httpx.AsyncClient | None = None):
        self._url = url
        self._provider = provider
        self._client = client or httpx.AsyncClient(timeout=20)

    async def post_message(self, channel_id, text, thread_id=None):
        resp = await self._client.post(self._url, json={"text": text})
        resp.raise_for_status()
        return None

    def mention(self, user_id, username=None) -> str:
        if self._provider == "slack" and user_id:
            return f"<@{user_id}>"
        return f"@{username or user_id}"

    async def list_messages(self, channel_id: str, since: datetime) -> list[ChatMessage]:
        raise NotImplementedError("incoming webhooks cannot read messages")

    async def list_replies(self, channel_id: str, thread_id: str) -> list[ChatMessage]:
        raise NotImplementedError("incoming webhooks cannot read messages")

    async def add_reaction(self, channel_id, message_id, emoji):
        raise NotImplementedError("incoming webhooks cannot add reactions")

    async def remove_reaction(self, channel_id, message_id, emoji):
        raise NotImplementedError("incoming webhooks cannot remove reactions")

    async def aclose(self) -> None:
        await self._client.aclose()
