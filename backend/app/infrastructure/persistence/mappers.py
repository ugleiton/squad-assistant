"""Row <-> domain entity mapping."""

from ...domain import entities as d
from . import models as m


def member(row: m.Member) -> d.Member:
    return d.Member(
        id=row.id,
        name=row.name,
        chat_user_id=row.chat_user_id,
        chat_username=row.chat_username,
        gitlab_username=row.gitlab_username,
    )


def review_assistant(row: m.ReviewAssistant) -> d.ReviewAssistant:
    return d.ReviewAssistant(**row.model_dump())


def review_thread(row: m.ReviewThread) -> d.ReviewThread:
    return d.ReviewThread(**row.model_dump())


def daily_assistant(row: m.DailyAssistant) -> d.DailyAssistant:
    return d.DailyAssistant(**row.model_dump(exclude={"webhook_url", "squad_id"}))
