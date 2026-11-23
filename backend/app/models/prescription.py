"""Prescription and extracted medication models."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import DateTime, Float, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import JSON, Uuid

from app.db.base import Base, TimestampMixin, UUIDMixin
from app.models.enums import PrescriptionStatus

if TYPE_CHECKING:
    pass


class Prescription(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "prescriptions"
    __table_args__ = (
        Index("ix_prescriptions_status", "status"),
        Index("ix_prescriptions_owner_id", "owner_id"),
    )

    owner_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )

    # Original upload
    original_filename: Mapped[str] = mapped_column(String(255), nullable=False)
    stored_path: Mapped[str] = mapped_column(String(512), nullable=False)
    mime_type: Mapped[str] = mapped_column(String(64), nullable=False)
    file_size: Mapped[int] = mapped_column(Integer, nullable=False)
    checksum: Mapped[str] = mapped_column(String(64), nullable=False)

    # Processing lifecycle
    status: Mapped[str] = mapped_column(
        String(32), default=PrescriptionStatus.UPLOADED, nullable=False
    )
    error: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Inference results
    raw_output: Mapped[str | None] = mapped_column(Text, nullable=True)
    confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    model_name: Mapped[str | None] = mapped_column(String(128), nullable=True)

    patient_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    patient_age: Mapped[int | None] = mapped_column(Integer, nullable=True)
    doctor_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    prescribed_date: Mapped[str | None] = mapped_column(String(64), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    processing_started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # AI insights (summary / interaction check / daily schedule)
    ai_insights: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    ai_insights_status: Mapped[str | None] = mapped_column(String(16), nullable=True)
    ai_insights_model: Mapped[str | None] = mapped_column(String(128), nullable=True)
    ai_insights_generated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    owner = relationship("User", back_populates="prescriptions")
    items = relationship(
        "PrescriptionItem",
        back_populates="prescription",
        cascade="all, delete-orphan",
        order_by="PrescriptionItem.created_at",
    )

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Prescription {self.id} status={self.status}>"


class PrescriptionItem(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "prescription_items"

    prescription_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("prescriptions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    medication: Mapped[str] = mapped_column(String(255), nullable=False)
    dosage: Mapped[str | None] = mapped_column(String(128), nullable=True)
    frequency: Mapped[str | None] = mapped_column(String(128), nullable=True)
    duration: Mapped[str | None] = mapped_column(String(128), nullable=True)
    instructions: Mapped[str | None] = mapped_column(Text, nullable=True)

    prescription = relationship("Prescription", back_populates="items")
