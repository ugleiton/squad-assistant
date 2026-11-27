from datetime import UTC, datetime, time

from app.daily.service import DailyService
from app.models import (
    DailyAssistant,
    DailyParticipant,
    DailySchedule,
    DeliveryMode,
    Member,
    RotationMode,
)


async def test_sends_reminder_once_with_facilitator(session, fake_chat):
    a = DailyAssistant(
        name="Squad A",
        timezone="America/Sao_Paulo",
        delivery=DeliveryMode.bot,
        channel_id="C1",
        lead_time_minutes=10,
        rotation_mode=RotationMode.daily,
        language="pt_BR",
    )
    session.add(a)
    session.commit()
    m1, m2 = Member(name="Ana", chat_user_id="U1"), Member(name="Bruno", chat_user_id="U2")
    session.add_all([m1, m2])
    session.commit()
    session.add_all(
        [
            DailyParticipant(daily_assistant_id=a.id, member_id=m1.id, order=0),
            DailyParticipant(daily_assistant_id=a.id, member_id=m2.id, order=1),
            DailySchedule(daily_assistant_id=a.id, weekday=4, time=time(9, 30)),  # Friday
        ]
    )
    session.commit()
    chat = fake_chat()
    svc = DailyService(session, a, chat=chat)

    # 2026-11-27 is a Friday; 09:21 in São Paulo = 12:21 UTC
    assert not await svc.tick(datetime(2026, 11, 27, 12, 10, tzinfo=UTC))
    assert await svc.tick(datetime(2026, 11, 27, 12, 21, tzinfo=UTC))
    assert not await svc.tick(datetime(2026, 11, 27, 12, 22, tzinfo=UTC))
    assert len(chat.posts) == 1
    assert "Daily em 9 min (09:30)" in chat.posts[0][1]
    assert "<@U1>" in chat.posts[0][1]
