"""Health and root endpoint tests."""

from __future__ import annotations

from httpx import AsyncClient


async def test_root_returns_service_info(client: AsyncClient):
    response = await client.get("/")
    assert response.status_code == 200
    body = response.json()
    assert body["docs"] == "/docs"
    assert "app" in body


async def test_health_ok(client: AsyncClient):
    response = await client.get("/api/v1/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["environment"] == "test"


async def test_health_detailed_reports_components(client: AsyncClient):
    response = await client.get("/api/v1/health/detailed")
    assert response.status_code == 200
    components = response.json()["components"]
    assert components["database"] is True
    assert components["redis"] is True
    # Ollama health is environment-dependent (may or may not be running).
    assert isinstance(components["ollama"], bool)
