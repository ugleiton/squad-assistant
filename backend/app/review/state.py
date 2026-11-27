from ..gitlab.client import MergeRequestStatus
from ..models import ReviewState


def compute_state(mr: MergeRequestStatus, chat_replies_from_others: int = 0) -> ReviewState:
    """Rules:
    - merged -> merged; closed -> closed
    - approved, or every review discussion (resolvable thread) resolved -> resolved
    - someone commented (GitLab or chat thread) -> in_review
    - otherwise -> awaiting_review
    """
    if mr.state == "merged":
        return ReviewState.merged
    if mr.state in ("closed", "locked"):
        return ReviewState.closed
    commented = mr.user_notes_count > 0 or chat_replies_from_others > 0
    if mr.approved:
        return ReviewState.resolved
    if mr.resolvable_discussions > 0 and mr.unresolved_discussions == 0:
        return ReviewState.resolved
    if commented:
        return ReviewState.in_review
    return ReviewState.awaiting_review
