"""Liveness/readiness endpoints."""

from __future__ import annotations

from fastapi import APIRouter
from sqlalchemy import text

from app.api.deps import DbSession, RedisClient
from app.core.config import get_settings
from app.services.inference import check_ollama_health

router = APIRouter(tags=["health"])


@router.get("/health")
async def health() -> dict:
    settings = get_settings()
    return {
        "status": "ok",
        "app": settings.app_name,
        "version": settings.app_version,
        "environment": settings.environment,
    }


@router.get("/health/detailed")
async def health_detailed(db: DbSession, redis: RedisClient) -> dict:
    db_ok = False
    try:
        await db.execute(text("SELECT 1"))
        db_ok = True
    except Exception:  # pragma: no cover - depends on live DB
        pass

    redis_ok = False
    try:
        redis_ok = bool(await redis.ping())
    except Exception:  # pragma: no cover - depends on live Redis
        pass

    ollama_ok = await check_ollama_health()
    components = {"database": db_ok, "redis": redis_ok, "ollama": ollama_ok}
    return {
        "status": "ok" if all(components.values()) else "degraded",
        "components": components,
    }
