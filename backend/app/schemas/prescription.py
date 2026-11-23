"""Pydantic v2 request/response schemas for prescriptions."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import PrescriptionStatus


class PrescriptionItemOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    medication: str
    dosage: str | None = None
    frequency: str | None = None
    duration: str | None = None
    instructions: str | None = None


class PrescriptionBrief(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    status: PrescriptionStatus
    original_filename: str
    patient_name: str | None = None
    doctor_name: str | None = None
    prescribed_date: str | None = None
    created_at: datetime


class PrescriptionOut(PrescriptionBrief):
    model_config = ConfigDict(from_attributes=True)

    mime_type: str
    file_size: int
    error: str | None = None
    raw_output: str | None = None
    confidence: float | None = None
    model_name: str | None = None
    patient_age: int | None = None
    notes: str | None = None
    processing_started_at: datetime | None = None
    completed_at: datetime | None = None
    updated_at: datetime
    items: list[PrescriptionItemOut] = Field(default_factory=list)

    # AI insights (raw JSON as generated — typed on the frontend)
    ai_insights: dict[str, Any] | None = None
    ai_insights_status: str | None = None
    ai_insights_model: str | None = None
    ai_insights_generated_at: datetime | None = None


class PrescriptionListOut(BaseModel):
    items: list[PrescriptionBrief]
    total: int
    page: int
    page_size: int


class StatsOut(BaseModel):
    total: int
    by_status: dict[str, int]
    recent: list[PrescriptionBrief]


class InsightsStatusResponse(BaseModel):
    status: str
