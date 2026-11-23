"""Structured-output parsing and Ollama client tests."""

from __future__ import annotations

import json

import httpx
import pytest

from app.core.errors import InferenceError
from app.services.inference import (
    MedicationExtraction,
    PrescriptionExtraction,
    build_format_schema,
    parse_model_output,
    run_inference,
)

VALID = {
    "patient_name": "Jane Roe",
    "patient_age": 30,
    "doctor_name": "Dr. Who",
    "prescribed_date": "2026-02-01",
    "medications": [
        {"name": "Paracetamol", "dosage": "500 mg", "frequency": "2x/day",
         "duration": "5 days", "instructions": None}
    ],
    "notes": None,
    "confidence": 0.87,
}


def test_format_schema_contains_all_fields():
    schema = build_format_schema()
    assert set(schema["properties"]) >= {
        "patient_name",
        "patient_age",
        "doctor_name",
        "prescribed_date",
        "medications",
        "notes",
        "confidence",
    }
    medications = schema["properties"]["medications"]
    ref = medications.get("items", {}).get("$ref")
    if ref:  # pydantic v2 nests nested models under $defs
        item_schema = schema["$defs"][ref.split("/")[-1]]
    else:
        item_schema = medications["items"]
    assert "properties" in item_schema
    assert set(item_schema["properties"]) >= {"name", "dosage", "frequency"}


def test_parse_plain_json():
    result = parse_model_output(json.dumps(VALID))
    assert result.patient_name == "Jane Roe"
    assert result.medications[0].name == "Paracetamol"
    assert result.confidence == 0.87


def test_parse_fenced_json():
    fenced = f"```json\n{json.dumps(VALID)}\n```"
    result = parse_model_output(fenced)
    assert result.doctor_name == "Dr. Who"


def test_parse_malformed_json_raises():
    with pytest.raises(ValueError, match="malformed JSON"):
        parse_model_output("this is not json")


def test_parse_schema_violation_raises():
    bad = {**VALID, "medications": "not-a-list"}
    with pytest.raises(ValueError, match="schema validation"):
        parse_model_output(json.dumps(bad))


def test_parse_rejects_unknown_fields():
    bad = {**VALID, "surprise_field": 1}
    with pytest.raises(ValueError, match="schema validation"):
        parse_model_output(json.dumps(bad))


def test_run_inference_two_pass(monkeypatch):
    """Pass 1 transcribes the image, pass 2 parses it under the JSON schema."""
    calls: list[dict] = []

    class FakeResponse:
        def __init__(self, content: str) -> None:
            self._content = content

        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict:
            return {"message": {"content": self._content}}

    transcript = "Patient: Jane Roe\nAge: 30\nRx:\n1. Paracetamol 500 mg 2x/day 5 days"

    def fake_post(url, **kwargs):
        calls.append(kwargs.get("json"))
        if len(calls) == 1:
            return FakeResponse(transcript)
        return FakeResponse(json.dumps(VALID))

    monkeypatch.setattr(httpx, "post", fake_post)
    result = run_inference("QkFTRTY0")

    assert result.patient_name == "Jane Roe"
    assert len(calls) == 2
    first, second = calls
    assert first["messages"][1]["images"] == ["QkFTRTY0"]
    assert "format" not in first  # transcription pass is free-form
    assert second["format"] == build_format_schema()
    assert "Jane Roe" in second["messages"][1]["content"]


def test_run_inference_empty_transcription(monkeypatch):
    class EmptyResponse:
        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict:
            return {"message": {"content": "   "}}

    monkeypatch.setattr(httpx, "post", lambda *a, **k: EmptyResponse())
    with pytest.raises(InferenceError, match="empty transcription"):
        run_inference("QkFTRTY0")


def test_run_inference_connection_error(monkeypatch):
    def failing_post(*_args, **_kwargs):
        raise httpx.ConnectError("connection refused")

    monkeypatch.setattr(httpx, "post", failing_post)
    with pytest.raises(InferenceError, match="Ollama request failed"):
        run_inference("QkFTRTY0")


def test_run_inference_invalid_parse_output(monkeypatch):
    class FakeResponse:
        def __init__(self, content: str) -> None:
            self._content = content

        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict:
            return {"message": {"content": self._content}}

    responses = iter([FakeResponse("some text"), FakeResponse("garbage")])
    monkeypatch.setattr(httpx, "post", lambda *a, **k: next(responses))
    with pytest.raises(InferenceError, match="malformed JSON"):
        run_inference("QkFTRTY0")


def test_prepare_image_bytes_downscales_large_images():
    from io import BytesIO

    from PIL import Image

    from app.services.inference import prepare_image_bytes

    # Noisy image: does not compress, so the resized JPEG is really smaller.
    big = Image.effect_noise((3600, 2400), 30)
    buffer = BytesIO()
    big.save(buffer, format="PNG")
    data = buffer.getvalue()

    result = prepare_image_bytes(data)

    resized = Image.open(BytesIO(result))
    assert max(resized.size) == 2000
    assert len(result) < len(data)


def test_prepare_image_bytes_keeps_small_images_intact():
    from io import BytesIO

    from PIL import Image

    from app.services.inference import prepare_image_bytes

    small = Image.new("RGB", (800, 600), (10, 10, 10))
    buffer = BytesIO()
    small.save(buffer, format="JPEG", quality=90)
    data = buffer.getvalue()

    assert prepare_image_bytes(data) == data


def test_prepare_image_bytes_falls_back_on_invalid_data():
    from app.services.inference import prepare_image_bytes

    garbage = b"definitely not an image" * 100
    assert prepare_image_bytes(garbage) == garbage


def test_extraction_models_defaults():
    extraction = PrescriptionExtraction()
    assert extraction.medications == []
    assert extraction.confidence == 0.0
    med = MedicationExtraction(name="Aspirin")
    assert med.dosage is None
