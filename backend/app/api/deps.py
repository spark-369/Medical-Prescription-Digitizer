"""FastAPI dependencies: DB session, Redis, current user, and RBAC guards."""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator
from typing import Annotated

from fastapi import Depends, Header, Query
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import CredentialsError, PermissionDeniedError
from app.core.redis import get_redis_dep, is_jti_blacklisted
from app.core.security import ACCESS_TOKEN_TYPE, decode_token
from app.db.session import get_db
from app.models.enums import Role
from app.models.user import User
from app.services.user_service import get_by_id


async def get_db_dep() -> AsyncIterator[AsyncSession]:  # re-exported alias
    async for session in get_db():
        yield session


DbSession = Annotated[AsyncSession, Depends(get_db)]
RedisClient = Annotated[Redis, Depends(get_redis_dep)]


async def get_current_user(
    db: DbSession,
    redis: RedisClient,
    authorization: Annotated[str | None, Header()] = None,
    access_token: Annotated[str | None, Query()] = None,
) -> User:
    """Resolve the caller from a Bearer header, or ``?access_token=``.

    The query-parameter fallback exists for ``EventSource`` (SSE), which
    cannot set custom headers. Every token's ``jti`` is checked against the
    Redis blacklist so logout/rotation take effect immediately.
    """
    token: str | None = None
    if authorization and authorization.lower().startswith("bearer "):
        token = authorization[7:].strip()
    token = token or access_token
    if not token:
        raise CredentialsError("Not authenticated")

    payload = decode_token(token, ACCESS_TOKEN_TYPE)
    if await is_jti_blacklisted(redis, payload["jti"]):
        raise CredentialsError("Token has been revoked")
    try:
        user_id = uuid.UUID(str(payload["sub"]))
    except ValueError as exc:
        raise CredentialsError("Invalid token subject") from exc

    user = await get_by_id(db, user_id)
    if user is None or not user.is_active:
        raise CredentialsError("User not found or inactive")
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]


def require_roles(*roles: Role):
    """Dependency factory enforcing role-based access control."""

    async def checker(user: CurrentUser) -> User:
        if user.role not in roles:
            raise PermissionDeniedError("Insufficient role for this operation")
        return user

    return checker


AdminUser = Annotated[User, Depends(require_roles(Role.ADMIN))]
