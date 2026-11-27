from datetime import UTC, datetime, timedelta

from app.domain.entities import ReviewAssistant


def _assistant(**kw):
    return ReviewAssistant(
        id=1, name="R", chat_connection_id=1, channel_id="C", gitlab_connection_id=1, **kw
    )


def test_scan_due_respects_interval():
    now = datetime(2026, 11, 27, 12, 0, tzinfo=UTC)
    assert _assistant().is_scan_due(now)
    a = _assistant(scan_interval_minutes=5, last_scan_at=now - timedelta(minutes=4))
    assert not a.is_scan_due(now)
    a.last_scan_at = now - timedelta(minutes=5)
    assert a.is_scan_due(now)
    assert not _assistant(enabled=False).is_scan_due(now)


def test_naive_last_scan_is_treated_as_utc():
    now = datetime(2026, 11, 27, 12, 0, tzinfo=UTC)
    a = _assistant(last_scan_at=datetime(2026, 11, 27, 11, 0))
    assert a.is_scan_due(now)
