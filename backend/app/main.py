"""Composition root: builds the FastAPI app, wires routers and starts the scheduler."""

import logging
from contextlib import asynccontextmanager
from pathlib import Path

import httpx
from fastapi import APIRouter, Depends, FastAPI, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from . import __version__
from .domain.enums import DEFAULT_REVIEW_EMOJIS, DEFAULT_REVIEW_FEATURES
from .infrastructure.chat.slack import SlackError as UpstreamError
from .infrastructure.config import get_settings
from .infrastructure.i18n import available_languages
from .infrastructure.persistence.db import init_db
from .interfaces.api import connections, daily, review, squads, webhooks
from .interfaces.api.deps import require_admin

logging.basicConfig(level=logging.INFO)
STATIC_DIR = Path(__file__).parent / "static"


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    scheduler = None
    if get_settings().scheduler_enabled:
        from .infrastructure.scheduler import build_scheduler

        scheduler = build_scheduler()
        scheduler.start()
    yield
    if scheduler:
        scheduler.shutdown(wait=False)


app = FastAPI(title="Squad Assistant", version=__version__, lifespan=lifespan)


@app.exception_handler(httpx.HTTPError)
@app.exception_handler(UpstreamError)
async def upstream_error(request: Request, exc: Exception):
    """Errors from Slack, Mattermost or GitLab are shown to the admin instead of a bare 500."""
    return JSONResponse(status_code=502, content={"detail": f"{type(exc).__name__}: {exc}"})


@app.exception_handler(LookupError)
async def missing_config(request: Request, exc: LookupError):
    return JSONResponse(status_code=422, content={"detail": str(exc)})


api = APIRouter(prefix="/api", dependencies=[Depends(require_admin)])
for r in (connections.router, squads.router, review.router, daily.router):
    api.include_router(r)


@api.get("/meta", tags=["meta"])
def meta():
    return {
        "version": __version__,
        "languages": available_languages(),
        "default_language": get_settings().default_language,
        "review_emojis": DEFAULT_REVIEW_EMOJIS,
        "review_features": DEFAULT_REVIEW_FEATURES,
    }


app.include_router(api)
app.include_router(webhooks.router)


@app.get("/healthz", include_in_schema=False)
def healthz():
    return {"ok": True}


if STATIC_DIR.exists():  # built React app (see Dockerfile)
    app.mount("/assets", StaticFiles(directory=STATIC_DIR / "assets"), name="assets")

    @app.get("/{path:path}", include_in_schema=False)
    def spa(path: str):
        file = (STATIC_DIR / path).resolve()
        inside = file.is_relative_to(STATIC_DIR.resolve())
        return FileResponse(file if inside and file.is_file() else STATIC_DIR / "index.html")
