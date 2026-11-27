from datetime import UTC, datetime

from app.chat.base import ChatMessage
from app.gitlab.client import MergeRequestStatus
from app.models import Member, ReviewAssistant, ReviewState, Squad, SquadMember
from app.review.service import ReviewService


class FakeGitLab:
    def __init__(self, status):
        self.status = status

    async def merge_request_status(self, project, iid):
        return self.status


def _setup(session):
    sq = Squad(name="Payments")
    author, mate = Member(name="Ana", chat_user_id="U1"), Member(name="Bia", chat_user_id="U2")
    session.add_all([sq, author, mate])
    session.commit()
    session.add_all(
        [
            SquadMember(squad_id=sq.id, member_id=author.id),
            SquadMember(squad_id=sq.id, member_id=mate.id),
        ]
    )
    a = ReviewAssistant(
        name="Review",
        chat_connection_id=1,
        channel_id="C1",
        gitlab_connection_id=1,
        gitlab_projects=["g/app"],
        squad_ids=[sq.id],
    )
    session.add(a)
    session.commit()
    return a


async def test_scan_links_thread_mentions_squad_and_marks_status(session, fake_chat):
    a = _setup(session)
    now = datetime(2026, 11, 27, 12, 0, tzinfo=UTC)
    chat = fake_chat(
        messages=[
            ChatMessage(
                id="111.1",
                user_id="U1",
                text="review pls https://gitlab.com/g/app/-/merge_requests/7",
                created_at=now,
            )
        ]
    )
    gl = FakeGitLab(MergeRequestStatus("opened", False, 0, 0, "", resolvable_discussions=0))
    svc = ReviewService(session, a, chat=chat, gitlab=gl)

    assert await svc.scan(now) == 1
    assert chat.posts[0][2] == "111.1" and "<@U2>" in chat.posts[0][1]
    assert "<@U1>" not in chat.posts[0][1]
    assert ("+", "111.1", "hourglass_flowing_sand") in chat.reactions

    # Someone opens a discussion -> in review
    gl.status = MergeRequestStatus("opened", False, 1, 1, "", resolvable_discussions=1)
    await svc.scan(now)
    assert chat.reactions[-2:] == [("-", "111.1", "hourglass_flowing_sand"), ("+", "111.1", "mag")]

    # Merge webhook -> message + rocket
    gl.status = MergeRequestStatus("merged", True, 1, 0, "", resolvable_discussions=1)
    event = {
        "object_kind": "merge_request",
        "project": {"path_with_namespace": "g/app", "id": 5},
        "user": {"username": "bia"},
        "object_attributes": {"iid": 7, "action": "merge", "target_branch": "main"},
    }
    assert await svc.handle_gitlab_event(event) == 1
    assert "bia" in chat.posts[-1][1]
    assert chat.reactions[-1] == ("+", "111.1", "rocket")
    assert svc.open_threads() == []
    assert ReviewState.merged


async def test_pipeline_message_posted_once_per_status(session, fake_chat):
    a = _setup(session)
    now = datetime(2026, 11, 27, 12, 0, tzinfo=UTC)
    chat = fake_chat(
        messages=[
            ChatMessage(
                id="1.1",
                user_id="U1",
                text="https://gitlab.com/g/app/-/merge_requests/8",
                created_at=now,
            )
        ]
    )
    svc = ReviewService(
        session, a, chat=chat, gitlab=FakeGitLab(MergeRequestStatus("opened", False, 0, 0, ""))
    )
    await svc.scan(now)
    event = {
        "object_kind": "pipeline",
        "project": {"path_with_namespace": "g/app", "web_url": "u"},
        "merge_request": {"iid": 8},
        "object_attributes": {"id": 99, "status": "failed", "ref": "f"},
    }
    await svc.handle_gitlab_event(event)
    await svc.handle_gitlab_event(event)
    assert sum("#99" in p[1] for p in chat.posts) == 1
