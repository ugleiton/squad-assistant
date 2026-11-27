import json
from datetime import UTC, datetime

import httpx
import respx

from app.infrastructure.chat.mattermost import MattermostProvider
from app.infrastructure.chat.slack import SlackProvider
from app.infrastructure.chat.webhook import IncomingWebhookProvider

SINCE = datetime(2026, 11, 27, 12, 0, tzinfo=UTC)
TS = f"{SINCE.timestamp() + 60:.6f}"


@respx.mock
async def test_slack_lists_messages_with_pagination_and_attachments():
    history = respx.get("https://slack.com/api/conversations.history").mock(
        side_effect=[
            httpx.Response(
                200,
                json={
                    "ok": True,
                    "messages": [
                        {"ts": TS, "user": "U1", "text": "pls review"},
                        {"ts": TS, "subtype": "channel_join", "text": "joined"},
                    ],
                    "response_metadata": {"next_cursor": "c2"},
                },
            ),
            httpx.Response(
                200,
                json={
                    "ok": True,
                    "messages": [
                        {
                            "ts": TS,
                            "subtype": "bot_message",
                            "bot_id": "B1",
                            "text": "",
                            "attachments": [{"title_link": "https://gl/g/app/-/merge_requests/3"}],
                        }
                    ],
                },
            ),
        ]
    )
    msgs = await SlackProvider("xoxb").list_messages("C1", SINCE)
    assert [m.user_id for m in msgs] == ["U1", "B1"]
    assert "merge_requests/3" in msgs[1].text
    assert history.calls[0].request.headers["authorization"] == "Bearer xoxb"
    assert history.calls[1].request.url.params["cursor"] == "c2"


@respx.mock
async def test_slack_reactions_replies_and_post():
    add = respx.post("https://slack.com/api/reactions.add").mock(
        return_value=httpx.Response(200, json={"ok": False, "error": "already_reacted"})
    )
    respx.post("https://slack.com/api/reactions.remove").mock(
        return_value=httpx.Response(200, json={"ok": True})
    )
    post = respx.post("https://slack.com/api/chat.postMessage").mock(
        return_value=httpx.Response(200, json={"ok": True, "ts": "2.2"})
    )
    respx.get("https://slack.com/api/conversations.replies").mock(
        return_value=httpx.Response(
            200,
            json={
                "ok": True,
                "messages": [{"ts": "1.1", "user": "U1"}, {"ts": "1.2", "user": "U2"}],
            },
        )
    )
    respx.get("https://slack.com/api/auth.test").mock(
        return_value=httpx.Response(200, json={"ok": True, "user_id": "UBOT"})
    )
    slack = SlackProvider("xoxb")
    await slack.add_reaction("C1", "1.1", "mag")  # already_reacted is not an error
    await slack.remove_reaction("C1", "1.1", "hourglass_flowing_sand")
    assert await slack.post_message("C1", "hi", thread_id="1.1") == "2.2"
    assert json.loads(post.calls[0].request.content) == {
        "channel": "C1",
        "text": "hi",
        "thread_ts": "1.1",
    }
    assert json.loads(add.calls[0].request.content)["name"] == "mag"
    assert [r.id for r in await slack.list_replies("C1", "1.1")] == ["1.2"]
    assert await slack.get_bot_user_id() == "UBOT"
    assert slack.mention("U2") == "<@U2>"


@respx.mock
async def test_slack_retries_once_when_rate_limited():
    route = respx.post("https://slack.com/api/chat.postMessage").mock(
        side_effect=[
            httpx.Response(429, headers={"Retry-After": "0"}),
            httpx.Response(200, json={"ok": True, "ts": "3.3"}),
        ]
    )
    assert await SlackProvider("xoxb").post_message("C1", "hi") == "3.3"
    assert route.call_count == 2


@respx.mock
async def test_slack_api_error_raises():
    respx.post("https://slack.com/api/chat.postMessage").mock(
        return_value=httpx.Response(200, json={"ok": False, "error": "not_in_channel"})
    )
    try:
        await SlackProvider("xoxb").post_message("C1", "hi")
    except RuntimeError as exc:
        assert "not_in_channel" in str(exc)
    else:
        raise AssertionError("expected an error")


MM = "https://mm.example.com/api/v4"


@respx.mock
async def test_mattermost_messages_filter_replies_system_and_edited_old_posts():
    since_ms = int(SINCE.timestamp() * 1000)
    respx.get(f"{MM}/channels/C1/posts").mock(
        return_value=httpx.Response(
            200,
            json={
                "posts": {
                    "p1": {"id": "p1", "user_id": "u1", "message": "mr", "create_at": since_ms + 1},
                    "p2": {
                        "id": "p2",
                        "root_id": "p1",
                        "message": "reply",
                        "create_at": since_ms + 2,
                    },
                    "p3": {"id": "p3", "type": "system_join_channel", "create_at": since_ms + 3},
                    "p4": {"id": "p4", "message": "old edited", "create_at": since_ms - 1000},
                    "p5": {
                        "id": "p5",
                        "message": "",
                        "create_at": since_ms + 5,
                        "props": {"attachments": [{"text": "https://gl/g/a/-/merge_requests/9"}]},
                    },
                }
            },
        )
    )
    msgs = await MattermostProvider("https://mm.example.com/", "tok").list_messages("C1", SINCE)
    assert sorted(m.id for m in msgs) == ["p1", "p5"]
    assert "merge_requests/9" in next(m for m in msgs if m.id == "p5").text


@respx.mock
async def test_mattermost_reactions_post_and_mentions():
    respx.get(f"{MM}/users/me").mock(return_value=httpx.Response(200, json={"id": "bot1"}))
    add = respx.post(f"{MM}/reactions").mock(return_value=httpx.Response(200, json={}))
    rm = respx.delete(f"{MM}/users/bot1/posts/p1/reactions/mag").mock(
        return_value=httpx.Response(404)
    )
    post = respx.post(f"{MM}/posts").mock(return_value=httpx.Response(201, json={"id": "p9"}))
    respx.get(f"{MM}/posts/p1/thread").mock(
        return_value=httpx.Response(
            200,
            json={
                "posts": {
                    "p1": {"id": "p1", "create_at": 1},
                    "p2": {"id": "p2", "user_id": "u2", "create_at": 2},
                }
            },
        )
    )
    mm = MattermostProvider("https://mm.example.com", "tok")
    await mm.add_reaction("C1", "p1", "mag")
    await mm.remove_reaction("C1", "p1", "mag")  # 404 = reaction already gone
    assert await mm.post_message("C1", "hi", thread_id="p1") == "p9"
    assert json.loads(add.calls[0].request.content) == {
        "user_id": "bot1",
        "post_id": "p1",
        "emoji_name": "mag",
    }
    assert json.loads(post.calls[0].request.content)["root_id"] == "p1"
    assert rm.called
    assert [r.id for r in await mm.list_replies("C1", "p1")] == ["p2"]
    assert await mm.get_bot_user_id() == "bot1"
    assert mm.mention("u2", "bia") == "@bia"


@respx.mock
async def test_incoming_webhook_posts_text_and_mentions_by_platform():
    hook = respx.post("https://hooks.example/x").mock(return_value=httpx.Response(200))
    slack = IncomingWebhookProvider("https://hooks.example/x", "slack")
    await slack.post_message(None, "Daily!")
    assert json.loads(hook.calls[0].request.content) == {"text": "Daily!"}
    assert slack.mention("U1", "ana") == "<@U1>"
    assert (
        IncomingWebhookProvider("https://hooks.example/x", "mattermost").mention("U1", "ana")
        == "@ana"
    )
