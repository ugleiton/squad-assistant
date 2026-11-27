"""In-process scheduler. One job runs every minute and fans out to the assistants that are due,
so there is no extra worker or broker to deploy."""

import logging
from datetime import UTC, datetime, timedelta

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from sqlmodel import Session, select

from .daily.service import DailyService
from .db import engine
from .models import DailyAssistant, ReviewAssistant

log = logging.getLogger(__name__)


async def run_review_scans(now: datetime | None = None) -> None:
    now = now or datetime.now(UTC)
    with Session(engine) as s:
        for a in s.exec(select(ReviewAssistant).where(ReviewAssistant.enabled)).all():
            last = a.last_scan_at
            if last and last.tzinfo is None:
                last = last.replace(tzinfo=UTC)
            if last and now - last < timedelta(minutes=a.scan_interval_minutes):
                continue
            from .review.service import ReviewService

            try:
                await ReviewService(s, a).scan(now)
            except Exception:
                log.exception("review scan failed for assistant %s", a.id)


async def run_daily_ticks(now: datetime | None = None) -> None:
    with Session(engine) as s:
        for a in s.exec(select(DailyAssistant).where(DailyAssistant.enabled)).all():
            try:
                await DailyService(s, a).tick(now)
            except Exception:
                log.exception("daily reminder failed for assistant %s", a.id)


def build_scheduler() -> AsyncIOScheduler:
    sched = AsyncIOScheduler(timezone="UTC")
    sched.add_job(
        run_review_scans, "interval", minutes=1, id="review_scans", max_instances=1, coalesce=True
    )
    sched.add_job(
        run_daily_ticks, "cron", second=5, id="daily_ticks", max_instances=1, coalesce=True
    )
    return sched
