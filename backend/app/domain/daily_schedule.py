from datetime import datetime, timedelta

from .entities import DailySchedule


def due_daily(
    schedules: list[DailySchedule],
    lead_minutes: int,
    now_local: datetime,
    window_minutes: int = 15,
) -> datetime | None:
    """Return the local start of the daily whose reminder is due at `now_local`, if any.

    A reminder is due from (start - lead) until start, capped by `window_minutes` so a restarted
    server does not send very late reminders."""
    for day_offset in (0, 1):  # a reminder may fall on the previous day near midnight
        day = (now_local + timedelta(days=day_offset)).date()
        for sch in schedules:
            if sch.weekday != day.weekday():
                continue
            start = datetime.combine(day, sch.time, tzinfo=now_local.tzinfo)
            alert_at = start - timedelta(minutes=lead_minutes)
            if alert_at <= now_local < min(start, alert_at + timedelta(minutes=window_minutes)):
                return start
    return None
