# Squad Assistant

[Português](README.pt-BR.md) · English

Open source, self-hosted assistant for squads on **Slack** and **Mattermost**.

- **Review assistants** track GitLab merge requests posted in a review channel: they mark each
  thread with a status emoji (awaiting review, in review, resolved/approved, merged, closed),
  mention the author's squad, and post pipeline and merge updates in the thread.
- **Daily assistants** remind the squad before each stand-up, per weekday schedule, with an
  optional facilitator rotation by day or by week. They post with the bot or an incoming webhook.

You can create as many assistants as you need, each with its own settings. The admin UI and the
bot messages are multilingual (English and Brazilian Portuguese to start).

> Status: early development (v0.1). Feedback and contributions are welcome.

## Quick start

```bash
cp .env.example .env        # set SQUAD_PUBLIC_URL, SQUAD_SECRET_KEY, SQUAD_ADMIN_PASSWORD
docker compose up -d        # SQLite, data in the "data" volume
open http://localhost:8000
```

Or use the published image: `docker run -p 8000:8000 --env-file .env -v squad-data:/data <dockerhub-user>/squad-assistant:latest`.

To use PostgreSQL, set `SQUAD_DATABASE_URL=postgresql+psycopg://...` and run
`docker compose --profile postgres up -d`.

## How it works

```
GitLab ──webhook──► FastAPI ◄── Admin UI (React)
                     │  ├─ Review service ─┐
                     │  ├─ Daily service   ├─► Slack / Mattermost
                     │  └─ Scheduler (APScheduler, in-process)
                     └─ SQLite (default) or PostgreSQL
```

### Review assistant

1. Create a Slack or Mattermost **connection** (bot token) and a **GitLab connection**
   (token with `read_api`).
2. Create **members** (chat user id, GitLab username) and group them in **squads**.
3. Create a review assistant: channel, GitLab projects, squads, scan interval, emojis and actions.
   The UI shows a **webhook URL and secret token** once; add them in GitLab under
   *Settings → Webhooks* with the *Merge request*, *Comments* and *Pipeline* events.
4. Every scan interval the bot reads new messages in the channel, finds MR links, and updates
   each open thread:

| State | Rule | Default emoji |
|---|---|---|
| Awaiting review | No comments and no approval | `:hourglass_flowing_sand:` |
| In review | Someone commented and discussions are still open | `:mag:` |
| Resolved / approved | MR approved or every review discussion resolved | `:white_check_mark:` |
| Merged | MR merged | `:rocket:` |
| Closed | MR closed without merge | `:heavy_check_mark:` (gray check) |

### Daily assistant

Pick the weekdays and times, time zone, participants, rotation (none, daily or weekly), how many
minutes before to alert, and the delivery: the bot (real @mentions) or an incoming webhook.

### Required bot permissions

- **Slack**: `channels:history`, `groups:history`, `reactions:write`, `chat:write`. Invite the bot to the channel.
- **Mattermost**: a bot account added to the team and channel.

## Development

```bash
# backend
cd backend
python -m venv .venv && . .venv/bin/activate
pip install -e ".[dev]"
uvicorn app.main:app --reload          # http://localhost:8000/docs
pytest

# frontend (proxies /api to :8000)
cd frontend
npm install
npm run dev                            # http://localhost:5173
```

### Adding a language

- Admin UI: add `frontend/src/locales/<lang>.json` and register it in `frontend/src/i18n.ts`.
- Bot messages: add `backend/app/locales/<lang>.json` with the same keys as `en.json`.

## Docker images

`.github/workflows/docker-publish.yml` builds `linux/amd64` and `linux/arm64` images and pushes
them to Docker Hub: every push to `main` publishes `:main`, and a tag like `v0.1.0` publishes
`:0.1.0`, `:0.1`, `:0` and `:latest`. It reads `DOCKERHUB_USERNAME` and `DOCKERHUB_TOKEN` from the GitHub environment
`GENERAL` (a Docker Hub access token with Read & Write scope).

## Roadmap

- [x] Project skeleton, data model, Slack and Mattermost adapters, GitLab webhook with generated token
- [x] Review state machine, squad mentions, pipeline and merge messages
- [x] Daily reminders with rotation
- [ ] Alembic migrations
- [ ] Skip days off and holidays in the daily rotation
- [ ] Slack/Mattermost slash commands (e.g. `/daily skip`)
- [ ] Helm chart

## License

[Apache License 2.0](LICENSE)
