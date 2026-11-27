import os

os.environ.setdefault("SQUAD_DATABASE_URL", "sqlite://")
os.environ.setdefault("SQUAD_SCHEDULER_ENABLED", "false")

import pytest  # noqa: E402
from sqlalchemy.pool import StaticPool  # noqa: E402
from sqlmodel import Session, SQLModel, create_engine  # noqa: E402

from app import models  # noqa: E402,F401
from app.chat.base import ChatMessage, ChatProvider  # noqa: E402


@pytest.fixture
def engine():
    eng = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    SQLModel.metadata.create_all(eng)
    return eng


@pytest.fixture
def session(engine):
    with Session(engine) as s:
        yield s


class FakeChat(ChatProvider):
    def __init__(self, messages=None, replies=None):
        self.messages = messages or []
        self.replies = replies or {}
        self.posts: list[tuple] = []
        self.reactions: list[tuple] = []

    async def list_messages(self, channel_id, since):
        return self.messages

    async def list_replies(self, channel_id, thread_id):
        return self.replies.get(thread_id, [])

    async def add_reaction(self, channel_id, message_id, emoji):
        self.reactions.append(("+", message_id, emoji))

    async def remove_reaction(self, channel_id, message_id, emoji):
        self.reactions.append(("-", message_id, emoji))

    async def post_message(self, channel_id, text, thread_id=None):
        self.posts.append((channel_id, text, thread_id))
        return "x"

    def mention(self, user_id, username=None):
        return f"<@{user_id}>"


@pytest.fixture
def fake_chat():
    return FakeChat


__all__ = ["ChatMessage"]
