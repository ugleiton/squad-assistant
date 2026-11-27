from datetime import date

from app.daily.rotation import next_facilitator
from app.models import RotationMode

P = [10, 20, 30]


def test_daily_rotation_advances_each_day():
    fid, key = next_facilitator(P, RotationMode.daily, None, None, date(2026, 11, 23))
    assert fid == 10
    fid, key = next_facilitator(P, RotationMode.daily, fid, key, date(2026, 11, 23))
    assert fid == 10  # same day, same facilitator
    fid, key = next_facilitator(P, RotationMode.daily, fid, key, date(2026, 11, 24))
    assert fid == 20


def test_weekly_rotation_keeps_person_all_week():
    fid, key = next_facilitator(P, RotationMode.weekly, 30, None, date(2026, 11, 23))
    assert (fid, key) == (10, "2026-W48")
    assert next_facilitator(P, RotationMode.weekly, fid, key, date(2026, 11, 27))[0] == 10
    assert next_facilitator(P, RotationMode.weekly, fid, key, date(2026, 11, 30))[0] == 20


def test_no_rotation():
    assert next_facilitator(P, RotationMode.none, None, None, date(2026, 11, 23)) == (None, None)
