from fastapi import APIRouter, Depends, Header, HTTPException, Request
from sqlmodel import Session

from ...application.review.webhook_auth import verify_token
from ...infrastructure import container
from ...infrastructure.persistence.db import get_session
from ...infrastructure.persistence.repositories import SqlReviewRepository

router = APIRouter(prefix="/webhooks", tags=["webhooks"])


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
    handled = await container.review_tracker(s, a).handle_gitlab_event(event)
    return {"threads": handled}
