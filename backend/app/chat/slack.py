from datetime import UTC, datetime

import httpx

from .base import ChatMessage, ChatProvider

SLACK_API = "https://slack.com/api/"


class SlackError(RuntimeError):
    pass


class SlackProvider(ChatProvider):
    def __init__(self, bot_token: str, client: httpx.AsyncClient | None = None):
        self._client = client or httpx.AsyncClient(
            base_url=SLACK_API, headers={"Authorization": f"Bearer {bot_token}"}, timeout=20
        )

    async def _call(self, method: str, **params) -> dict:
        if method.startswith(("conversations.history", "conversations.replies")):
            resp = await self._client.get(method, params=params)
        else:
            resp = await self._client.post(method, json=params)
        resp.raise_for_status()
        data = resp.json()
        if not data.get("ok"):
            error = data.get("error")
            if error in {"already_reacted", "no_reaction"}:
                return data
            raise SlackError(f"{method}: {error}")
        return data

    @staticmethod
    def _to_msg(m: dict) -> ChatMessage:
        return ChatMessage(
            id=m["ts"],
            user_id=m.get("user") or m.get("bot_id"),
            text=m.get("text", ""),
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
            messages += [self._to_msg(m) for m in data.get("messages", []) if not m.get("subtype")]
            cursor = (data.get("response_metadata") or {}).get("next_cursor")
            if not cursor:
                return messages

    async def list_replies(self, channel_id: str, thread_id: str) -> list[ChatMessage]:
        data = await self._call(
            "conversations.replies", channel=channel_id, ts=thread_id, limit=200
        )
        return [self._to_msg(m) for m in data.get("messages", []) if m.get("ts") != thread_id]

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
