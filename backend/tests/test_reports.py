"""AI analytics report tests: aggregation, task, and REST endpoints."""

from __future__ import annotations

from app.schemas.report import ReportContent
from tests.conftest import bearer, login, register, upload_prescription

REPORT_JSON = {
    "headline": "A busy month of digitization",
    "overview": "You digitized 10 prescriptions with a 90% completion rate.",
    "highlights": [
        {"title": "Most prescribed", "detail": "Amoxicillin appears in 4 records."},
    ],
    "recommendations": ["Review the failed extraction."],
}


def _patch_report_llm(monkeypatch):
    captured: list[str] = []

    def fake_generate(context: str) -> ReportContent:
        captured.append(context)
        return ReportContent.model_validate(REPORT_JSON)

    monkeypatch.setattr("app.workers.tasks.generate_report_content", fake_generate)
    return captured


async def test_generate_report_full_flow(client, monkeypatch):
    captured = _patch_report_llm(monkeypatch)
    await register(client)
    token = (await login(client))["access_token"]
    await upload_prescription(client, token)

    start = await client.post(
        "/api/v1/reports/generate", headers=bearer(token)
    )
    assert start.status_code == 202
    report_id = start.json()["id"]
    assert start.json()["status"] == "pending"

    listing = await client.get("/api/v1/reports", headers=bearer(token))
    assert listing.status_code == 200
    reports = listing.json()
    assert len(reports) == 1
    assert reports[0]["id"] == report_id
    assert reports[0]["status"] == "ready"
    assert reports[0]["content"]["headline"] == REPORT_JSON["headline"]
    assert reports[0]["content"]["overview"].startswith("You digitized")

    # Aggregated numbers must be grounded in the test data.
    assert "total_prescriptions: 1" in captured[0]


async def test_reports_are_isolated_per_user(client, monkeypatch):
    _patch_report_llm(monkeypatch)
    await register(client)
    admin_token = (await login(client))["access_token"]

    await client.post("/api/v1/reports/generate", headers=bearer(admin_token))
    mine = await client.get("/api/v1/reports", headers=bearer(admin_token))
    assert len(mine.json()) == 1

    # A second user sees nothing.
    await client.post(
        "/api/v1/users",
        json={
            "email": "other@example.com",
            "password": "othersecret1",
            "full_name": "Other",
            "role": "staff",
        },
        headers=bearer(admin_token),
    )
    other_tokens = await login(client, email="other@example.com", password="othersecret1")
    theirs = await client.get("/api/v1/reports", headers=bearer(other_tokens["access_token"]))
    assert theirs.json() == []


async def test_report_generation_failure_marks_status(client, monkeypatch):
    def failing_generate(context: str) -> ReportContent:
        raise RuntimeError("Ollama exploded")

    monkeypatch.setattr(
        "app.workers.tasks.generate_report_content", failing_generate
    )
    await register(client)
    token = (await login(client))["access_token"]

    start = await client.post("/api/v1/reports/generate", headers=bearer(token))
    assert start.status_code == 202

    listing = await client.get("/api/v1/reports", headers=bearer(token))
    assert listing.json()[0]["status"] == "failed"


async def test_delete_report(client, monkeypatch):
    _patch_report_llm(monkeypatch)
    await register(client)
    token = (await login(client))["access_token"]
    await client.post("/api/v1/reports/generate", headers=bearer(token))

    listing = await client.get("/api/v1/reports", headers=bearer(token))
    report_id = listing.json()[0]["id"]

    deleted = await client.delete(
        f"/api/v1/reports/{report_id}", headers=bearer(token)
    )
    assert deleted.status_code == 204

    listing = await client.get("/api/v1/reports", headers=bearer(token))
    assert listing.json() == []


async def test_reports_require_authentication(client):
    response = await client.get("/api/v1/reports")
    assert response.status_code == 401
