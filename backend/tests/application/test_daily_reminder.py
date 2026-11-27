from datetime import UTC, datetime, time

from app.application.daily.reminder import DailyReminder
from app.domain.entities import DailyAssistant, DailySchedule, Member
from app.domain.enums import RotationMode
from tests.fakes import FakeChat, InMemoryDailyRepository, fake_translate

ANA, BRUNO = Member(1, "Ana", "U1"), Member(2, "Bruno", "U2")


def make(rotation=RotationMode.daily, **kw):
    a = DailyAssistant(
        id=1,
        name="Squad A",
        timezone="America/Sao_Paulo",
        channel_id="C1",
        lead_time_minutes=10,
        rotation_mode=rotation,
        language="pt_BR",
        **kw,
    )
    repo = InMemoryDailyRepository(
        schedules=[DailySchedule(weekday=d, time=time(9, 30)) for d in range(5)],
        participants=[ANA, BRUNO],
    )
    chat = FakeChat()
    return DailyReminder(a, repo, chat, fake_translate), repo, chat


async def test_sends_reminder_once_and_rotates_daily():
    reminder, repo, chat = make()
    # Friday 2026-11-27, 09:21 in São Paulo = 12:21 UTC
    assert not await reminder.tick(datetime(2026, 11, 27, 12, 10, tzinfo=UTC))
    assert await reminder.tick(datetime(2026, 11, 27, 12, 21, tzinfo=UTC))
    assert not await reminder.tick(datetime(2026, 11, 27, 12, 22, tzinfo=UTC))
    assert len(chat.posts) == 1
    assert "daily.reminder" in chat.posts[0][1] and "facilitator=<@U1>" in chat.posts[0][1]
    assert "minutes=9" in chat.posts[0][1] and "time=09:30" in chat.posts[0][1]

    # Next weekday (Monday) -> next facilitator
    assert await reminder.tick(datetime(2026, 11, 30, 12, 21, tzinfo=UTC))
    assert "facilitator=<@U2>" in chat.posts[-1][1]


async def test_no_rotation_has_no_facilitator_and_custom_template():
    reminder, _, chat = make(
        rotation=RotationMode.none,
        message_template="Daily {time} em {minutes} min {meeting_url}",
        meeting_url="https://meet/x",
    )
    await reminder.tick(datetime(2026, 11, 27, 12, 20, tzinfo=UTC))
    assert chat.posts[0][1] == "Daily 09:30 em 10 min https://meet/x"


async def test_send_test_does_not_advance_rotation():
    reminder, repo, chat = make()
    await reminder.send_test(datetime(2026, 11, 27, 12, 0, tzinfo=UTC))
    assert len(chat.posts) == 1 and repo.state.current_member_id is None and repo.runs == []
