"""Daily reminder use case: send a reminder `lead_time_minutes` before each scheduled daily."""

from datetime import UTC, datetime
from zoneinfo import ZoneInfo

from ...domain.daily_schedule import due_daily
from ...domain.entities import DailyAssistant, Member, RotationState
from ...domain.rotation import next_facilitator
from ..ports import ChatProvider, DailyRepository, Translator


class DailyReminder:
    def __init__(
        self,
        assistant: DailyAssistant,
        repo: DailyRepository,
        chat: ChatProvider,
        translate: Translator,
    ):
        self.a = assistant
        self.repo = repo
        self.chat = chat
        self.t = translate

    def facilitator_for(self, day) -> Member | None:
        members = self.repo.participants(self.a.id)
        state = self.repo.rotation_state(self.a.id)
        fid, key = next_facilitator(
            [m.id for m in members],
            self.a.rotation_mode,
            state.current_member_id,
            state.period_key,
            day,
        )
        self.repo.save_rotation_state(self.a.id, RotationState(fid, key))
        return next((m for m in members if m.id == fid), None)

    async def tick(self, now: datetime | None = None) -> bool:
        """Send the reminder if one is due. Safe to call every minute."""
        now = now or datetime.now(UTC)
        now_local = now.astimezone(ZoneInfo(self.a.timezone or "UTC"))
        start = due_daily(self.repo.schedules(self.a.id), self.a.lead_time_minutes, now_local)
        if start is None:
            return False
        start_utc = start.astimezone(UTC)
        if self.repo.run_exists(self.a.id, start_utc):
            return False
        facilitator = self.facilitator_for(start.date())
        await self.chat.post_message(self.a.channel_id, self.render(start, now_local, facilitator))
        self.repo.add_run(self.a.id, start_utc, facilitator.id if facilitator else None)
        return True

    async def send_test(self, now: datetime | None = None) -> str:
        """Post a sample reminder now, without advancing the rotation."""
        now_local = (now or datetime.now(UTC)).astimezone(ZoneInfo(self.a.timezone or "UTC"))
        members = self.repo.participants(self.a.id)
        text = self.render(now_local, now_local, members[0] if members else None)
        await self.chat.post_message(self.a.channel_id, text)
        return text

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
        text = self.t(self.a.language, key, **params)
        if self.a.meeting_url:
            text += "\n" + self.t(self.a.language, "daily.meeting_link", **params)
        return text
