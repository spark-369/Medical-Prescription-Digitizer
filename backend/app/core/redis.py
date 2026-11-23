"""Redis connectivity.

Two clients are provided:

* an **async** client used by the FastAPI app (JWT blacklist, SSE pub/sub),
* a **sync** client used by Celery workers to publish progress events.

Blacklisted JWT ids are stored with a TTL equal to the token's remaining
lifetime so the blacklist self-cleans.
"""

from __future__ import annotations

import json
import time
from typing import Any

import redis as redis_sync
from redis.asyncio import Redis as AsyncRedis

from app.core.config import get_settings

_async_client: AsyncRedis | None = None
_sync_client: redis_sync.Redis | None = None

BLACKLIST_PREFIX = "bl:jti:"


def get_redis() -> AsyncRedis:
    """Return the process-wide async Redis client (created lazily)."""
    global _async_client
    if _async_client is None:
        _async_client = AsyncRedis.from_url(
            get_settings().redis_url, decode_responses=True
        )
    return _async_client


async def get_redis_dep() -> AsyncRedis:
    """FastAPI dependency wrapper around :func:`get_redis` (overridable in tests)."""
    return get_redis()


def get_sync_redis() -> redis_sync.Redis:
    """Return the process-wide sync Redis client (created lazily)."""
    global _sync_client
    if _sync_client is None:
        _sync_client = redis_sync.from_url(
            get_settings().redis_url, decode_responses=True
        )
    return _sync_client


def event_channel(prescription_id: str) -> str:
    """Redis pub/sub channel carrying processing events for a prescription."""
    return f"presc:{prescription_id}:events"


def insights_event_channel(prescription_id: str) -> str:
    """Redis pub/sub channel carrying AI-insight generation events."""
    return f"presc:{prescription_id}:insights:events"


async def add_jti_to_blacklist(
    redis: AsyncRedis,
    jti: str,
    *,
    expires_at: float | None = None,
    ttl_seconds: int | None = None,
) -> None:
    if ttl_seconds is None:
        ttl_seconds = (
            max(int(expires_at - time.time()), 1) if expires_at is not None else 3600
        )
    await redis.set(BLACKLIST_PREFIX + jti, "1", ex=ttl_seconds)


async def is_jti_blacklisted(redis: AsyncRedis, jti: str) -> bool:
    return await redis.exists(BLACKLIST_PREFIX + jti) == 1


def publish_event(channel: str, payload: dict[str, Any]) -> None:
    """Publish a JSON event on a channel (sync — used from Celery workers)."""
    get_sync_redis().publish(channel, json.dumps(payload))
