"""Database engine, session factory, and the FastAPI session dependency.

The engine is built lazily from ``DATABASE_URL`` so the API can still import and
answer ``/health`` without a database configured; anything that touches the DB
calls ``get_db`` and fails clearly if it isn't set.
"""

from __future__ import annotations

from collections.abc import Iterator
from functools import lru_cache

from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from ..core.config import get_settings


class Base(DeclarativeBase):
    """Declarative base; ``Base.metadata`` is what Alembic autogenerates from."""


@lru_cache(maxsize=1)
def _engine() -> Engine:
    return create_engine(get_settings().require_database_url(), pool_pre_ping=True)


@lru_cache(maxsize=1)
def _session_factory() -> sessionmaker[Session]:
    return sessionmaker(bind=_engine(), autoflush=False, expire_on_commit=False)


def get_db() -> Iterator[Session]:
    """FastAPI dependency: yields a session and always closes it."""
    db = _session_factory()()
    try:
        yield db
    finally:
        db.close()
