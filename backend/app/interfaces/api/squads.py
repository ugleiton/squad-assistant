from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, delete, select

from ...infrastructure.persistence.db import get_session
from ...infrastructure.persistence.models import Member, Squad, SquadMember
from .schemas import MemberIn, SquadIn, SquadOut

router = APIRouter(tags=["squads"])


def _404():
    raise HTTPException(404, "Not found")


@router.get("/members", response_model=list[Member])
def list_members(s: Session = Depends(get_session)):
    return s.exec(select(Member).order_by(Member.name)).all()


@router.post("/members", response_model=Member, status_code=201)
def create_member(body: MemberIn, s: Session = Depends(get_session)):
    m = Member(**body.model_dump())
    s.add(m)
    s.commit()
    s.refresh(m)
    return m


@router.put("/members/{mid}", response_model=Member)
def update_member(mid: int, body: MemberIn, s: Session = Depends(get_session)):
    m = s.get(Member, mid) or _404()
    for k, v in body.model_dump().items():
        setattr(m, k, v)
    s.add(m)
    s.commit()
    s.refresh(m)
    return m


@router.delete("/members/{mid}", status_code=204)
def delete_member(mid: int, s: Session = Depends(get_session)):
    m = s.get(Member, mid) or _404()
    s.exec(delete(SquadMember).where(SquadMember.member_id == mid))
    s.delete(m)
    s.commit()


def _squad_out(s: Session, sq: Squad) -> SquadOut:
    ids = s.exec(select(SquadMember.member_id).where(SquadMember.squad_id == sq.id)).all()
    return SquadOut(id=sq.id, name=sq.name, member_ids=list(ids))


def _set_members(s: Session, squad_id: int, member_ids: list[int]) -> None:
    s.exec(delete(SquadMember).where(SquadMember.squad_id == squad_id))
    for mid in dict.fromkeys(member_ids):
        s.add(SquadMember(squad_id=squad_id, member_id=mid))


@router.get("/squads", response_model=list[SquadOut])
def list_squads(s: Session = Depends(get_session)):
    return [_squad_out(s, sq) for sq in s.exec(select(Squad).order_by(Squad.name)).all()]


@router.post("/squads", response_model=SquadOut, status_code=201)
def create_squad(body: SquadIn, s: Session = Depends(get_session)):
    sq = Squad(name=body.name)
    s.add(sq)
    s.commit()
    s.refresh(sq)
    _set_members(s, sq.id, body.member_ids)
    s.commit()
    return _squad_out(s, sq)


@router.put("/squads/{sid}", response_model=SquadOut)
def update_squad(sid: int, body: SquadIn, s: Session = Depends(get_session)):
    sq = s.get(Squad, sid) or _404()
    sq.name = body.name
    _set_members(s, sid, body.member_ids)
    s.add(sq)
    s.commit()
    return _squad_out(s, sq)


@router.delete("/squads/{sid}", status_code=204)
def delete_squad(sid: int, s: Session = Depends(get_session)):
    sq = s.get(Squad, sid) or _404()
    s.exec(delete(SquadMember).where(SquadMember.squad_id == sid))
    s.delete(sq)
    s.commit()
