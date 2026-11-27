from .entities import MergeRequestStatus
from .enums import ReviewState


def compute_state(
    mr: MergeRequestStatus, chat_replies_from_others: int = 0, mark_resolved: bool = True
) -> ReviewState:
    """Rules:
    - merged -> merged; closed -> closed
    - approved, or every review discussion (resolvable thread) resolved -> resolved
    - someone commented (GitLab or chat thread) -> in_review
    - otherwise -> awaiting_review
    With `mark_resolved` off, a resolved MR stays in_review until it is merged or closed.
    """
    if mr.state == "merged":
        return ReviewState.merged
    if mr.state in ("closed", "locked"):
        return ReviewState.closed
    commented = mr.user_notes_count > 0 or chat_replies_from_others > 0
    resolved = mr.approved or (mr.resolvable_discussions > 0 and mr.unresolved_discussions == 0)
    if resolved:
        return ReviewState.resolved if mark_resolved else ReviewState.in_review
    if commented:
        return ReviewState.in_review
    return ReviewState.awaiting_review
