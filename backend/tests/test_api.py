from fastapi.testclient import TestClient

from app.db import get_session
from app.main import app


def test_review_assistant_webhook_token_flow(engine):
    from sqlmodel import Session

    def _s():
        with Session(engine) as s:
            yield s

    app.dependency_overrides[get_session] = _s
    with TestClient(app) as c:
        chat = c.post(
            "/api/chat-connections",
            json={"name": "Slack", "provider": "slack", "bot_token": "xoxb-1"},
        ).json()
        assert chat["has_token"] and "bot_token" not in chat
        gl = c.post("/api/gitlab-connections", json={"name": "GL", "access_token": "glpat"}).json()
        creds = c.post(
            "/api/review-assistants",
            json={
                "name": "R",
                "chat_connection_id": chat["id"],
                "channel_id": "C1",
                "gitlab_connection_id": gl["id"],
            },
        ).json()
        assert creds["webhook_url"].endswith("/webhooks/gitlab/1")
        token = creds["webhook_token"]

        ping = {"object_kind": "push", "project": {"path_with_namespace": "g/app"}}
        assert c.post("/webhooks/gitlab/1", json=ping).status_code == 401
        assert (
            c.post("/webhooks/gitlab/1", json=ping, headers={"X-Gitlab-Token": "no"}).status_code
            == 401
        )
        r = c.post("/webhooks/gitlab/1", json=ping, headers={"X-Gitlab-Token": token})
        assert r.status_code == 200 and r.json() == {"threads": 0}

        assert c.get("/api/meta").json()["languages"] == ["en", "pt_BR"]
    app.dependency_overrides.clear()


def test_daily_assistant_crud(engine):
    from sqlmodel import Session

    def _s():
        with Session(engine) as s:
            yield s

    app.dependency_overrides[get_session] = _s
    with TestClient(app) as c:
        m = c.post("/api/members", json={"name": "Ana", "chat_user_id": "U1"}).json()
        body = {
            "name": "Daily",
            "delivery": "webhook",
            "webhook_url": "https://hooks.example/x",
            "timezone": "America/Sao_Paulo",
            "rotation_mode": "weekly",
            "schedules": [{"weekday": 0, "time": "09:30"}, {"weekday": 4, "time": "10:00"}],
            "participants": [{"member_id": m["id"]}],
        }
        d = c.post("/api/daily-assistants", json=body).json()
        assert d["has_webhook_url"] and "webhook_url" not in d or d.get("webhook_url") is None
        assert len(d["schedules"]) == 2
        assert (
            c.post("/api/daily-assistants", json={**body, "timezone": "Mars/Base"}).status_code
            == 422
        )
    app.dependency_overrides.clear()
