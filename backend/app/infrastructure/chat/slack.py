import asyncio
from datetime import UTC, datetime

import httpx

from ...application.ports import ChatProvider
from ...domain.entities import ChatMessage

SLACK_API = "https://slack.com/api/"
READ_METHODS = {"conversations.history", "conversations.replies", "auth.test"}
# Messages that can carry an MR link: regular user messages and bot/integration posts.
ACCEPTED_SUBTYPES = {None, "bot_message"}


class SlackError(RuntimeError):
    pass


class SlackProvider(ChatProvider):
    def __init__(
        self,
        bot_token: str,
        bot_user_id: str | None = None,
        client: httpx.AsyncClient | None = None,
    ):
        self._client = client or httpx.AsyncClient(
            base_url=SLACK_API, headers={"Authorization": f"Bearer {bot_token}"}, timeout=20
        )
        self.bot_user_id = bot_user_id

    async def _send(self, method: str, params: dict) -> httpx.Response:
        if method in READ_METHODS:
            return await self._client.get(method, params=params)
        return await self._client.post(method, json=params)

    async def _call(self, method: str, **params) -> dict:
        resp = await self._send(method, params)
        if resp.status_code == 429:  # rate limited: wait once as Slack asks
            await asyncio.sleep(min(float(resp.headers.get("Retry-After", "1")), 30))
            resp = await self._send(method, params)
        resp.raise_for_status()
        data = resp.json()
        if not data.get("ok"):
            error = data.get("error")
            if error in {"already_reacted", "no_reaction"}:
                return data
            raise SlackError(f"{method}: {error}")
        return data

    @staticmethod
    def _text(m: dict) -> str:
        """Message text plus attachment text, where integrations often put the MR link."""
        parts = [m.get("text") or ""]
        for att in m.get("attachments") or []:
            parts += [att.get(k) or "" for k in ("title_link", "pretext", "text", "fallback")]
        return "\n".join(p for p in parts if p)

    @classmethod
    def _to_msg(cls, m: dict) -> ChatMessage:
        return ChatMessage(
            id=m["ts"],
            user_id=m.get("user") or m.get("bot_id"),
            text=cls._text(m),
            created_at=datetime.fromtimestamp(float(m["ts"]), tz=UTC),
            reply_count=m.get("reply_count", 0),
        )

    async def list_messages(self, channel_id: str, since: datetime) -> list[ChatMessage]:
        messages: list[ChatMessage] = []
        cursor = None
        while True:
            params = {"channel": channel_id, "oldest": f"{since.timestamp():.6f}", "limit": 200}
            if cursor:
                params["cursor"] = cursor
            data = await self._call("conversations.history", **params)
            messages += [
                self._to_msg(m)
                for m in data.get("messages", [])
                if m.get("subtype") in ACCEPTED_SUBTYPES
            ]
            cursor = (data.get("response_metadata") or {}).get("next_cursor")
            if not cursor:
                return messages

    async def list_replies(self, channel_id: str, thread_id: str) -> list[ChatMessage]:
        replies: list[ChatMessage] = []
        cursor = None
        while True:
            params = {"channel": channel_id, "ts": thread_id, "limit": 200}
            if cursor:
                params["cursor"] = cursor
            data = await self._call("conversations.replies", **params)
            replies += [
                self._to_msg(m) for m in data.get("messages", []) if m.get("ts") != thread_id
            ]
            cursor = (data.get("response_metadata") or {}).get("next_cursor")
            if not cursor:
                return replies

    async def get_bot_user_id(self) -> str | None:
        if not self.bot_user_id:
            self.bot_user_id = (await self._call("auth.test")).get("user_id")
        return self.bot_user_id

    async def add_reaction(self, channel_id: str, message_id: str, emoji: str) -> None:
        await self._call("reactions.add", channel=channel_id, timestamp=message_id, name=emoji)

    async def remove_reaction(self, channel_id: str, message_id: str, emoji: str) -> None:
        await self._call("reactions.remove", channel=channel_id, timestamp=message_id, name=emoji)

    async def post_message(self, channel_id, text, thread_id=None):
        payload = {"channel": channel_id, "text": text}
        if thread_id:
            payload["thread_ts"] = thread_id
        data = await self._call("chat.postMessage", **payload)
        return data.get("ts")

    def mention(self, user_id, username=None) -> str:
        return f"<@{user_id}>" if user_id else f"@{username}"

    async def aclose(self) -> None:
        await self._client.aclose()
