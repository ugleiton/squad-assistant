from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select

from ...application.review.webhook_auth import generate_webhook_token, hash_token
from ...domain.enums import DEFAULT_REVIEW_EMOJIS, DEFAULT_REVIEW_FEATURES
from ...infrastructure import container
from ...infrastructure.config import get_settings
from ...infrastructure.persistence.db import get_session
from ...infrastructure.persistence.models import ReviewAssistant, ReviewThread
from .schemas import ReviewAssistantIn, ReviewAssistantOut, WebhookCredentials

router = APIRouter(prefix="/review-assistants", tags=["review"])


def webhook_url(assistant_id: int) -> str:
    return f"{get_settings().public_url.rstrip('/')}/webhooks/gitlab/{assistant_id}"


def _out(a: ReviewAssistant) -> ReviewAssistantOut:
    data = a.model_dump(exclude={"webhook_token_hash", "last_scan_at"})
    return ReviewAssistantOut(**data, webhook_url=webhook_url(a.id))


def _get(s: Session, aid: int) -> ReviewAssistant:
    a = s.get(ReviewAssistant, aid)
    if not a:
        raise HTTPException(404, "Not found")
    return a


def _apply(a: ReviewAssistant, body: ReviewAssistantIn) -> None:
    for k, v in body.model_dump(exclude={"emojis", "features"}).items():
        setattr(a, k, v)
    a.emojis = {**DEFAULT_REVIEW_EMOJIS, **(a.emojis or {}), **(body.emojis or {})}
    a.features = {**DEFAULT_REVIEW_FEATURES, **(a.features or {}), **(body.features or {})}


@router.get("", response_model=list[ReviewAssistantOut])
def list_assistants(s: Session = Depends(get_session)):
    return [_out(a) for a in s.exec(select(ReviewAssistant)).all()]


@router.post("", response_model=WebhookCredentials, status_code=201)
def create_assistant(body: ReviewAssistantIn, s: Session = Depends(get_session)):
    """Creates the assistant and returns the GitLab webhook URL and a fresh secret token."""
    a = ReviewAssistant(
        name=body.name,
        chat_connection_id=body.chat_connection_id,
        channel_id=body.channel_id,
        gitlab_connection_id=body.gitlab_connection_id,
    )
    _apply(a, body)
    token = generate_webhook_token()
    a.webhook_token_hash = hash_token(token)
    s.add(a)
    s.commit()
    s.refresh(a)
    return WebhookCredentials(webhook_url=webhook_url(a.id), webhook_token=token)


@router.get("/{aid}", response_model=ReviewAssistantOut)
def get_assistant(aid: int, s: Session = Depends(get_session)):
    return _out(_get(s, aid))


@router.put("/{aid}", response_model=ReviewAssistantOut)
def update_assistant(aid: int, body: ReviewAssistantIn, s: Session = Depends(get_session)):
    a = _get(s, aid)
    _apply(a, body)
    s.add(a)
    s.commit()
    s.refresh(a)
    return _out(a)


@router.post("/{aid}/regenerate-token", response_model=WebhookCredentials)
def regenerate_token(aid: int, s: Session = Depends(get_session)):
    a = _get(s, aid)
    token = generate_webhook_token()
    a.webhook_token_hash = hash_token(token)
    s.add(a)
    s.commit()
    return WebhookCredentials(webhook_url=webhook_url(a.id), webhook_token=token)


@router.post("/{aid}/scan")
async def scan_now(aid: int, s: Session = Depends(get_session)):
    _get(s, aid)
    found = await container.review_tracker(s, aid).scan()
    return {"new_threads": found}


@router.get("/{aid}/threads", response_model=list[ReviewThread])
def list_threads(aid: int, s: Session = Depends(get_session)):
    return s.exec(
        select(ReviewThread)
        .where(ReviewThread.review_assistant_id == aid)
        .order_by(ReviewThread.created_at.desc())
    ).all()


@router.delete("/{aid}", status_code=204)
def delete_assistant(aid: int, s: Session = Depends(get_session)):
    a = _get(s, aid)
    a.enabled = False  # soft delete keeps thread history
    s.add(a)
    s.commit()
