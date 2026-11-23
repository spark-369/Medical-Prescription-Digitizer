"""Authentication endpoints: register, login, refresh, logout, me.

Token transport (per architecture spec):
* Access token  -> returned in the JSON body, sent as ``Authorization: Bearer``.
* Refresh token -> also set as an httpOnly cookie and rotated on refresh;
  rotated refresh tokens are blacklisted in Redis (reuse detection).
"""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Response
from fastapi.params import Cookie
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer, OAuth2PasswordRequestForm

from app.api.deps import DbSession, RedisClient, get_current_user
from app.core.config import get_settings
from app.core.errors import CredentialsError
from app.core.redis import add_jti_to_blacklist, is_jti_blacklisted
from app.core.security import (
    ACCESS_TOKEN_TYPE,
    REFRESH_TOKEN_TYPE,
    create_access_token,
    create_refresh_token,
    decode_token,
)
from app.models.user import User
from app.schemas.auth import MessageResponse, RefreshRequest, TokenPair, UserCreate, UserOut
from app.services.user_service import authenticate, create_user, get_by_id

router = APIRouter(prefix="/auth", tags=["auth"])

REFRESH_COOKIE = "mpd.refresh_token"
bearer_scheme = HTTPBearer(auto_error=False)


def _set_refresh_cookie(response: Response, token: str) -> None:
    settings = get_settings()
    response.set_cookie(
        key=REFRESH_COOKIE,
        value=token,
        httponly=True,
        secure=not settings.debug,
        samesite="lax",
        path="/",
        max_age=settings.refresh_token_expire_days * 24 * 60 * 60,
    )


@router.post("/register", response_model=UserOut, status_code=201)
async def register(payload: UserCreate, db: DbSession) -> User:
    """Open registration for dev; the first account becomes an admin."""
    user = await create_user(
        db, email=payload.email, password=payload.password, full_name=payload.full_name
    )
    await db.commit()  # commit before returning so follow-up logins see the row
    return user


@router.post("/login", response_model=TokenPair)
async def login(
    response: Response,
    form: Annotated[OAuth2PasswordRequestForm, Depends()],
    db: DbSession,
) -> TokenPair:
    user = await authenticate(db, email=form.username, password=form.password)
    access_token, _, _ = create_access_token(str(user.id), user.role)
    refresh_token, _, _ = create_refresh_token(str(user.id))
    _set_refresh_cookie(response, refresh_token)
    settings = get_settings()
    return TokenPair(
        access_token=access_token,
        refresh_token=refresh_token,
        expires_in=settings.access_token_expire_minutes * 60,
    )


@router.post("/refresh", response_model=TokenPair)
async def refresh(
    response: Response,
    db: DbSession,
    redis: RedisClient,
    body: RefreshRequest | None = None,
    refresh_cookie: Annotated[str | None, Cookie(alias=REFRESH_COOKIE)] = None,
) -> TokenPair:
    """Rotate tokens. Accepts the refresh token via cookie or JSON body."""
    token = (body.refresh_token if body else None) or refresh_cookie
    if not token:
        raise CredentialsError("Missing refresh token")

    payload = decode_token(token, REFRESH_TOKEN_TYPE)
    if await is_jti_blacklisted(redis, payload["jti"]):
        raise CredentialsError("Refresh token has already been used")

    try:
        user_id = uuid.UUID(str(payload["sub"]))
    except ValueError as exc:
        raise CredentialsError("Invalid token subject") from exc
    user = await get_by_id(db, user_id)
    if user is None or not user.is_active:
        raise CredentialsError("User not found or inactive")

    # Rotation: the presented refresh token may never be used again.
    await add_jti_to_blacklist(redis, payload["jti"], expires_at=payload["exp"])

    access_token, _, _ = create_access_token(str(user.id), user.role)
    new_refresh, _, _ = create_refresh_token(str(user.id))
    _set_refresh_cookie(response, new_refresh)
    settings = get_settings()
    return TokenPair(
        access_token=access_token,
        refresh_token=new_refresh,
        expires_in=settings.access_token_expire_minutes * 60,
    )


@router.post("/logout", response_model=MessageResponse)
async def logout(
    response: Response,
    redis: RedisClient,
    user: Annotated[User, Depends(get_current_user)],
    credentials: Annotated[
        HTTPAuthorizationCredentials | None, Depends(bearer_scheme)
    ] = None,
    refresh_cookie: Annotated[str | None, Cookie(alias=REFRESH_COOKIE)] = None,
) -> MessageResponse:
    """Blacklist the presented access/refresh tokens and clear the cookie."""
    if credentials is not None:
        try:
            payload = decode_token(credentials.credentials, ACCESS_TOKEN_TYPE)
            await add_jti_to_blacklist(redis, payload["jti"], expires_at=payload["exp"])
        except CredentialsError:
            pass
    if refresh_cookie:
        try:
            payload = decode_token(refresh_cookie, REFRESH_TOKEN_TYPE)
            await add_jti_to_blacklist(redis, payload["jti"], expires_at=payload["exp"])
        except CredentialsError:
            pass
    response.delete_cookie(key=REFRESH_COOKIE, path="/")
    return MessageResponse(message="Logged out")


@router.get("/me", response_model=UserOut)
async def me(user: Annotated[User, Depends(get_current_user)]) -> User:
    return user
