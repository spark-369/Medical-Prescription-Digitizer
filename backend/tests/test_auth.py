"""Authentication flow tests: register, login, me, logout, refresh rotation."""

from __future__ import annotations

from httpx import AsyncClient
from jose import jwt

from app.core.config import get_settings
from tests.conftest import bearer, login, register

SETTINGS = get_settings()


def _decode(token: str) -> dict:
    return jwt.decode(token, SETTINGS.secret_key, algorithms=[SETTINGS.jwt_algorithm])


async def test_register_creates_first_user_as_admin(client: AsyncClient):
    user = await register(client)
    assert user["role"] == "admin"
    assert user["email"] == "doctor@example.com"


async def test_register_duplicate_email_conflict(client: AsyncClient):
    await register(client)
    response = await client.post(
        "/api/v1/auth/register",
        json={
            "email": "doctor@example.com",
            "password": "anothersecret1",
            "full_name": "Impostor",
        },
    )
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "conflict"


async def test_register_weak_password_rejected(client: AsyncClient):
    response = await client.post(
        "/api/v1/auth/register",
        json={"email": "x@example.com", "password": "short", "full_name": "X"},
    )
    assert response.status_code == 422


async def test_login_returns_tokens_and_refresh_cookie(client: AsyncClient):
    await register(client)
    response = await client.post(
        "/api/v1/auth/login",
        data={"username": "doctor@example.com", "password": "supersecret123"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["token_type"] == "bearer"
    assert body["expires_in"] == SETTINGS.access_token_expire_minutes * 60
    assert _decode(body["access_token"])["type"] == "access"
    assert _decode(body["refresh_token"])["type"] == "refresh"
    assert "mpd.refresh_token" in response.cookies


async def test_login_wrong_password(client: AsyncClient):
    await register(client)
    response = await client.post(
        "/api/v1/auth/login",
        data={"username": "doctor@example.com", "password": "wrongpassword"},
    )
    assert response.status_code == 401


async def test_me_with_bearer_token(client: AsyncClient):
    await register(client)
    tokens = await login(client)
    response = await client.get("/api/v1/auth/me", headers=bearer(tokens["access_token"]))
    assert response.status_code == 200
    assert response.json()["email"] == "doctor@example.com"


async def test_me_without_token_unauthorized(client: AsyncClient):
    response = await client.get("/api/v1/auth/me")
    assert response.status_code == 401


async def test_me_with_tampered_token(client: AsyncClient):
    await register(client)
    tokens = await login(client)
    tampered = tokens["access_token"][:-4] + "0000"
    response = await client.get("/api/v1/auth/me", headers=bearer(tampered))
    assert response.status_code == 401


async def test_logout_blacklists_access_token(client: AsyncClient):
    await register(client)
    tokens = await login(client)
    headers = bearer(tokens["access_token"])

    response = await client.post("/api/v1/auth/logout", headers=headers)
    assert response.status_code == 200

    after = await client.get("/api/v1/auth/me", headers=headers)
    assert after.status_code == 401


async def test_refresh_rotates_and_rejects_reuse(client: AsyncClient):
    await register(client)
    tokens = await login(client)

    first = await client.post(
        "/api/v1/auth/refresh", json={"refresh_token": tokens["refresh_token"]}
    )
    assert first.status_code == 200
    rotated = first.json()
    assert rotated["refresh_token"] != tokens["refresh_token"]

    # The old refresh token must now be rejected (single-use rotation).
    reuse = await client.post(
        "/api/v1/auth/refresh", json={"refresh_token": tokens["refresh_token"]}
    )
    assert reuse.status_code == 401

    # The rotated token works again.
    second = await client.post(
        "/api/v1/auth/refresh", json={"refresh_token": rotated["refresh_token"]}
    )
    assert second.status_code == 200


async def test_refresh_via_cookie(client: AsyncClient):
    await register(client)
    await login(client)  # sets the httpOnly cookie on the client jar

    response = await client.post("/api/v1/auth/refresh")
    assert response.status_code == 200
    assert "access_token" in response.json()
