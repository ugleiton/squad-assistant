"""SQLModel implementations of the application repository ports."""

from dataclasses import asdict
from datetime import datetime

from sqlmodel import Session, select

from ...domain import entities as d
from . import mappers
from . import models as m


class SqlReviewRepository:
    def __init__(self, session: Session):
        self.s = session

    def get_assistant(self, assistant_id: int) -> d.ReviewAssistant | None:
        row = self.s.get(m.ReviewAssistant, assistant_id)
        return mappers.review_assistant(row) if row else None

    def list_enabled_assistants(self) -> list[d.ReviewAssistant]:
        rows = self.s.exec(select(m.ReviewAssistant).where(m.ReviewAssistant.enabled)).all()
        return [mappers.review_assistant(r) for r in rows]

    def mark_scanned(self, assistant_id: int, at: datetime) -> None:
        row = self.s.get(m.ReviewAssistant, assistant_id)
        if row:
            row.last_scan_at = at
            self.s.add(row)
            self.s.commit()

    def find_thread(self, assistant_id: int, chat_thread_id: str) -> d.ReviewThread | None:
        row = self.s.exec(
            select(m.ReviewThread).where(
                m.ReviewThread.review_assistant_id == assistant_id,
                m.ReviewThread.chat_thread_id == chat_thread_id,
            )
        ).first()
        return mappers.review_thread(row) if row else None

    def open_threads(self, assistant_id: int) -> list[d.ReviewThread]:
        rows = self.s.exec(
            select(m.ReviewThread).where(
                m.ReviewThread.review_assistant_id == assistant_id,
                m.ReviewThread.state.notin_([d.ReviewState.merged, d.ReviewState.closed]),
            )
        ).all()
        return [mappers.review_thread(r) for r in rows]

    def threads_for_mr(self, assistant_id: int, iid: int) -> list[d.ReviewThread]:
        rows = self.s.exec(
            select(m.ReviewThread).where(
                m.ReviewThread.review_assistant_id == assistant_id, m.ReviewThread.mr_iid == iid
            )
        ).all()
        return [mappers.review_thread(r) for r in rows]

    def save_thread(self, thread: d.ReviewThread) -> d.ReviewThread:
        data = asdict(thread)
        row = self.s.get(m.ReviewThread, thread.id) if thread.id else None
        if row is None:
            data.pop("id")
            row = m.ReviewThread(**data)
        else:
            for k, v in data.items():
                setattr(row, k, v)
        self.s.add(row)
        self.s.commit()
        self.s.refresh(row)
        thread.id = row.id
        return thread

    def add_event(self, thread_id: int, type: str, payload: dict) -> None:
        self.s.add(m.ReviewEvent(review_thread_id=thread_id, type=type, payload=payload))
        self.s.commit()

    def squad_members(self, squad_ids: list[int]) -> list[tuple[int, d.Member]]:
        if not squad_ids:
            return []
        rows = self.s.exec(
            select(m.SquadMember, m.Member)
            .join(m.Member, m.Member.id == m.SquadMember.member_id)
            .where(m.SquadMember.squad_id.in_(squad_ids))
        ).all()
        return [(sm.squad_id, mappers.member(mem)) for sm, mem in rows]


class SqlDailyRepository:
    def __init__(self, session: Session):
        self.s = session

    def list_enabled_assistants(self) -> list[d.DailyAssistant]:
        rows = self.s.exec(select(m.DailyAssistant).where(m.DailyAssistant.enabled)).all()
        return [mappers.daily_assistant(r) for r in rows]

    def schedules(self, assistant_id: int) -> list[d.DailySchedule]:
        rows = self.s.exec(
            select(m.DailySchedule).where(m.DailySchedule.daily_assistant_id == assistant_id)
        ).all()
        return [d.DailySchedule(weekday=r.weekday, time=r.time) for r in rows]

    def participants(self, assistant_id: int) -> list[d.Member]:
        rows = self.s.exec(
            select(m.DailyParticipant, m.Member)
            .join(m.Member, m.Member.id == m.DailyParticipant.member_id)
            .where(m.DailyParticipant.daily_assistant_id == assistant_id, m.DailyParticipant.active)
            .order_by(m.DailyParticipant.order, m.Member.name)
        ).all()
        return [mappers.member(mem) for _, mem in rows]

    def rotation_state(self, assistant_id: int) -> d.RotationState:
        row = self.s.get(m.DailyRotationState, assistant_id)
        return d.RotationState(row.current_member_id, row.period_key) if row else d.RotationState()

    def save_rotation_state(self, assistant_id: int, state: d.RotationState) -> None:
        row = self.s.get(m.DailyRotationState, assistant_id) or m.DailyRotationState(
            daily_assistant_id=assistant_id
        )
        row.current_member_id, row.period_key = state.current_member_id, state.period_key
        self.s.add(row)
        self.s.commit()

    def run_exists(self, assistant_id: int, scheduled_for: datetime) -> bool:
        return (
            self.s.exec(
                select(m.DailyRun).where(
                    m.DailyRun.daily_assistant_id == assistant_id,
                    m.DailyRun.scheduled_for == scheduled_for,
                )
            ).first()
            is not None
        )

    def add_run(self, assistant_id: int, scheduled_for: datetime, facilitator_id: int | None):
        self.s.add(
            m.DailyRun(
                daily_assistant_id=assistant_id,
                scheduled_for=scheduled_for,
                facilitator_id=facilitator_id,
            )
        )
        self.s.commit()
