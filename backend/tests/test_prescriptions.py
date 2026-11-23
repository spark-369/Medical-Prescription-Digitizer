"""Prescription REST + SSE end-to-end tests (Celery in eager mode)."""

from __future__ import annotations

from types import SimpleNamespace

from httpx import AsyncClient

from app.core.config import get_settings
from tests.conftest import PNG_BYTES, bearer, login, register, upload_prescription

SETTINGS = get_settings()


async def _register_and_login(client: AsyncClient) -> str:
    await register(client)
    tokens = await login(client)
    return tokens["access_token"]


async def test_upload_processes_end_to_end(client: AsyncClient):
    token = await _register_and_login(client)
    prescription = await upload_prescription(client, token)

    assert prescription.status in {"queued", "processing", "completed"}

    detail = await client.get(
        f"/api/v1/prescriptions/{prescription.id}", headers=bearer(token)
    )
    assert detail.status_code == 200
    body = detail.json()
    assert body["status"] == "completed"
    assert body["patient_name"] == "John Doe"
    assert body["patient_age"] == 42
    assert body["doctor_name"] == "Dr. Sarah Smith"
    assert body["confidence"] == 0.93
    assert body["model_name"] == SETTINGS.ollama_model
    assert len(body["items"]) == 2
    assert body["items"][0]["medication"] == "Amoxicillin"
    assert body["items"][0]["dosage"] == "500 mg"


async def test_upload_requires_authentication(client: AsyncClient):
    response = await client.post(
        "/api/v1/prescriptions",
        files={"file": ("rx.png", b"\x89PNG\r\n\x1a\nabc", "image/png")},
    )
    assert response.status_code == 401


