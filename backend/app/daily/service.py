"""Daily assistant: sends a reminder `lead_time_minutes` before each scheduled daily."""

import logging
from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo

from sqlmodel import Session, select

from ..chat import ChatProvider, provider_for_connection, webhook_provider
from ..i18n import t
from ..models import (
    ChatConnection,
    DailyAssistant,
    DailyParticipant,
    DailyRotationState,
    DailyRun,
    DailySchedule,
    DeliveryMode,
    Member,
)
from ..security import decrypt
from .rotation import next_facilitator

log = logging.getLogger(__name__)


def due_daily(
    schedules: list[DailySchedule],
    lead_minutes: int,
    now_local: datetime,
    window_minutes: int = 15,
) -> datetime | None:
    """Return the local datetime of the daily whose reminder is due now, if any.
    A reminder is due from (start - lead) until start, capped by `window_minutes` so a
    restarted server does not send very late reminders."""
    for day_offset in (0, 1):  # a reminder may fall on the previous day near midnight
        day = (now_local + timedelta(days=day_offset)).date()
        for sch in schedules:
            if sch.weekday != day.weekday():
                continue
            start = datetime.combine(day, sch.time, tzinfo=now_local.tzinfo)
            alert_at = start - timedelta(minutes=lead_minutes)
            if alert_at <= now_local < min(start, alert_at + timedelta(minutes=window_minutes)):
                return start
    return None


class DailyService:
    def __init__(
        self, session: Session, assistant: DailyAssistant, chat: ChatProvider | None = None
    ):
        self.s = session
        self.a = assistant
        self._chat = chat

    @property
    def chat(self) -> ChatProvider:
        if self._chat is None:
            if self.a.delivery == DeliveryMode.webhook:
                provider = "slack"
                if self.a.chat_connection_id:
                    conn = self.s.get(ChatConnection, self.a.chat_connection_id)
                    provider = conn.provider.value if conn else provider
                self._chat = webhook_provider(decrypt(self.a.webhook_url) or "", provider)
            else:
                conn = self.s.get(ChatConnection, self.a.chat_connection_id)
                self._chat = provider_for_connection(conn)
        return self._chat

    def participants(self) -> list[Member]:
        rows = self.s.exec(
            select(DailyParticipant, Member)
            .join(Member, Member.id == DailyParticipant.member_id)
            .where(DailyParticipant.daily_assistant_id == self.a.id, DailyParticipant.active)
            .order_by(DailyParticipant.order, Member.name)
        ).all()
        return [m for _, m in rows]

    def facilitator_for(self, day) -> Member | None:
        members = self.participants()
        state = self.s.get(DailyRotationState, self.a.id) or DailyRotationState(
            daily_assistant_id=self.a.id
        )
        fid, key = next_facilitator(
            [m.id for m in members],
            self.a.rotation_mode,
            state.current_member_id,
            state.period_key,
            day,
        )
        state.current_member_id, state.period_key = fid, key
        self.s.add(state)
        return next((m for m in members if m.id == fid), None)

    async def tick(self, now: datetime | None = None) -> bool:
        """Send the reminder if one is due. Safe to call every minute."""
        now = now or datetime.now(UTC)
        tz = ZoneInfo(self.a.timezone or "UTC")
        now_local = now.astimezone(tz)
        schedules = list(
            self.s.exec(
                select(DailySchedule).where(DailySchedule.daily_assistant_id == self.a.id)
            ).all()
        )
        start = due_daily(schedules, self.a.lead_time_minutes, now_local)
        if start is None:
            return False
        start_utc = start.astimezone(UTC)
        already = self.s.exec(
            select(DailyRun).where(
                DailyRun.daily_assistant_id == self.a.id, DailyRun.scheduled_for == start_utc
            )
        ).first()
        if already:
            return False
        facilitator = self.facilitator_for(start.date())
        text = self.render(start, now_local, facilitator)
        await self.chat.post_message(self.a.channel_id, text)
        self.s.add(
            DailyRun(
                daily_assistant_id=self.a.id,
                scheduled_for=start_utc,
                facilitator_id=facilitator.id if facilitator else None,
            )
        )
        self.s.commit()
        return True

    def render(self, start: datetime, now_local: datetime, facilitator: Member | None) -> str:
        minutes = max(0, round((start - now_local).total_seconds() / 60))
        fac = (
            self.chat.mention(facilitator.chat_user_id, facilitator.chat_username)
            if facilitator
            else ""
        )
        params = dict(
            minutes=minutes,
            time=start.strftime("%H:%M"),
            facilitator=fac,
            meeting_url=self.a.meeting_url or "",
        )
        if self.a.message_template:
            return self.a.message_template.format(**params)
        key = "daily.reminder" if facilitator else "daily.reminder_no_facilitator"
        text = t(self.a.language, key, **params)
        if self.a.meeting_url:
            text += "\n" + t(self.a.language, "daily.meeting_link", **params)
        return text
