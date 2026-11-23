"""Admin user management and RBAC tests."""

from __future__ import annotations

from httpx import AsyncClient

from tests.conftest import bearer, login, register


async def test_first_user_is_admin_and_can_list_users(client: AsyncClient):
    await register(client)  # first user -> admin
    tokens = await login(client)

    response = await client.get("/api/v1/users", headers=bearer(tokens["access_token"]))
    assert response.status_code == 200
    users = response.json()
    assert len(users) == 1
    assert users[0]["role"] == "admin"


async def test_staff_cannot_list_users(client: AsyncClient):
    await register(client)  # admin
    admin_tokens = await login(client)

    created = await client.post(
        "/api/v1/users",
        json={
            "email": "staff@example.com",
            "password": "staffsecret1",
            "full_name": "Staff Member",
            "role": "staff",
        },
        headers=bearer(admin_tokens["access_token"]),
    )
    assert created.status_code == 201
    assert created.json()["role"] == "staff"

    staff_tokens = await login(client, email="staff@example.com", password="staffsecret1")
    response = await client.get(
        "/api/v1/users", headers=bearer(staff_tokens["access_token"])
    )
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "permission_denied"


async def test_non_admin_cannot_create_users(client: AsyncClient):
    await register(client)
    tokens = await login(client)
    response = await client.post(
        "/api/v1/users",
        json={
            "email": "new@example.com",
            "password": "newsecret12",
            "full_name": "New",
        },
        headers=bearer(tokens["access_token"]),
    )
    # The first registered user is admin, so this must succeed; verify and
    # then ensure a plain staff member is rejected.
    assert response.status_code == 201

    staff = await client.post(
        "/api/v1/users",
        json={
            "email": "clerk@example.com",
            "password": "clerksecret1",
            "full_name": "Clerk",
            "role": "staff",
        },
        headers=bearer(tokens["access_token"]),
    )
    assert staff.status_code == 201
    clerk_tokens = await login(client, email="clerk@example.com", password="clerksecret1")
    forbidden = await client.post(
        "/api/v1/users",
        json={"email": "x@example.com", "password": "xsecret123", "full_name": "X"},
        headers=bearer(clerk_tokens["access_token"]),
    )
    assert forbidden.status_code == 403
