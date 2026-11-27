from app.gitlab.client import MergeRequestStatus
from app.models import ReviewState
from app.review.state import compute_state


def mr(**kw):
    base = dict(
        state="opened",
        approved=False,
        user_notes_count=0,
        unresolved_discussions=0,
        resolvable_discussions=0,
        web_url="",
    )
    return MergeRequestStatus(**{**base, **kw})


def test_awaiting_when_untouched():
    assert compute_state(mr()) == ReviewState.awaiting_review


def test_in_review_with_open_discussion():
    m = mr(user_notes_count=2, resolvable_discussions=1, unresolved_discussions=1)
    assert compute_state(m) == ReviewState.in_review


def test_in_review_with_chat_reply_only():
    assert compute_state(mr(), chat_replies_from_others=1) == ReviewState.in_review


def test_resolved_when_all_discussions_resolved():
    m = mr(user_notes_count=3, resolvable_discussions=2, unresolved_discussions=0)
    assert compute_state(m) == ReviewState.resolved


def test_resolved_when_approved():
    assert compute_state(mr(approved=True)) == ReviewState.resolved


def test_merged_and_closed():
    assert compute_state(mr(state="merged")) == ReviewState.merged
    assert compute_state(mr(state="closed")) == ReviewState.closed
