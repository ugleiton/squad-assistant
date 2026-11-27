from urllib.parse import urlparse

import httpx
import pytest
import respx
from fastapi.testclient import TestClient
from sqlmodel import Session

from app.infrastructure.persistence.db import get_session
from app.main import app


@pytest.fixture
def client(engine):
    def _s():
        with Session(engine) as s:
            yield s

    app.dependency_overrides[get_session] = _s
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


@respx.mock
def test_connection_tests_store_bot_id_and_report_gitlab_user(client):
    respx.get("https://slack.com/api/auth.test").mock(
        return_value=httpx.Response(200, json={"ok": True, "user_id": "UBOT"})
    )
    respx.get("https://gl.example.com/api/v4/user").mock(
        return_value=httpx.Response(200, json={"username": "squad-bot"})
    )
    chat = client.post(
        "/api/chat-connections", json={"name": "S", "provider": "slack", "bot_token": "x"}
    ).json()
    r = client.post(f"/api/chat-connections/{chat['id']}/test")
    assert r.json() == {"ok": True, "bot_user_id": "UBOT"}
    assert client.get("/api/chat-connections").json()[0]["bot_user_id"] == "UBOT"

    gl = client.post(
        "/api/gitlab-connections",
        json={"name": "G", "base_url": "https://gl.example.com", "access_token": "t"},
    ).json()
    assert client.post(f"/api/gitlab-connections/{gl['id']}/test").json()["username"] == "squad-bot"


@respx.mock
def test_upstream_errors_become_502(client):
    respx.get("https://slack.com/api/auth.test").mock(
        return_value=httpx.Response(200, json={"ok": False, "error": "invalid_auth"})
    )
    chat = client.post(
        "/api/chat-connections", json={"name": "S", "provider": "slack", "bot_token": "bad"}
    ).json()
    r = client.post(f"/api/chat-connections/{chat['id']}/test")
    assert r.status_code == 502 and "invalid_auth" in r.json()["detail"]


@respx.mock
def test_daily_send_test_through_mattermost_webhook(client):
    hook = respx.post("https://mm.example.com/hooks/abc").mock(return_value=httpx.Response(200))
    ana = client.post("/api/members", json={"name": "Ana", "chat_username": "ana"}).json()
    body = {
        "name": "Daily",
        "delivery": "webhook",
        "webhook_url": "https://mm.example.com/hooks/abc",
        "webhook_platform": "mattermost",
        "language": "pt_BR",
        "schedules": [{"weekday": 0, "time": "09:30"}],
        "participants": [{"member_id": ana["id"]}],
    }
    d = client.post("/api/daily-assistants", json=body).json()
    assert d["webhook_platform"] == "mattermost"
    text = client.post(f"/api/daily-assistants/{d['id']}/send-test").json()["text"]
    assert "@ana" in text and "Daily em" in text
    assert hook.called

    no_url = {**body, "webhook_url": None}
    assert client.post("/api/daily-assistants", json=no_url).status_code == 422


def test_review_webhook_answers_200_even_if_chat_fails(client):
    chat = client.post(
        "/api/chat-connections",
        json={
            "name": "MM",
            "provider": "mattermost",
            "base_url": "https://mm.invalid",
            "bot_token": "x",
        },
    ).json()
    gl = client.post("/api/gitlab-connections", json={"name": "G", "access_token": "t"}).json()
    creds = client.post(
        "/api/review-assistants",
        json={
            "name": "R",
            "chat_connection_id": chat["id"],
            "channel_id": "C",
            "gitlab_connection_id": gl["id"],
        },
    ).json()
    # no thread linked yet -> nothing to do, but the call path must not error
    event = {
        "object_kind": "merge_request",
        "project": {"path_with_namespace": "g/app"},
        "object_attributes": {"iid": 1, "action": "open"},
    }
    r = client.post(
        urlparse(creds["webhook_url"]).path,
        json=event,
        headers={"X-Gitlab-Token": creds["webhook_token"]},
    )
    assert r.status_code == 200 and r.json() == {"threads": 0}
