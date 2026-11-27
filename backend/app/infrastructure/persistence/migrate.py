"""Run Alembic migrations programmatically (on app startup and from tests)."""

import logging
from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import Engine, inspect

log = logging.getLogger(__name__)

MIGRATIONS_DIR = Path(__file__).parent / "migrations"
# Schema of v0.1, created with SQLModel.create_all before migrations existed.
BASELINE_REVISION = "0001"


def _config(engine: Engine) -> Config:
    cfg = Config()
    cfg.set_main_option("script_location", str(MIGRATIONS_DIR))
    cfg.set_main_option("sqlalchemy.url", engine.url.render_as_string(hide_password=False))
    return cfg


def upgrade_to_head(engine: Engine) -> None:
    cfg = _config(engine)
    with engine.begin() as conn:
        cfg.attributes["connection"] = conn
        tables = set(inspect(conn).get_table_names())
        if tables and "alembic_version" not in tables:
            # Database created by v0.1 (create_all): mark it as the baseline, then upgrade.
            log.info("existing database without migrations: stamping %s", BASELINE_REVISION)
            command.stamp(cfg, BASELINE_REVISION)
        command.upgrade(cfg, "head")
