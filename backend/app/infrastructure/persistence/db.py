from collections.abc import Iterator

from sqlmodel import Session, create_engine

from ..config import get_settings

_settings = get_settings()
_connect_args = {"check_same_thread": False} if _settings.database_url.startswith("sqlite") else {}
engine = create_engine(_settings.database_url, connect_args=_connect_args)


def init_db() -> None:
    """Create or upgrade the schema with Alembic migrations."""
    from .migrate import upgrade_to_head

    upgrade_to_head(engine)


def get_session() -> Iterator[Session]:
    with Session(engine) as session:
        yield session
