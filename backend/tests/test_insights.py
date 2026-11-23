"""AI insights tests: context builder, generation service, task, and endpoint."""

from __future__ import annotations

import json
from types import SimpleNamespace

import pytest

from app.core.errors import InferenceError
from app.services.insights import (
    _normalize_schedule,
    build_context,
    generate_insights_report,
)
from tests.conftest import bearer, login, register, upload_prescription

SUMMARY_JSON = {
    "summary": "Take Amoxicillin three times a day for a week; Ibuprofen only if needed.",
    "key_points": ["Finish the full Amoxicillin course", "Take it after meals"],
}
INTERACTIONS_JSON = {
    "risk_level": "low",
    "findings": [],
    "general_advice": "Space the medicines apart and stay hydrated.",
}
SCHEDULE_JSON = {
    "daily_plan": [
        {
            "medication": "Amoxicillin",
            "times": ["08:00", "14:00", "20:00"],
            "days": 7,
            "instructions": "after meals",
        },
        {
            "medication": "Ibuprofen",
            "times": [],
            "days": 5,
            "instructions": "as needed",
        },
    ],
    "notes": None,
}


def _patch_chat(monkeypatch, *, fail: bool = False, schedule_entries: int = 2):
    """Patch the Ollama client with scripted structured responses."""
    calls: list[dict] = []
    schedule_json = {
        "daily_plan": [
            {
                "medication": f"Med {index}",
                "times": ["08:00"],
                "days": 1,
                "instructions": None,
            }
            for index in range(schedule_entries)
        ],
        "notes": None,
    }
    responses = [
        json.dumps(SUMMARY_JSON),
        json.dumps(INTERACTIONS_JSON),
        json.dumps(schedule_json),
    ]

    def fake_chat(payload):
        calls.append(payload)
        if fail:
            raise InferenceError("Ollama is down")
        return responses[min(len(calls) - 1, len(responses) - 1)]

    monkeypatch.setattr("app.services.ollama.chat", fake_chat)
    return calls


def test_build_context_includes_all_fields():
    context = build_context(
        {
            "patient_name": "John Doe",
            "patient_age": 42,
            "doctor_name": "Dr. Sarah Smith",
            "prescribed_date": "2026-11-20",
            "notes": "Return if symptoms persist.",
            "medications": [
                {
                    "medication": "Amoxicillin",
                    "dosage": "500 mg",
                    "frequency": "3x daily",
                    "duration": "7 days",
                    "instructions": "after meals",
                }
            ],
        }
    )
    assert "patient: John Doe" in context
    assert "1. Amoxicillin | dosage: 500 mg | frequency: 3x daily" in context
    assert "notes: Return if symptoms persist." in context


def test_normalize_schedule_recovers_stray_fields_and_dedupes():
    from app.schemas.insights import MedicationSchedule, ScheduleMedication

    messy = MedicationSchedule(
        daily_plan=[
            ScheduleMedication(
                medication="Amoxicillin",
                times=["08:00", "14:00", "20:00", "days: 7", "instructions: after meals"],
                days=0,
                instructions=None,
            ),
            ScheduleMedication(
                medication="Ibuprofen",
                times=["as needed", "days: 5"],
                days=0,
                instructions=None,
            ),
            # Duplicate entry for the same medication — must be dropped.
            ScheduleMedication(
                medication="ibuprofen",
                times=[],
                days=0,
                instructions=None,
            ),
            # Bare day count inside instructions — harvested into days.
            ScheduleMedication(
                medication="Paracetamol",
                times=["09:00"],
                days=0,
                instructions="for 3 days",
            ),
        ],
        notes=None,
    )
    clean = _normalize_schedule(messy, medication_count=4)
    assert len(clean.daily_plan) == 3  # duplicate dropped

    first = clean.daily_plan[0]
    assert first.times == ["08:00", "14:00", "20:00"]
    assert first.days == 7
    assert first.instructions == "after meals"
    second = clean.daily_plan[1]
    assert second.times == []
    assert second.days == 5
    assert second.instructions == "as needed"
    third = clean.daily_plan[2]
    assert third.days == 3
    assert third.instructions is None


def test_daily_plan_accepts_more_than_ten_entries():
    """Regression: 11 extracted medications must not fail schedule validation.

    The schedule grammar is pinned to one entry per medication, so the
    Pydantic cap must stay >= the extraction cap (20).
    """
    from app.schemas.insights import MedicationSchedule

    entries = [
        {
            "medication": f"Med {index}",
            "times": ["08:00"],
            "days": 1,
            "instructions": None,
        }
        for index in range(11)
    ]
    schedule = MedicationSchedule.model_validate(
        {"daily_plan": entries, "notes": None}
    )
    assert len(schedule.daily_plan) == 11


