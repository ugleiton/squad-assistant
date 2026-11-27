from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from sqlalchemy import create_engine, inspect, text
from sqlmodel import SQLModel

from app.infrastructure.persistence import models  # noqa: F401
from app.infrastructure.persistence.migrate import upgrade_to_head


def _engine(tmp_path):
    return create_engine(f"sqlite:///{tmp_path / 'db.sqlite'}")


def test_fresh_database_matches_models(tmp_path):
    engine = _engine(tmp_path)
    upgrade_to_head(engine)
    with engine.connect() as conn:
        diff = compare_metadata(MigrationContext.configure(conn), SQLModel.metadata)
    assert diff == []


def test_upgrade_is_idempotent(tmp_path):
    engine = _engine(tmp_path)
    upgrade_to_head(engine)
    upgrade_to_head(engine)
    with engine.connect() as conn:
        assert conn.execute(text("select version_num from alembic_version")).scalar() == "0002"


def test_legacy_create_all_database_is_stamped_and_upgraded(tmp_path):
    """v0.1 created tables with create_all and had no alembic_version table."""
    engine = _engine(tmp_path)
    upgrade_to_head(engine)
    with engine.begin() as conn:
        conn.execute(text("drop table alembic_version"))
        conn.execute(text("alter table dailyassistant drop column webhook_platform"))
        conn.execute(text("insert into squad (name) values ('kept')"))

    upgrade_to_head(engine)

    with engine.connect() as conn:
        cols = {c["name"] for c in inspect(conn).get_columns("dailyassistant")}
        assert "webhook_platform" in cols
        assert conn.execute(text("select name from squad")).scalar() == "kept"
