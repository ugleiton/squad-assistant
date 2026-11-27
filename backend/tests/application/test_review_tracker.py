from datetime import UTC, datetime

from app.application.review.tracker import ReviewTracker
from app.domain.entities import ChatMessage, Member, MergeRequestStatus, ReviewAssistant
from tests.fakes import FakeChat, FakeGitLab, InMemoryReviewRepository, fake_translate

NOW = datetime(2026, 11, 27, 12, 0, tzinfo=UTC)
ANA, BIA = Member(id=1, name="Ana", chat_user_id="U1"), Member(id=2, name="Bia", chat_user_id="U2")


def status(state="opened", approved=False, notes=0, unresolved=0, resolvable=0):
    return MergeRequestStatus(state, approved, notes, unresolved, "", resolvable)


def make(messages, gl_status, **assistant_kw):
    a = ReviewAssistant(
        id=1,
        name="Review",
        chat_connection_id=1,
        channel_id="C1",
        gitlab_connection_id=1,
        gitlab_projects=["g/app"],
        squad_ids=[10],
        **assistant_kw,
    )
    repo = InMemoryReviewRepository([a], squads=[(10, ANA), (10, BIA)])
    chat = FakeChat(messages=messages)
    gl = FakeGitLab(gl_status)
    return ReviewTracker(a, repo, chat, gl, fake_translate), repo, chat, gl


def msg(id, text, user="U1"):
    return ChatMessage(id=id, user_id=user, text=text, created_at=NOW)


async def test_scan_links_thread_mentions_squad_and_tracks_states():
    tracker, repo, chat, gl = make(
        [msg("111.1", "review pls https://gitlab.com/g/app/-/merge_requests/7")], status()
    )

    assert await tracker.scan(NOW) == 1
    assert chat.posts[0][2] == "111.1"
    assert "<@U2>" in chat.posts[0][1] and "<@U1>" not in chat.posts[0][1]
    assert ("+", "111.1", "hourglass_flowing_sand") in chat.reactions
    assert repo.assistants[1].last_scan_at is not None

    # Rescan does not duplicate the thread nor mention again
    assert await tracker.scan(NOW) == 0
    assert len(chat.posts) == 1

    # A discussion is opened -> in review
    gl.status = status(notes=1, unresolved=1, resolvable=1)
    await tracker.scan(NOW)
    assert chat.reactions[-2:] == [("-", "111.1", "hourglass_flowing_sand"), ("+", "111.1", "mag")]

    # Merge webhook -> merge message + rocket, thread no longer open
    gl.status = status(state="merged", approved=True, notes=1, resolvable=1)
    event = {
        "object_kind": "merge_request",
        "project": {"path_with_namespace": "g/app", "id": 5},
        "user": {"username": "bia"},
        "object_attributes": {"iid": 7, "action": "merge", "target_branch": "main"},
    }
    assert await tracker.handle_gitlab_event(event) == 1
    assert "review.merged" in chat.posts[-1][1] and "user=bia" in chat.posts[-1][1]
    assert chat.reactions[-1] == ("+", "111.1", "rocket")
    assert repo.open_threads(1) == []


async def test_closed_mr_gets_gray_check():
    tracker, repo, chat, gl = make(
        [msg("1.1", "https://gitlab.com/g/app/-/merge_requests/9")], status(state="closed")
    )
    await tracker.scan(NOW)
    assert chat.reactions[-1] == ("+", "1.1", "heavy_check_mark")


async def test_ignores_other_projects_and_chat_replies_from_author_or_bot():
    tracker, repo, chat, _ = make(
        [
            msg("1.1", "https://gitlab.com/other/app/-/merge_requests/1"),
            msg("2.2", "https://gitlab.com/g/app/-/merge_requests/2"),
        ],
        status(),
    )
    chat.replies = {"2.2": [msg("r1", "bump", user="U1"), msg("r2", "hi", user="BOT")]}
    assert await tracker.scan(NOW) == 1
    [thread] = repo.open_threads(1)
    assert thread.chat_thread_id == "2.2" and thread.state.value == "awaiting_review"


async def test_pipeline_message_posted_once_per_status():
    tracker, repo, chat, _ = make(
        [msg("1.1", "https://gitlab.com/g/app/-/merge_requests/8")], status()
    )
    await tracker.scan(NOW)
    event = {
        "object_kind": "pipeline",
        "project": {"path_with_namespace": "g/app", "web_url": "u"},
        "merge_request": {"iid": 8},
        "object_attributes": {"id": 99, "status": "failed", "ref": "f"},
    }
    await tracker.handle_gitlab_event(event)
    await tracker.handle_gitlab_event(event)
    assert sum("pipeline_id=99" in p[1] for p in chat.posts) == 1


async def test_features_can_be_disabled():
    tracker, repo, chat, _ = make(
        [msg("1.1", "https://gitlab.com/g/app/-/merge_requests/3")],
        status(),
        features={"mention_squad": False, "mark_status": False},
    )
    await tracker.scan(NOW)
    assert chat.posts == [] and chat.reactions == []
