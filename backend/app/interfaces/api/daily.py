from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, delete, select

from ...infrastructure import container
from ...infrastructure.persistence.db import get_session
from ...infrastructure.persistence.models import (
    DailyAssistant,
    DailyParticipant,
    DailyRotationState,
    DailySchedule,
)
from ...infrastructure.security import encrypt
from .schemas import DailyAssistantIn, DailyAssistantOut, ParticipantIn, ScheduleIn

router = APIRouter(prefix="/daily-assistants", tags=["daily"])


def _get(s: Session, aid: int) -> DailyAssistant:
    a = s.get(DailyAssistant, aid)
    if not a:
        raise HTTPException(404, "Not found")
    return a


def _out(s: Session, a: DailyAssistant) -> DailyAssistantOut:
    schedules = s.exec(
        select(DailySchedule)
        .where(DailySchedule.daily_assistant_id == a.id)
        .order_by(DailySchedule.weekday, DailySchedule.time)
    ).all()
    parts = s.exec(
        select(DailyParticipant)
        .where(DailyParticipant.daily_assistant_id == a.id)
        .order_by(DailyParticipant.order)
    ).all()
    state = s.get(DailyRotationState, a.id)
    data = a.model_dump(exclude={"webhook_url"})
    return DailyAssistantOut(
        **data,
        has_webhook_url=bool(a.webhook_url),
        schedules=[ScheduleIn(weekday=x.weekday, time=x.time) for x in schedules],
        participants=[
            ParticipantIn(member_id=p.member_id, order=p.order, active=p.active) for p in parts
        ],
        current_facilitator_id=state.current_member_id if state else None,
    )


def _validate(body: DailyAssistantIn) -> None:
    try:
        ZoneInfo(body.timezone)
    except ZoneInfoNotFoundError as exc:
        raise HTTPException(422, f"Unknown timezone {body.timezone}") from exc
    if body.delivery == "bot" and not (body.chat_connection_id and body.channel_id):
        raise HTTPException(422, "Bot delivery needs chat_connection_id and channel_id")


def _apply(s: Session, a: DailyAssistant, body: DailyAssistantIn) -> None:
    for k, v in body.model_dump(exclude={"schedules", "participants", "webhook_url"}).items():
        setattr(a, k, v)
    if body.webhook_url:
        a.webhook_url = encrypt(body.webhook_url)
    s.add(a)
    s.flush()
    s.exec(delete(DailySchedule).where(DailySchedule.daily_assistant_id == a.id))
    s.exec(delete(DailyParticipant).where(DailyParticipant.daily_assistant_id == a.id))
    for x in body.schedules:
        s.add(DailySchedule(daily_assistant_id=a.id, weekday=x.weekday, time=x.time))
    for i, p in enumerate(body.participants):
        s.add(
            DailyParticipant(
                daily_assistant_id=a.id, member_id=p.member_id, order=p.order or i, active=p.active
            )
        )


@router.get("", response_model=list[DailyAssistantOut])
def list_assistants(s: Session = Depends(get_session)):
    return [_out(s, a) for a in s.exec(select(DailyAssistant)).all()]


@router.post("", response_model=DailyAssistantOut, status_code=201)
def create_assistant(body: DailyAssistantIn, s: Session = Depends(get_session)):
    _validate(body)
    a = DailyAssistant(name=body.name)
    _apply(s, a, body)
    s.commit()
    s.refresh(a)
    return _out(s, a)


@router.get("/{aid}", response_model=DailyAssistantOut)
def get_assistant(aid: int, s: Session = Depends(get_session)):
    return _out(s, _get(s, aid))


@router.put("/{aid}", response_model=DailyAssistantOut)
def update_assistant(aid: int, body: DailyAssistantIn, s: Session = Depends(get_session)):
    _validate(body)
    a = _get(s, aid)
    _apply(s, a, body)
    s.commit()
    s.refresh(a)
    return _out(s, a)


@router.post("/{aid}/send-test")
async def send_test(aid: int, s: Session = Depends(get_session)):
    """Posts a sample reminder now, without advancing the rotation."""
    _get(s, aid)
    return {"text": await container.daily_reminder(s, aid).send_test()}


@router.delete("/{aid}", status_code=204)
def delete_assistant(aid: int, s: Session = Depends(get_session)):
    a = _get(s, aid)
    s.exec(delete(DailySchedule).where(DailySchedule.daily_assistant_id == aid))
    s.exec(delete(DailyParticipant).where(DailyParticipant.daily_assistant_id == aid))
    a.enabled = False
    s.add(a)
    s.commit()
