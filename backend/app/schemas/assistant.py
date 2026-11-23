"""Schemas for the AI assistant chat endpoint.

The reply is a grammar-constrained (Ollama ``format``) JSON object so the
frontend always receives clean, structured output — never raw markdown.
"""

from __future__ import annotations

import uuid
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class ChatMessageIn(BaseModel):
    role: Literal["user", "assistant"]
    content: str = Field(min_length=1, max_length=4000)


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=2000)
    prescription_id: uuid.UUID | None = None
    history: list[ChatMessageIn] = Field(default_factory=list, max_length=12)


class AssistantReply(BaseModel):
    """Structured chat reply (also used as the Ollama ``format`` schema)."""

    model_config = ConfigDict(extra="forbid")

    answer: str = Field(
        description=(
            "The reply in plain text, 2-6 short sentences, without any "
            "markdown symbols such as **, # or *."
        ),
    )
    key_points: list[str] = Field(
        default_factory=list,
        max_length=6,
        description="0-5 very short bullet takeaways (max ~12 words each).",
    )
    follow_ups: list[str] = Field(
        default_factory=list,
        max_length=4,
        description="0-3 short suggested follow-up questions the user might ask.",
    )
