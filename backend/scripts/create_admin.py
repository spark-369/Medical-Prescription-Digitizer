"""Bootstrap an admin user.

Usage:
    python -m scripts.create_admin --email admin@example.com --password secret123
    (omit --password to be prompted securely)
"""

from __future__ import annotations

import argparse
import asyncio
import getpass

from sqlalchemy import select

from app.core.security import hash_password
from app.db.session import AsyncSessionLocal
from app.models.user import User


async def create_admin(email: str, password: str, full_name: str) -> None:
    async with AsyncSessionLocal() as session:
        existing = await session.scalar(select(User).where(User.email == email.lower()))
        if existing is not None:
            print(f"User {email} already exists (role={existing.role})")
            return
        user = User(
            email=email.lower(),
            hashed_password=hash_password(password),
            full_name=full_name,
            role="admin",
        )
        session.add(user)
        await session.commit()
        print(f"Admin created: {email}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Create an admin user")
    parser.add_argument("--email", required=True)
    parser.add_argument("--password", help="Omit to be prompted securely")
    parser.add_argument("--full-name", default="Administrator")
    args = parser.parse_args()

    password = args.password or getpass.getpass("Password: ")
    if len(password) < 8:
        raise SystemExit("Password must be at least 8 characters")
    asyncio.run(create_admin(args.email, password, args.full_name))


if __name__ == "__main__":
    main()
