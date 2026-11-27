from datetime import UTC, datetime

from app.domain.entities import ReviewThread, RotationState
from app.domain.enums import ReviewState
from app.infrastructure.persistence import models as m
from app.infrastructure.persistence.repositories import SqlDailyRepository, SqlReviewRepository


def test_review_repository_roundtrip(session):
    sq = m.Squad(name="S")
    ana = m.Member(name="Ana", chat_user_id="U1")
    session.add_all([sq, ana])
    session.commit()
    session.add(m.SquadMember(squad_id=sq.id, member_id=ana.id))
    a = m.ReviewAssistant(name="R", chat_connection_id=1, channel_id="C", gitlab_connection_id=1)
    session.add(a)
    session.commit()

    repo = SqlReviewRepository(session)
    assert repo.get_assistant(a.id).emojis["closed"] == "heavy_check_mark"
    t = repo.save_thread(
        ReviewThread(None, a.id, "1.1", "g/app", 7, "https://x/g/app/-/merge_requests/7")
    )
    assert t.id is not None
    assert repo.find_thread(a.id, "1.1").mr_iid == 7
    t.state = ReviewState.merged
    repo.save_thread(t)
    assert repo.open_threads(a.id) == []
    assert repo.threads_for_mr(a.id, 7)[0].state == ReviewState.merged
    repo.add_event(t.id, "state", {"to": "merged"})
    assert [(sid, mem.name) for sid, mem in repo.squad_members([sq.id])] == [(sq.id, "Ana")]
    repo.mark_scanned(a.id, datetime(2026, 11, 27, tzinfo=UTC))
    assert repo.get_assistant(a.id).last_scan_at is not None


def test_daily_repository_roundtrip(session):
    a = m.DailyAssistant(name="D")
    ana, bia = m.Member(name="Ana"), m.Member(name="Bia")
    session.add_all([a, ana, bia])
    session.commit()
    session.add_all(
        [
            m.DailyParticipant(daily_assistant_id=a.id, member_id=bia.id, order=1),
            m.DailyParticipant(daily_assistant_id=a.id, member_id=ana.id, order=0),
        ]
    )
    session.commit()
    repo = SqlDailyRepository(session)
    assert [p.name for p in repo.participants(a.id)] == ["Ana", "Bia"]
    assert repo.rotation_state(a.id) == RotationState()
    repo.save_rotation_state(a.id, RotationState(ana.id, "2026-11-27"))
    assert repo.rotation_state(a.id).current_member_id == ana.id
    when = datetime(2026, 11, 27, 12, 30, tzinfo=UTC)
    assert not repo.run_exists(a.id, when)
    repo.add_run(a.id, when, ana.id)
    assert repo.run_exists(a.id, when)
