"""Thin Ollama client shared by the inference pipeline and AI insights.

All calls go through ``/api/chat``. Structured calls pass a JSON schema in
Ollama's ``format`` parameter so the model can only emit schema-valid JSON.
"""

from __future__ import annotations

import json
import re
from typing import Any

import httpx
from pydantic import BaseModel, ValidationError

from app.core.config import get_settings
from app.core.errors import InferenceError
from app.core.logging import get_logger

logger = get_logger(__name__)

_FENCE_RE = re.compile(r"^\s*```(?:json)?\s*(.*?)\s*```\s*$", re.DOTALL)


def chat(payload: dict[str, Any]) -> str:
    """POST one /api/chat request and return the assistant content."""
    settings = get_settings()
    url = f"{settings.ollama_base_url.rstrip('/')}/api/chat"
    try:
        response = httpx.post(url, json=payload, timeout=settings.ollama_timeout_seconds)
        response.raise_for_status()
        return response.json()["message"]["content"]
    except httpx.HTTPError as exc:
        raise InferenceError(f"Ollama request failed: {exc}") from exc
    except (KeyError, TypeError) as exc:
        raise InferenceError("Unexpected Ollama response shape") from exc


def forced_schema(
    model_cls: type[BaseModel],
    *,
    exact_items: dict[str, int] | None = None,
) -> dict[str, Any]:
    """JSON schema for Ollama's ``format`` parameter with every key required.

    Marking all fields required prevents small models from terminating at the
    shortest valid JSON object (emitting nulls for everything else). Values
    may still be ``null`` — fields are nullable in the schema.

    ``exact_items`` pins ``minItems``/``maxItems`` for list fields so the
    grammar must produce exactly that many entries (e.g. one schedule entry
    per medication) — this prevents small models from looping duplicates.
    """
    schema = model_cls.model_json_schema()
    properties = schema.get("properties", {})
    schema["required"] = list(properties.keys())
    for field, count in (exact_items or {}).items():
        prop = properties.get(field)
        if prop is not None:
            prop["minItems"] = count
            prop["maxItems"] = count
    return schema


def parse_structured(raw: str, model_cls: type[BaseModel]) -> BaseModel:
    """Parse raw model output into a validated Pydantic model."""
    text = raw.strip()
    fenced = _FENCE_RE.match(text)
    if fenced:
        text = fenced.group(1).strip()
    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        raise InferenceError("Model returned malformed JSON") from exc
    try:
        return model_cls.model_validate(data)
    except ValidationError as exc:
        raise InferenceError(f"Model output failed schema validation: {exc}") from exc


def structured_chat(
    system: str,
    user: str,
    schema_model: type[BaseModel],
    *,
    exact_items: dict[str, int] | None = None,
) -> BaseModel:
    """One grammar-constrained chat call validated against ``schema_model``."""
    settings = get_settings()
    payload: dict[str, Any] = {
        "model": settings.ollama_model,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        "format": forced_schema(schema_model, exact_items=exact_items),
        "stream": False,
        "options": {
            "temperature": settings.ollama_temperature,
            "num_ctx": settings.ollama_num_ctx,
        },
    }
    logger.info("Ollama structured call -> %s", schema_model.__name__)
    raw = chat(payload)
    return parse_structured(raw, schema_model)
