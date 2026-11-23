"""Pydantic schemas for AI-generated prescription insights.

These models double as the Ollama ``format`` JSON schemas (grammar
constraints) and as the stored/read shape for the API.

Medical safety note: interaction findings from a small local model are
informational only — the UI must always present them with a disclaimer.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class PrescriptionSummary(BaseModel):
    """Plain-language explanation of the prescription."""

    model_config = ConfigDict(extra="forbid")

    summary: str = Field(description="2-4 short sentences in plain language")
    # max_length -> maxItems in the JSON schema: bounds grammar generation so
    # a confused model cannot loop forever adding entries.
    key_points: list[str] = Field(default_factory=list, max_length=8)


class InteractionFinding(BaseModel):
    """One potential interaction or duplication between medications."""

    model_config = ConfigDict(extra="forbid")

    medications: list[str] = Field(max_length=6)
    severity: Literal["low", "moderate", "high", "unknown"]
    description: str
    recommendation: str


class InteractionReport(BaseModel):
    """Overall drug-interaction review result."""

    model_config = ConfigDict(extra="forbid")

    risk_level: Literal["none", "low", "moderate", "high", "unknown"]
    findings: list[InteractionFinding] = Field(default_factory=list, max_length=10)
    general_advice: str | None = None


class ScheduleMedication(BaseModel):
    """Daily schedule for one medication (times in 24h HH:MM)."""

    model_config = ConfigDict(extra="forbid")

    medication: str
    times: list[str] = Field(default_factory=list, max_length=6)
    days: int = 0
    instructions: str | None = None


class MedicationSchedule(BaseModel):
    """Compact daily plan — expanded per day in the UI if needed."""

    model_config = ConfigDict(extra="forbid")

    # Cap mirrors the extraction limit (20 medications), so a pinned
    # exact-count grammar can never produce output the model rejects.
    daily_plan: list[ScheduleMedication] = Field(default_factory=list, max_length=20)
    notes: str | None = None


class PrescriptionInsights(BaseModel):
    """The full AI-insights bundle stored per prescription."""

    model_config = ConfigDict(extra="forbid")

    summary: str
    key_points: list[str] = Field(default_factory=list)
    interactions: InteractionReport
    schedule: MedicationSchedule
