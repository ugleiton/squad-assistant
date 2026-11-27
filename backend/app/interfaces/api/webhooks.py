import logging

from fastapi import APIRouter, Depends, Header, HTTPException, Request
from sqlmodel import Session

from ...application.review.webhook_auth import verify_token
from ...infrastructure import container
from ...infrastructure.persistence.db import get_session
from ...infrastructure.persistence.repositories import SqlReviewRepository

router = APIRouter(prefix="/webhooks", tags=["webhooks"])
log = logging.getLogger(__name__)


@router.post("/gitlab/{assistant_id}")
async def gitlab_webhook(
    assistant_id: int,
    request: Request,
    x_gitlab_token: str | None = Header(default=None),
    s: Session = Depends(get_session),
):
    a = SqlReviewRepository(s).get_assistant(assistant_id)
    if not a or not verify_token(x_gitlab_token, a.webhook_token_hash):
        raise HTTPException(401, "Invalid token")
    if not a.enabled:
        return {"ignored": "assistant disabled"}
    event = await request.json()
    try:
        async with container.review_tracker(s, a) as tracker:
            handled = await tracker.handle_gitlab_event(event)
    except Exception as exc:
        # Answer 200 anyway: GitLab disables webhooks that keep failing, and the next scan
        # will reconcile the thread state.
        log.exception("failed to handle GitLab event for assistant %s", assistant_id)
        return {"threads": 0, "error": type(exc).__name__}
    return {"threads": handled}
