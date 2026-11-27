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

- Backend: Python 3.11+, FastAPI, SQLModel (SQLAlchemy 2), APScheduler (in-process), httpx,
  organized in Clean Architecture layers (see below).
- Database: SQLite by default; PostgreSQL via `SQUAD_DATABASE_URL=postgresql+psycopg://...`.
  Everything must work on both. Use portable types (`JSON` columns, no Postgres-only features).
- Frontend: React 19 + Vite + TypeScript, react-i18next. Built into `backend/app/static` in the
  Docker image and served by FastAPI.
- Deploy: one Docker image (API + UI + scheduler), `docker-compose.yml` with optional Postgres.

## Architecture (Clean Architecture)

The backend is split in four layers. Dependencies point inward only:

```
interfaces  ──►  infrastructure  ──►  application  ──►  domain
(FastAPI)        (DB, Slack, GitLab)   (use cases, ports)  (entities, rules)
```

- **domain**: entities (plain dataclasses), enums, and pure business rules. Standard library only.
- **application**: use cases (`ReviewTracker`, `DailyReminder`) and the **ports** they depend on
  (`ChatProvider`, `GitLabGateway`, `Translator`, `ReviewRepository`, `DailyRepository`).
  Imports only `domain` and the standard library: no FastAPI, SQLModel or httpx.
- **infrastructure**: adapters that implement the ports (SQLModel repositories, Slack/Mattermost/
  webhook clients, GitLab client, i18n catalogs, encryption, config, scheduler) and
  `container.py`, which wires use cases to adapters. Never imports `interfaces`.
- **interfaces**: FastAPI routers and schemas. Business flows (scan, webhook handling, reminders)
  go through use cases via `infrastructure.container`. Configuration CRUD (connections, squads,
  members, assistants) has no business rules and talks to the persistence models directly.
- `app/main.py` is the composition root (app, routers, scheduler lifespan).

`tests/test_architecture.py` enforces these rules; keep it green instead of weakening it.

## Layout

```
backend/
  app/
    main.py                     composition root
    domain/
      entities.py               Member, ReviewAssistant, ReviewThread, DailyAssistant, ...
      enums.py                  ReviewState, RotationMode, DeliveryMode, ChatProviderType, defaults
      review_state.py           compute_state(): review status rules
      mr_links.py               GitLab MR link parsing and project filter
      rotation.py               facilitator rotation (none / daily / weekly)
      daily_schedule.py         due_daily(): when a reminder must be sent
    application/
      ports.py                  ChatProvider, GitLabGateway, Translator, repositories
      review/tracker.py         ReviewTracker: scan channel, refresh threads, GitLab events
      review/webhook_auth.py    webhook token generation, hashing and verification
      daily/reminder.py         DailyReminder: tick, render, send_test
    infrastructure/
      config.py                 Settings (env prefix SQUAD_)
      container.py              builds use cases with their adapters
      persistence/              db.py (engine), models.py (ORM tables), mappers.py, repositories.py
      chat/                     slack.py, mattermost.py, webhook.py, factory.py
      gitlab/client.py          GitLab REST adapter (MR status, approvals, discussions)
      i18n.py, locales/*.json   bot message catalogs (en, pt_BR)
      security.py               Fernet encryption of stored secrets
      scheduler.py              one-minute jobs fanning out to due assistants
    interfaces/api/             routers: connections, squads, review, daily, webhooks; schemas; deps
  tests/
    domain/                     pure rule tests
    application/                use case tests with in-memory fakes (tests/fakes.py)
    infrastructure/             repository tests on in-memory SQLite
    interfaces/                 API tests (TestClient)
    test_architecture.py        dependency rule
frontend/
  src/App.tsx                   tabs + language switcher
  src/pages/                    Connections, Squads, ReviewAssistants, DailyAssistants
  src/locales/                  en.json, pt-BR.json
  src/api.ts                    fetch wrapper and types
.github/workflows/              ci.yml (lint, tests, builds), docker-publish.yml (Docker Hub)
```

## Adding a feature

1. Put the rule in `domain` as a pure function or entity method, with a test in `tests/domain`.
2. If it needs I/O, add or extend a port in `application/ports.py` and use it from a use case;
   test the use case with fakes in `tests/fakes.py`.
3. Implement the port in `infrastructure` (for chat: both Slack and Mattermost) and wire it in
   `infrastructure/container.py`.
4. Expose it in `interfaces/api` if the UI needs it.

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
  - Bot messages: add the key to every file in `backend/app/infrastructure/locales/` (at least `en` and
    `pt_BR`). Use cases receive a `Translator` and call it with `assistant.language`.
  - UI: add the key to `frontend/src/locales/en.json` and `pt-BR.json`.
- **Secrets** (bot tokens, GitLab tokens, incoming webhook URLs) are stored with
  `security.encrypt()` and never returned by the API; responses expose `has_token`-style flags.
  The GitLab webhook token is only stored as a SHA-256 hash and shown once on creation/regeneration.
- **Chat platforms**: new behavior goes through the `ChatProvider` port and must be
  implemented for both Slack and Mattermost. Emoji names are passed without colons. The
  incoming-webhook provider can only post messages (fine for dailies, not for reviews).
- **Business rules stay pure and tested** in `domain/` (`review_state.py`, `rotation.py`,
  `daily_schedule.py`). Change the tests alongside the rules.
- **Datetimes** are timezone-aware UTC in the database (`domain.entities.utcnow()`); daily schedules are
  wall-clock times interpreted in the assistant's `timezone`.
- **Schema changes**: tables are created with `create_all` for now (no Alembic yet). Adding
  Alembic migrations is on the roadmap; until then, prefer additive, nullable/defaulted columns.
- Tests must not hit the network: use the fakes in `tests/fakes.py` or `respx`.
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
