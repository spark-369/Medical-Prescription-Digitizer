"""Database engines and session factories.

* ``database_url`` (async) powers the FastAPI request cycle (asyncpg).
* ``database_url_sync`` powers Celery workers (psycopg3).
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any

from sqlalchemy import create_engine
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import sessionmaker

from app.core.config import get_settings


def create_async_engine_and_factory() -> tuple[AsyncEngine, async_sessionmaker[AsyncSession]]:
    settings = get_settings()
    engine = create_async_engine(settings.database_url, echo=False, pool_pre_ping=True)
    factory = async_sessionmaker(engine, expire_on_commit=False, autoflush=False)
    return engine, factory


async_engine, AsyncSessionLocal = create_async_engine_and_factory()


async def get_db() -> AsyncIterator[AsyncSession]:
    """FastAPI dependency yielding an async database session."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


_sync_factory: sessionmaker[Any] | None = None
_sync_engine = None


def get_sync_session_factory() -> sessionmaker[Any]:
    """Cached session factory for worker processes (created lazily)."""
    global _sync_factory, _sync_engine
    if _sync_factory is None:
        settings = get_settings()
        _sync_engine = create_engine(
            settings.database_url_sync,
            echo=False,
            pool_pre_ping=True,
            connect_args={"timeout": 15} if settings.database_url_sync.startswith("sqlite") else {},
        )
        _sync_factory = sessionmaker(bind=_sync_engine, expire_on_commit=False, autoflush=False)
    return _sync_factory


def reset_sync_session_factory() -> None:
    """Dispose the cached sync engine (used between test runs)."""
    global _sync_factory, _sync_engine
    if _sync_engine is not None:
        _sync_engine.dispose()
    _sync_engine = None
    _sync_factory = None
    _sync_factory = None
