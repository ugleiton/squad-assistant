# CLAUDE.md

Guidance for Claude Code (and other AI agents) working in this repository.

## What this is

Squad Assistant: an open source, self-hosted bot for squads on Slack and Mattermost.

- **Review assistants** watch a review channel for GitLab merge request links, mark each thread
  with a status emoji, mention the author's squad, and post pipeline and merge updates. GitLab
  calls `/webhooks/gitlab/{assistant_id}` with a per-assistant secret token.
- **Daily assistants** send a reminder before each stand-up (per weekday schedule, time zone,
  facilitator rotation by day or week), via the bot or an incoming webhook.

Many assistants of each kind can exist, each with its own settings stored in the database.

## Stack

- Backend: Python 3.11+, FastAPI, SQLModel (SQLAlchemy 2), APScheduler (in-process), httpx.
- Database: SQLite by default; PostgreSQL via `SQUAD_DATABASE_URL=postgresql+psycopg://...`.
  Everything must work on both. Use portable types (`JSON` columns, no Postgres-only features).
- Frontend: React 19 + Vite + TypeScript, react-i18next. Built into `backend/app/static` in the
  Docker image and served by FastAPI.
- Deploy: one Docker image (API + UI + scheduler), `docker-compose.yml` with optional Postgres.

## Layout

```
backend/
  app/
    main.py            FastAPI app, routers, SPA serving, scheduler lifespan
    config.py          Settings (env prefix SQUAD_)
    db.py              engine, init_db (create_all), get_session
    models.py          all tables + enums + default emojis/features
    security.py        webhook token generation/hash, Fernet encryption of secrets
    i18n.py            t(lang, key, **params) for bot messages
    locales/*.json     bot message catalogs (en, pt_BR)
    chat/              ChatProvider interface + slack.py, mattermost.py, webhook.py, factory.py
    gitlab/            REST client (MR status, approvals, discussions) and MR link parsing
    review/            state.py (pure state rules), service.py (scan, reactions, webhook events)
    daily/             rotation.py (pure), service.py (due check, reminder rendering, tick)
    scheduler.py       one-minute jobs fanning out to due assistants
    api/               routers: connections, squads, review, daily, webhooks; schemas.py; deps.py
  tests/               pytest; FakeChat in conftest.py, no network calls
frontend/
  src/App.tsx          tabs + language switcher
  src/pages/           Connections, Squads, ReviewAssistants, DailyAssistants
  src/locales/         en.json, pt-BR.json
  src/api.ts           fetch wrapper and types
.github/workflows/     ci.yml (lint, tests, builds), docker-publish.yml (Docker Hub)
```

## Commands

```bash
# backend (from backend/)
pip install -e ".[dev]"
uvicorn app.main:app --reload        # http://localhost:8000/docs
pytest -q
ruff check app tests && ruff format app tests

# frontend (from frontend/)
npm install
npm run dev                          # http://localhost:5173, proxies /api and /webhooks to :8000
npm run build                        # type check + build

# whole app
docker compose up -d                 # SQLite
docker compose --profile postgres up -d
```

CI (`ci.yml`) runs `ruff check`, `ruff format --check`, `pytest`, `npm run build` and
`docker build`. Keep all of them green.

## Conventions

- **i18n is required.** Never hardcode user-facing text.
  - Bot messages: add the key to every file in `backend/app/locales/` (at least `en` and
    `pt_BR`) and use `t(assistant.language, "key", ...)`.
  - UI: add the key to `frontend/src/locales/en.json` and `pt-BR.json`.
- **Secrets** (bot tokens, GitLab tokens, incoming webhook URLs) are stored with
  `security.encrypt()` and never returned by the API; responses expose `has_token`-style flags.
  The GitLab webhook token is only stored as a SHA-256 hash and shown once on creation/regeneration.
- **Chat platforms**: new behavior goes through the `ChatProvider` interface and must be
  implemented for both Slack and Mattermost. Emoji names are passed without colons. The
  incoming-webhook provider can only post messages (fine for dailies, not for reviews).
- **Business rules stay pure and tested**: review state rules live in `review/state.py`, rotation
  in `daily/rotation.py`. Change the tests alongside the rules.
- **Datetimes** are timezone-aware UTC in the database (`models.utcnow()`); daily schedules are
  wall-clock times interpreted in the assistant's `timezone`.
- **Schema changes**: tables are created with `create_all` for now (no Alembic yet). Adding
  Alembic migrations is on the roadmap; until then, prefer additive, nullable/defaulted columns.
- Tests must not hit the network: use `FakeChat` / fake GitLab clients or `respx`.
- Code style: ruff (line length 100). Python type hints everywhere.
- Docs: README.md (English) and README.pt-BR.md. Contributions may be in English or Portuguese.

## Review states (default emojis)

| State | Rule | Emoji |
|---|---|---|
| awaiting_review | no comments and no approval | `hourglass_flowing_sand` |
| in_review | comments exist and discussions are still open | `mag` |
| resolved | MR approved or every resolvable discussion resolved | `white_check_mark` |
| merged | MR merged | `rocket` |
| closed | MR closed without merge | `heavy_check_mark` (gray check) |
