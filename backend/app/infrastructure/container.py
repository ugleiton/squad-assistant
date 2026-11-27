"""Composition: builds use cases wired to their infrastructure adapters.

Use them as async context managers so the HTTP clients are closed:

    async with container.review_tracker(session, assistant_id) as tracker:
        await tracker.scan()
"""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from sqlmodel import Session

from ..application.daily.reminder import DailyReminder
from ..application.ports import ChatProvider
from ..application.review.tracker import ReviewTracker
from ..domain.entities import DailyAssistant, ReviewAssistant
from ..domain.enums import DeliveryMode
from .chat import provider_for_connection, webhook_provider
from .gitlab.client import GitLabClient
from .i18n import t
from .persistence import models as m
from .persistence.mappers import daily_assistant, review_assistant
from .persistence.repositories import SqlDailyRepository, SqlReviewRepository
from .security import decrypt


@asynccontextmanager
async def review_tracker(
    session: Session, assistant: ReviewAssistant | int
) -> AsyncIterator[ReviewTracker]:
    if isinstance(assistant, int):
        assistant = review_assistant(session.get(m.ReviewAssistant, assistant))
    conn = session.get(m.ChatConnection, assistant.chat_connection_id)
    gl = session.get(m.GitLabConnection, assistant.gitlab_connection_id)
    if conn is None or gl is None:
        raise LookupError("review assistant is missing its chat or GitLab connection")
    chat = provider_for_connection(conn)
    gitlab = GitLabClient(gl.base_url, decrypt(gl.access_token))
    try:
        yield ReviewTracker(assistant, SqlReviewRepository(session), chat, gitlab, t)
    finally:
        await chat.aclose()
        await gitlab.aclose()


def _daily_chat(session: Session, row: m.DailyAssistant) -> ChatProvider:
    conn = session.get(m.ChatConnection, row.chat_connection_id) if row.chat_connection_id else None
    if row.delivery == DeliveryMode.webhook:
        platform = row.webhook_platform or (conn.provider if conn else None)
        provider = platform.value if platform else "slack"
        return webhook_provider(decrypt(row.webhook_url) or "", provider)
    if conn is None or not row.channel_id:
        raise LookupError("daily assistant with bot delivery needs a chat connection and channel")
    return provider_for_connection(conn)


@asynccontextmanager
async def daily_reminder(
    session: Session, assistant: DailyAssistant | int
) -> AsyncIterator[DailyReminder]:
    aid = assistant if isinstance(assistant, int) else assistant.id
    row = session.get(m.DailyAssistant, aid)
    chat = _daily_chat(session, row)
    try:
        yield DailyReminder(daily_assistant(row), SqlDailyRepository(session), chat, t)
    finally:
        await chat.aclose()
