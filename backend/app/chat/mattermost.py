from datetime import UTC, datetime

import httpx

from .base import ChatMessage, ChatProvider


class MattermostProvider(ChatProvider):
    def __init__(
        self,
        base_url: str,
        bot_token: str,
        bot_user_id: str | None = None,
        client: httpx.AsyncClient | None = None,
    ):
        self._client = client or httpx.AsyncClient(
            base_url=base_url.rstrip("/") + "/api/v4/",
            headers={"Authorization": f"Bearer {bot_token}"},
            timeout=20,
        )
        self._bot_user_id = bot_user_id

    async def _bot_id(self) -> str:
        if not self._bot_user_id:
            resp = await self._client.get("users/me")
            resp.raise_for_status()
            self._bot_user_id = resp.json()["id"]
        return self._bot_user_id

    @staticmethod
    def _to_msg(p: dict) -> ChatMessage:
        return ChatMessage(
            id=p["id"],
            user_id=p.get("user_id"),
            text=p.get("message", ""),
            created_at=datetime.fromtimestamp(p["create_at"] / 1000, tz=UTC),
            reply_count=p.get("reply_count", 0),
        )

    async def list_messages(self, channel_id: str, since: datetime) -> list[ChatMessage]:
        resp = await self._client.get(
            f"channels/{channel_id}/posts", params={"since": int(since.timestamp() * 1000)}
        )
        resp.raise_for_status()
        posts = resp.json().get("posts", {}).values()
        return [
            self._to_msg(p)
            for p in posts
            if not p.get("root_id") and not p.get("type") and p.get("delete_at", 0) == 0
        ]

    async def list_replies(self, channel_id: str, thread_id: str) -> list[ChatMessage]:
        resp = await self._client.get(f"posts/{thread_id}/thread")
        resp.raise_for_status()
        posts = resp.json().get("posts", {}).values()
        return [self._to_msg(p) for p in posts if p["id"] != thread_id]

    async def add_reaction(self, channel_id: str, message_id: str, emoji: str) -> None:
        resp = await self._client.post(
            "reactions",
            json={"user_id": await self._bot_id(), "post_id": message_id, "emoji_name": emoji},
        )
        resp.raise_for_status()

    async def remove_reaction(self, channel_id: str, message_id: str, emoji: str) -> None:
        resp = await self._client.delete(
            f"users/{await self._bot_id()}/posts/{message_id}/reactions/{emoji}"
        )
        if resp.status_code not in (200, 404):
            resp.raise_for_status()

    async def post_message(self, channel_id, text, thread_id=None):
        payload = {"channel_id": channel_id, "message": text}
        if thread_id:
            payload["root_id"] = thread_id
        resp = await self._client.post("posts", json=payload)
        resp.raise_for_status()
        return resp.json().get("id")

    def mention(self, user_id, username=None) -> str:
        return f"@{username}" if username else f"@{user_id}"

    async def aclose(self) -> None:
        await self._client.aclose()