def test_generate_insights_report_pins_schedule_to_medication_count(monkeypatch):
    """11 medications -> grammar pinned to 11 entries, validated cleanly."""
    calls = _patch_chat(monkeypatch, schedule_entries=11)
    report = generate_insights_report("CONTEXT", medication_count=11)

    assert report.schedule.daily_plan is not None
    plan_constraint = calls[2]["format"]["properties"]["daily_plan"]
    assert plan_constraint["minItems"] == 11
    assert plan_constraint["maxItems"] == 11
    assert len(report.schedule.daily_plan) == 11


def test_normalize_schedule_truncates_beyond_count():
    from app.schemas.insights import MedicationSchedule, ScheduleMedication

    schedule = MedicationSchedule(
        daily_plan=[
            ScheduleMedication(
                medication=f"Med {index}", times=["08:00"], days=1, instructions=None
            )
            for index in range(14)
        ],
        notes=None,
    )
    normalized = _normalize_schedule(schedule, medication_count=11)
    assert len(normalized.daily_plan) == 11


def test_generate_insights_report_makes_three_structured_calls(monkeypatch):
    calls = _patch_chat(monkeypatch)
    report = generate_insights_report("CONTEXT-TEXT", medication_count=2)

    assert len(calls) == 3
    assert report.summary.startswith("Take Amoxicillin")
    assert report.key_points == SUMMARY_JSON["key_points"]
    assert report.interactions.risk_level == "low"
    assert report.interactions.findings == []
    assert report.schedule.daily_plan[0].times == ["08:00"]
    assert report.schedule.daily_plan[0].days == 1
    for index, call in enumerate(calls):
        assert "format" in call  # every call is grammar-constrained
        if index == 2:
            plan = call["format"]["properties"]["daily_plan"]
            assert plan["minItems"] == 2 and plan["maxItems"] == 2
    assert "CONTEXT-TEXT" in calls[2]["messages"][1]["content"]


def test_generate_insights_report_invalid_output(monkeypatch):
    monkeypatch.setattr(
        "app.services.ollama.chat", lambda _payload: "this is not json"
    )
    with pytest.raises(InferenceError, match="malformed JSON"):
        generate_insights_report("ctx")


async def test_insights_endpoint_full_flow(client, monkeypatch):
    _patch_chat(monkeypatch)
    await register(client)
    token = (await login(client))["access_token"]
    prescription = await upload_prescription(client, token)
    assert prescription.ai_insights_status is None

    response = await client.post(
        f"/api/v1/prescriptions/{prescription.id}/insights", headers=bearer(token)
    )
    assert response.status_code == 202
    assert response.json()["status"] == "pending"

    detail = await client.get(
        f"/api/v1/prescriptions/{prescription.id}", headers=bearer(token)
    )
    body = detail.json()
    assert body["ai_insights_status"] == "ready"
    assert body["ai_insights"]["summary"] == SUMMARY_JSON["summary"]
    assert body["ai_insights"]["key_points"] == SUMMARY_JSON["key_points"]
    assert body["ai_insights"]["interactions"]["risk_level"] == "low"
    assert body["ai_insights"]["schedule"]["daily_plan"][0]["times"] == ["08:00"]
    assert body["ai_insights"]["schedule"]["daily_plan"][0]["days"] == 1
    assert body["ai_insights_model"] is not None


async def test_insights_endpoint_requires_completed(client, monkeypatch):
    await register(client)
    token = (await login(client))["access_token"]
    # Suppress the eager pipeline so the prescription stays queued.
    monkeypatch.setattr(
        "app.api.routes.prescriptions.process_prescription",
        SimpleNamespace(delay=lambda *_args, **_kwargs: None),
    )
    prescription = await upload_prescription(client, token)
    assert prescription.status == "queued"

    response = await client.post(
        f"/api/v1/prescriptions/{prescription.id}/insights", headers=bearer(token)
    )
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "conflict"


async def test_insights_failure_marks_status_and_allows_retry(client, monkeypatch):
    _patch_chat(monkeypatch, fail=True)
    await register(client)
    token = (await login(client))["access_token"]
    prescription = await upload_prescription(client, token)

    first = await client.post(
        f"/api/v1/prescriptions/{prescription.id}/insights", headers=bearer(token)
    )
    assert first.status_code == 202
    detail = await client.get(
        f"/api/v1/prescriptions/{prescription.id}", headers=bearer(token)
    )
    assert detail.json()["ai_insights_status"] == "failed"

    # A failed run may be retried.
    retry = await client.post(
        f"/api/v1/prescriptions/{prescription.id}/insights", headers=bearer(token)
    )
    assert retry.status_code == 202