async def test_upload_rejects_disallowed_type(client: AsyncClient):
    token = await _register_and_login(client)
    response = await client.post(
        "/api/v1/prescriptions",
        files={"file": ("notes.txt", b"hello", "text/plain")},
        headers=bearer(token),
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "upload_invalid"


async def test_upload_rejects_oversized_file(client: AsyncClient, monkeypatch):
    from app.core.config import get_settings

    monkeypatch.setattr(get_settings(), "max_upload_size_mb", 1)
    token = await _register_and_login(client)

    over = PNG_BYTES + b"\x00" * (1024 * 1024)  # clearly over 1 MB
    response = await client.post(
        "/api/v1/prescriptions",
        files={"file": ("big.png", over, "image/png")},
        headers=bearer(token),
    )
    assert response.status_code == 422
    assert "smaller than 1 MB" in response.json()["error"]["message"]

    # Exactly at the cap is also rejected (accepted files are strictly < cap).
    exact = b"\x89PNG\r\n\x1a\n" + b"\x00" * (1024 * 1024 - 8)  # exactly 1 MiB
    response = await client.post(
        "/api/v1/prescriptions",
        files={"file": ("exact.png", exact, "image/png")},
        headers=bearer(token),
    )
    assert response.status_code == 422


async def test_upload_rejects_tiny_file(client: AsyncClient):
    token = await _register_and_login(client)
    tiny = b"\x89PNG\r\n\x1a\n" + b"\x00" * 100  # ~108 bytes, below the 10 KB floor
    response = await client.post(
        "/api/v1/prescriptions",
        files={"file": ("tiny.png", tiny, "image/png")},
        headers=bearer(token),
    )
    assert response.status_code == 422
    assert "too small" in response.json()["error"]["message"]
    assert "10 KB" in response.json()["error"]["message"]


async def test_upload_allows_any_size_when_limit_disabled(
    client: AsyncClient, monkeypatch
):
    from app.core.config import get_settings

    monkeypatch.setattr(get_settings(), "max_upload_size_mb", 0)  # unlimited
    token = await _register_and_login(client)
    big = PNG_BYTES + b"\x00" * (1024 * 1024)  # would exceed a 1 MB cap
    response = await client.post(
        "/api/v1/prescriptions",
        files={"file": ("big.png", big, "image/png")},
        headers=bearer(token),
    )
    assert response.status_code == 201
    assert response.json()["file_size"] == len(big)


async def test_search_filters_prescriptions(client: AsyncClient):
    admin_token = await _register_and_login(client)
    await upload_prescription(client, admin_token, filename="lab-report.png")

    # The fake extraction records "John Doe" as the patient.
    hit = await client.get(
        "/api/v1/prescriptions?search=john", headers=bearer(admin_token)
    )
    assert hit.status_code == 200
    assert hit.json()["total"] == 1

    miss = await client.get(
        "/api/v1/prescriptions?search=nonexistent", headers=bearer(admin_token)
    )
    assert miss.json()["total"] == 0


async def test_stats_endpoint(client: AsyncClient):
    token = await _register_and_login(client)
    await upload_prescription(client, token)
    response = await client.get("/api/v1/prescriptions/stats", headers=bearer(token))
    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 1
    assert body["by_status"].get("completed") == 1
    assert len(body["recent"]) == 1



async def test_list_scoping_and_pagination(client: AsyncClient):
    admin_token = await _register_and_login(client)

    # Admin creates a staff user.
    await client.post(
        "/api/v1/users",
        json={
            "email": "staff@example.com",
            "password": "staffsecret1",
            "full_name": "Staff",
            "role": "staff",
        },
        headers=bearer(admin_token),
    )
    staff_tokens = await login(client, email="staff@example.com", password="staffsecret1")
    staff_token = staff_tokens["access_token"]

    await upload_prescription(client, admin_token, filename="a.png")
    await upload_prescription(client, staff_token, filename="b.png")
    await upload_prescription(client, staff_token, filename="c.png")

    admin_list = await client.get("/api/v1/prescriptions", headers=bearer(admin_token))
    assert admin_list.status_code == 200
    assert admin_list.json()["total"] == 3  # admin sees everything

    staff_list = await client.get("/api/v1/prescriptions", headers=bearer(staff_token))
    assert staff_list.json()["total"] == 2  # staff sees only their own

    paged = await client.get(
        "/api/v1/prescriptions?page=1&page_size=2", headers=bearer(admin_token)
    )
    assert len(paged.json()["items"]) == 2
    assert paged.json()["page_size"] == 2


async def test_file_download(client: AsyncClient):
    token = await _register_and_login(client)
    prescription = await upload_prescription(client, token)
    response = await client.get(
        f"/api/v1/prescriptions/{prescription.id}/file", headers=bearer(token)
    )
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("image/png")


async def test_owner_scoping_blocks_other_users(client: AsyncClient):
    first_token = await _register_and_login(client)
    prescription = await upload_prescription(client, first_token)

    # A second user (staff) cannot read the first user's prescription.
    admin_tokens = await login(client)
    await client.post(
        "/api/v1/users",
        json={
            "email": "other@example.com",
            "password": "othersecret1",
            "full_name": "Other",
            "role": "staff",
        },
        headers=bearer(admin_tokens["access_token"]),
    )
    other_tokens = await login(client, email="other@example.com", password="othersecret1")
    response = await client.get(
        f"/api/v1/prescriptions/{prescription.id}",
        headers=bearer(other_tokens["access_token"]),
    )
    assert response.status_code == 403


async def test_reprocess_and_delete(client: AsyncClient):
    token = await _register_and_login(client)
    prescription = await upload_prescription(client, token)

    reprocess = await client.post(
        f"/api/v1/prescriptions/{prescription.id}/reprocess", headers=bearer(token)
    )
    assert reprocess.status_code == 200

    deleted = await client.delete(
        f"/api/v1/prescriptions/{prescription.id}", headers=bearer(token)
    )
    assert deleted.status_code == 204
    missing = await client.get(
        f"/api/v1/prescriptions/{prescription.id}", headers=bearer(token)
    )
    assert missing.status_code == 404


async def test_sse_snapshot_for_finished_prescription(client: AsyncClient):
    token = await _register_and_login(client)
    prescription = await upload_prescription(client, token)

    collected = ""
    async with client.stream(
        "GET",
        f"/api/v1/prescriptions/{prescription.id}/events",
        headers=bearer(token),
    ) as response:
        assert response.status_code == 200
        assert response.headers["content-type"].startswith("text/event-stream")
        async for chunk in response.aiter_text():
            collected += chunk

    assert '"snapshot"' in collected
    assert '"completed"' in collected


async def test_upload_survives_broker_outage(client: AsyncClient, monkeypatch):
    token = await _register_and_login(client)

    def broken_delay(*_args, **_kwargs):
        raise RuntimeError("broker down")

    monkeypatch.setattr(
        "app.api.routes.prescriptions.process_prescription",
        SimpleNamespace(delay=broken_delay),
    )
    response = await client.post(
        "/api/v1/prescriptions",
        files={"file": ("rx.png", PNG_BYTES, "image/png")},
        headers=bearer(token),
    )
    assert response.status_code == 201
    assert response.json()["status"] == "failed"
    assert "broker down" in response.json()["error"]
