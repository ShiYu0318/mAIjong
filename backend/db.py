"""Database engine, session factory and FastAPI dependency."""

from __future__ import annotations

from collections.abc import Iterator
from functools import lru_cache
from pathlib import Path

from sqlalchemy import Engine, create_engine, event
from sqlalchemy.orm import Session, sessionmaker

from backend.config import get_settings


@lru_cache(maxsize=1)
def get_engine() -> Engine:
    url = get_settings().database_url
    kwargs: dict[str, object] = {"future": True}
    if url.startswith("sqlite"):
        path = url.removeprefix("sqlite:///")
        if path and path != ":memory:":
            Path(path).parent.mkdir(parents=True, exist_ok=True)
        kwargs["connect_args"] = {"check_same_thread": False}
    engine = create_engine(url, **kwargs)
    if url.startswith("sqlite"):

        @event.listens_for(engine, "connect")
        def _fk_on(dbapi_conn, _record):  # type: ignore[no-untyped-def]
            dbapi_conn.execute("PRAGMA foreign_keys=ON")

    return engine


@lru_cache(maxsize=1)
def session_factory() -> sessionmaker[Session]:
    return sessionmaker(bind=get_engine(), expire_on_commit=False)


def get_session() -> Iterator[Session]:
    with session_factory()() as session:
        yield session


def init_db() -> None:
    """Create tables directly (tests / quick local runs). Production uses Alembic."""
    from backend import models

    models.Base.metadata.create_all(get_engine())
