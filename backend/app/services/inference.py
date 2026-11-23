"""Ollama vision inference with grammar-constrained (structured) output.

The extraction schema is derived from the Pydantic models below via
``model_json_schema()`` and passed as the ``format`` parameter to Ollama's
``/api/chat`` endpoint, so the model can only emit JSON matching the schema.
Target model: Qwen3-VL-2B-Instruct (GGUF Q4_K_M).
"""

from __future__ import annotations

import json
import re
from typing import Any

import httpx
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from app.core.config import get_settings
from app.core.errors import InferenceError
from app.core.logging import get_logger
from app.services.ollama import chat, forced_schema

logger = get_logger(__name__)


class MedicationExtraction(BaseModel):
    """A single prescribed medication parsed from the image."""

    model_config = ConfigDict(extra="forbid")

    name: str
    dosage: str | None = None
    frequency: str | None = None
    duration: str | None = None
    instructions: str | None = None


class PrescriptionExtraction(BaseModel):
    """Structured extraction result for a prescription image."""

    model_config = ConfigDict(extra="forbid")

    patient_name: str | None = None
    patient_age: int | None = None
    doctor_name: str | None = None
    prescribed_date: str | None = None
    medications: list[MedicationExtraction] = Field(
        default_factory=list, max_length=20
    )
    notes: str | None = None
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)


# --- Pass 1: vision transcription -------------------------------------------
# Small vision models are far more reliable at plain transcription than at
# emitting structured JSON directly from an image.
TRANSCRIBE_SYSTEM_PROMPT = "You are a meticulous OCR engine."

TRANSCRIBE_PROMPT = (
    "Transcribe every line of text visible in this prescription image, top to "
    "bottom, exactly as written. Output only the transcription."
)

# --- Pass 2: grammar-constrained structured extraction -----------------------
PARSE_SYSTEM_PROMPT = (
    "You are a deterministic data extraction engine. You output only JSON."
)

PARSE_PROMPT = """\
Fill in EVERY field of the JSON schema using ONLY the transcription below.
- patient_name: the patient's full name.
- patient_age: the patient's age as an integer.
- doctor_name: the prescribing doctor's name.
- prescribed_date: the date the prescription was issued (YYYY-MM-DD when possible).
- medications: one entry for each prescribed drug, each with its name, dosage
  (strength, e.g. "500 mg"), frequency (schedule, e.g. "3x daily"), duration
  (length, e.g. "7 days") and any special instructions.
- notes: any additional comments or follow-up instructions.
- confidence: your overall confidence between 0.0 and 1.0.

Every field listed above MUST be filled when the transcription contains the
information. Use null only when the transcription has no such text.

Transcription:
"""


def build_format_schema() -> dict[str, Any]:
    """JSON schema handed to Ollama's ``format`` parameter (all keys forced)."""
    return forced_schema(PrescriptionExtraction)


_FENCE_RE = re.compile(r"^\s*```(?:json)?\s*(.*?)\s*```\s*$", re.DOTALL)


def parse_model_output(raw: str) -> PrescriptionExtraction:
    """Parse raw model text into a validated PrescriptionExtraction."""
    text = raw.strip()
    fenced = _FENCE_RE.match(text)
    if fenced:
        text = fenced.group(1).strip()
    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ValueError("Model returned malformed JSON") from exc
    try:
        return PrescriptionExtraction.model_validate(data)
    except ValidationError as exc:
        raise ValueError(f"Model output failed schema validation: {exc}") from exc


def prepare_image_bytes(
    data: bytes,
    *,
    max_side: int = 2000,
    jpeg_quality: int = 85,
) -> bytes:
    """Downscale large images before inference.

    Phone photos are often 3-12 MB at 3000-4000 px, which inflates the
    vision token count and makes transcription take minutes. Resizing the
    long side (text stays legible) and re-encoding as JPEG typically cuts
    the payload by an order of magnitude. Any preprocessing failure falls
    back to the original bytes so uploads never break.
    """
    try:
        from io import BytesIO

        from PIL import Image

        image = Image.open(BytesIO(data))
        image.load()
        width, height = image.size

        already_small = max(width, height) <= max_side
        if already_small and image.format == "JPEG":
            return data

        if not already_small:
            scale = max_side / float(max(width, height))
            image = image.resize(
                (max(1, round(width * scale)), max(1, round(height * scale)))
            )

        buffer = BytesIO()
        image.convert("RGB").save(buffer, format="JPEG", quality=jpeg_quality)
        resized = buffer.getvalue()
        logger.info(
            "Image preprocessed: %d px -> %d px, %d -> %d bytes",
            max(width, height),
            max(image.size),
            len(data),
            len(resized),
        )
        return resized if len(resized) < len(data) else data
    except Exception:  # noqa: BLE001 - never fail an upload over preprocessing
        logger.warning("Image preprocessing failed — sending original bytes")
        return data


def run_inference(image_b64: str) -> PrescriptionExtraction:
    """Two-pass pipeline (called synchronously from the Celery worker).

    Pass 1 transcribes the image with the vision model; pass 2 converts the
    transcription into the structured schema using Ollama's grammar
    constrained ``format`` parameter. Small VLMs are far more reliable at
    transcription than at emitting JSON straight from an image.
    """
    settings = get_settings()
    logger.info("Calling Ollama model=%s (transcription pass)", settings.ollama_model)
    transcript = chat(
        {
            "model": settings.ollama_model,
            "messages": [
                {"role": "system", "content": TRANSCRIBE_SYSTEM_PROMPT},
                {"role": "user", "content": TRANSCRIBE_PROMPT, "images": [image_b64]},
            ],
            "stream": False,
            "options": {
                "temperature": 0.0,
                "num_ctx": settings.ollama_num_ctx,
            },
        }
    ).strip()
    if not transcript:
        raise InferenceError("Model returned an empty transcription")

    logger.info("Calling Ollama model=%s (structured parse pass)", settings.ollama_model)
    raw = chat(
        {
            "model": settings.ollama_model,
            "messages": [
                {"role": "system", "content": PARSE_SYSTEM_PROMPT},
                {"role": "user", "content": PARSE_PROMPT + transcript},
            ],
            "format": build_format_schema(),
            "stream": False,
            "options": {
                "temperature": settings.ollama_temperature,
                "num_ctx": settings.ollama_num_ctx,
            },
        }
    )
    try:
        return parse_model_output(raw)
    except ValueError as exc:
        raise InferenceError(str(exc)) from exc


async def check_ollama_health() -> bool:
    """Best-effort connectivity probe for the health endpoint."""
    settings = get_settings()
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get(f"{settings.ollama_base_url.rstrip('/')}/api/tags")
            return response.status_code == 200
    except httpx.HTTPError:
        return False
