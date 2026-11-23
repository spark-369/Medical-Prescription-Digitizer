"""Celery task pipeline tests (eager mode, deterministic inference)."""

from __future__ import annotations

from types import SimpleNamespace

from httpx import AsyncClient

from app.core.errors import InferenceError
from app.services.inference import PrescriptionExtraction
from app.workers.tasks import process_prescription
from tests.conftest import bearer, login, register, upload_prescription


async def _setup_queued_prescription(client: AsyncClient, monkeypatch) -> str:
    """Upload while suppressing the inline eager run, then return the id."""
    await register(client)
    tokens = await login(client)
    monkeypatch.setattr(
        "app.api.routes.prescriptions.process_prescription",
        SimpleNamespace(delay=lambda *_a, **_k: None),
    )
    prescription = await upload_prescription(client, tokens["access_token"])
    assert prescription.status == "queued"
    return str(prescription.id)


async def test_process_task_completes(client: AsyncClient, monkeypatch):
    prescription_id = await _setup_queued_prescription(client, monkeypatch)

    result = process_prescription.apply(args=[prescription_id])
    assert result.result["status"] == "completed"
    assert result.result["medications"] == 2

    tokens = await login(client)
    detail = await client.get(
        f"/api/v1/prescriptions/{prescription_id}", headers=bearer(tokens["access_token"])
    )
    body = detail.json()
    assert body["status"] == "completed"
    assert body["patient_name"] == "John Doe"
    assert len(body["items"]) == 2
    assert body["completed_at"] is not None


async def test_process_task_marks_failure(client: AsyncClient, monkeypatch):
    prescription_id = await _setup_queued_prescription(client, monkeypatch)

    def failing_inference(_image_b64: str) -> PrescriptionExtraction:
        raise InferenceError("Ollama is down")

    monkeypatch.setattr("app.workers.tasks.run_inference", failing_inference)

    result = process_prescription.apply(args=[prescription_id])
    assert result.result["status"] == "failed"

    tokens = await login(client)
    detail = await client.get(
        f"/api/v1/prescriptions/{prescription_id}", headers=bearer(tokens["access_token"])
    )
    body = detail.json()
    assert body["status"] == "failed"
    assert "Ollama is down" in body["error"]


async def test_process_task_missing_file_fails_gracefully(
    client: AsyncClient, monkeypatch
):
    prescription_id = await _setup_queued_prescription(client, monkeypatch)
    # Remove stored uploads (YYYY/MM subdirectories) to simulate storage loss.
    from app.core.config import get_settings

    stored = get_settings().resolved_upload_dir
    for path in stored.rglob("*"):
        if path.is_file() and path.parent != stored:
            path.unlink()

    result = process_prescription.apply(args=[prescription_id])
    assert result.result["status"] == "failed"
