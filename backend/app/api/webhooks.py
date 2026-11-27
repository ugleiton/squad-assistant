from fastapi import APIRouter, Depends, Header, HTTPException, Request
from sqlmodel import Session

from ..db import get_session
from ..models import ReviewAssistant
from ..security import verify_token

router = APIRouter(prefix="/webhooks", tags=["webhooks"])


@router.post("/gitlab/{assistant_id}")
async def gitlab_webhook(
    assistant_id: int,
    request: Request,
    x_gitlab_token: str | None = Header(default=None),
    s: Session = Depends(get_session),
):
    a = s.get(ReviewAssistant, assistant_id)
    if not a or not verify_token(x_gitlab_token, a.webhook_token_hash):
        raise HTTPException(401, "Invalid token")
    if not a.enabled:
        return {"ignored": "assistant disabled"}
    event = await request.json()
    from ..review.service import ReviewService

    handled = await ReviewService(s, a).handle_gitlab_event(event)
    return {"threads": handled}
