import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import APIRouter, Depends, FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from . import __version__
from .api import connections, daily, review, squads, webhooks
from .api.deps import require_admin
from .config import get_settings
from .db import init_db
from .i18n import available_languages
from .models import DEFAULT_REVIEW_EMOJIS, DEFAULT_REVIEW_FEATURES

logging.basicConfig(level=logging.INFO)
STATIC_DIR = Path(__file__).parent / "static"


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    scheduler = None
    if get_settings().scheduler_enabled:
        from .scheduler import build_scheduler

        scheduler = build_scheduler()
        scheduler.start()
    yield
    if scheduler:
        scheduler.shutdown(wait=False)


app = FastAPI(title="Squad Assistant", version=__version__, lifespan=lifespan)

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
