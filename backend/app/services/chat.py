"""AI assistant chat: grammar-constrained (structured JSON) replies.

Instead of streaming free-form markdown, every reply is forced through
Ollama's ``format`` JSON schema, so the frontend always gets a clean
``{answer, key_points, follow_ups}`` object.
"""

from __future__ import annotations

from typing import Any

from app.core.config import get_settings
from app.core.logging import get_logger
from app.schemas.assistant import AssistantReply
from app.services.ollama import chat, forced_schema, parse_structured

logger = get_logger(__name__)

ASSISTANT_SYSTEM_PROMPT = (
    "You are the built-in AI assistant of a medical prescription digitizer "
    "application used by clinic staff. Answer questions about medications, "
    "dosages and prescriptions in clear, patient-friendly language. "
    "If prescription data is provided, ground your answer strictly in it. "
    "Never diagnose, never prescribe and never change dosages; for medical "
    "decisions, advise consulting a doctor or pharmacist."
    "\n\nOutput rules:"
    "\n- answer: plain prose, 2-6 short sentences. NO markdown symbols "
    "(never use **, *, # or backticks)."
    "\n- key_points: 0-5 very short takeaway bullets."
    "\n- follow_ups: 0-3 short questions the user might ask next."
    "\nNever invent medical facts; use null-free clean language."
)


def assistant_reply(messages: list[dict[str, str]]) -> AssistantReply:
    """Produce one structured assistant reply for the given chat messages."""
    settings = get_settings()
    payload: dict[str, Any] = {
        "model": settings.ollama_model,
        "messages": messages,
        "format": forced_schema(AssistantReply),
        "stream": False,
        "options": {
            "temperature": settings.ollama_temperature,
            "num_ctx": settings.ollama_num_ctx,
        },
    }
    logger.info("Ollama structured call -> AssistantReply")
    raw = chat(payload)
    return parse_structured(raw, AssistantReply)
