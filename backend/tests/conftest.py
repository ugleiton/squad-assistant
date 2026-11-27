import os

os.environ.setdefault("SQUAD_DATABASE_URL", "sqlite://")
os.environ.setdefault("SQUAD_SCHEDULER_ENABLED", "false")

import pytest  # noqa: E402
from sqlalchemy.pool import StaticPool  # noqa: E402
from sqlmodel import Session, SQLModel, create_engine  # noqa: E402

from app.infrastructure.persistence import models  # noqa: E402,F401


@pytest.fixture
def engine():
    eng = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    SQLModel.metadata.create_all(eng)
    return eng


@pytest.fixture
def session(engine):
    with Session(engine) as s:
        yield s
