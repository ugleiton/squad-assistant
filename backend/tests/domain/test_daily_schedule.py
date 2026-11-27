from datetime import datetime, time
from zoneinfo import ZoneInfo

from app.domain.daily_schedule import due_daily
from app.domain.entities import DailySchedule

SP = ZoneInfo("America/Sao_Paulo")
FRIDAY_0930 = [DailySchedule(weekday=4, time=time(9, 30))]


def test_due_inside_lead_window():
    now = datetime(2026, 11, 27, 9, 21, tzinfo=SP)
    assert due_daily(FRIDAY_0930, 10, now) == datetime(2026, 11, 27, 9, 30, tzinfo=SP)


def test_not_due_before_lead_time_or_after_start():
    assert due_daily(FRIDAY_0930, 10, datetime(2026, 11, 27, 9, 10, tzinfo=SP)) is None
    assert due_daily(FRIDAY_0930, 10, datetime(2026, 11, 27, 9, 30, tzinfo=SP)) is None


def test_other_weekday_not_due():
    assert due_daily(FRIDAY_0930, 10, datetime(2026, 11, 26, 9, 21, tzinfo=SP)) is None


def test_reminder_on_previous_day_near_midnight():
    sched = [DailySchedule(weekday=5, time=time(0, 5))]  # Saturday 00:05
    now = datetime(2026, 11, 27, 23, 58, tzinfo=SP)
    assert due_daily(sched, 10, now) == datetime(2026, 11, 28, 0, 5, tzinfo=SP)
