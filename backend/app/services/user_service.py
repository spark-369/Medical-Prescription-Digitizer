"""User persistence and authentication helpers."""

from __future__ import annotations

import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import ConflictError, CredentialsError
from app.core.security import hash_password, verify_password
from app.models.enums import Role
from app.models.user import User


async def get_by_email(db: AsyncSession, email: str) -> User | None:
    return await db.scalar(select(User).where(User.email == email.lower()))


async def get_by_id(db: AsyncSession, user_id: uuid.UUID) -> User | None:
    return await db.get(User, user_id)


async def create_user(
    db: AsyncSession,
    *,
    email: str,
    password: str,
    full_name: str,
    role: Role | None = None,
) -> User:
    """Create a user. The very first account becomes an admin."""
    if await get_by_email(db, email):
        raise ConflictError("Email is already registered")
    if role is None:
        total_users = await db.scalar(select(func.count()).select_from(User))
        role = Role.ADMIN if not total_users else Role.STAFF
    user = User(
        email=email.lower(),
        hashed_password=hash_password(password),
        full_name=full_name,
        role=role,
    )
    db.add(user)
    await db.flush()
    await db.refresh(user)
    return user


async def authenticate(db: AsyncSession, *, email: str, password: str) -> User:
    user = await get_by_email(db, email)
    if user is None or not user.is_active or not verify_password(
        password, user.hashed_password
    ):
        raise CredentialsError("Incorrect email or password")
    return user
