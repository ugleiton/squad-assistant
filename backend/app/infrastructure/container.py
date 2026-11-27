"""Composition: builds use cases wired to their infrastructure adapters."""

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


def review_tracker(session: Session, assistant: ReviewAssistant | int) -> ReviewTracker:
    if isinstance(assistant, int):
        assistant = review_assistant(session.get(m.ReviewAssistant, assistant))
    conn = session.get(m.ChatConnection, assistant.chat_connection_id)
    gl = session.get(m.GitLabConnection, assistant.gitlab_connection_id)
    return ReviewTracker(
        assistant,
        SqlReviewRepository(session),
        provider_for_connection(conn),
        GitLabClient(gl.base_url, decrypt(gl.access_token)),
        t,
    )


def _daily_chat(session: Session, row: m.DailyAssistant) -> ChatProvider:
    conn = session.get(m.ChatConnection, row.chat_connection_id) if row.chat_connection_id else None
    if row.delivery == DeliveryMode.webhook:
        provider = conn.provider.value if conn else "slack"
        return webhook_provider(decrypt(row.webhook_url) or "", provider)
    return provider_for_connection(conn)


def daily_reminder(session: Session, assistant: DailyAssistant | int) -> DailyReminder:
    aid = assistant if isinstance(assistant, int) else assistant.id
    row = session.get(m.DailyAssistant, aid)
    return DailyReminder(
        daily_assistant(row), SqlDailyRepository(session), _daily_chat(session, row), t
    )
