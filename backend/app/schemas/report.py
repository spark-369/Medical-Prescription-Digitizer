"""Pydantic schemas for AI analytics reports."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class ReportHighlight(BaseModel):
    """One notable observation in the prescription history."""

    model_config = ConfigDict(extra="forbid")

    title: str
    detail: str


class ReportContent(BaseModel):
    """Structured analytics report over a user's prescription history."""

    model_config = ConfigDict(extra="forbid")

    headline: str
    overview: str
    highlights: list[ReportHighlight] = Field(default_factory=list, max_length=6)
    recommendations: list[str] = Field(default_factory=list, max_length=6)


class AiReportOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    status: Literal["pending", "ready", "failed"]
    content: dict[str, Any] | None = None
    model: str | None = None
    created_at: datetime


class ReportGeneratedResponse(BaseModel):
    id: uuid.UUID
    status: str
