"""Admin-only user management endpoints."""

from __future__ import annotations

from fastapi import APIRouter
from sqlalchemy import select

from app.api.deps import AdminUser, DbSession
from app.models.user import User
from app.schemas.auth import AdminUserCreate, UserOut
from app.services.user_service import create_user

router = APIRouter(prefix="/users", tags=["users"])


@router.get("", response_model=list[UserOut])
async def list_users(db: DbSession, _admin: AdminUser) -> list[User]:
    return list(await db.scalars(select(User).order_by(User.created_at)))


@router.post("", response_model=UserOut, status_code=201)
async def create_user_by_admin(
    payload: AdminUserCreate, db: DbSession, _admin: AdminUser
) -> User:
    user = await create_user(
        db,
        email=payload.email,
        password=payload.password,
        full_name=payload.full_name,
        role=payload.role,
    )
    await db.commit()
    return user
