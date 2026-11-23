"""Business logic for prescriptions: persistence, scoping, and extraction apply."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.errors import NotFoundError, PermissionDeniedError
from app.models.enums import PrescriptionStatus, Role
from app.models.prescription import Prescription, PrescriptionItem
from app.models.user import User


def _utcnow() -> datetime:
    return datetime.now(UTC)


async def create_prescription(
    db: AsyncSession,
    *,
    owner: User,
    original_filename: str,
    stored_path: str,
    mime_type: str,
    file_size: int,
    checksum: str,
) -> Prescription:
    prescription = Prescription(
        owner_id=owner.id,
        original_filename=original_filename,
        stored_path=stored_path,
        mime_type=mime_type,
        file_size=file_size,
        checksum=checksum,
        status=PrescriptionStatus.UPLOADED,
    )
    prescription.items = []  # transient-safe init: prevents async lazy-loads later
    db.add(prescription)
    await db.flush()
    return prescription


async def get_prescription(
    db: AsyncSession, prescription_id: uuid.UUID, user: User
) -> Prescription:
    """Fetch one prescription, enforcing owner/admin visibility."""
    prescription = await db.scalar(
        select(Prescription)
        .options(selectinload(Prescription.items))
        .where(Prescription.id == prescription_id)
    )
    if prescription is None:
        raise NotFoundError("Prescription not found")
    if user.role != Role.ADMIN and prescription.owner_id != user.id:
        raise PermissionDeniedError("You do not have access to this prescription")
    return prescription


async def list_prescriptions(
    db: AsyncSession,
    *,
    user: User,
    page: int = 1,
    page_size: int = 20,
    status: PrescriptionStatus | None = None,
    search: str | None = None,
) -> tuple[list[Prescription], int]:
    query = select(Prescription)
    if user.role != Role.ADMIN:
        query = query.where(Prescription.owner_id == user.id)
    if status is not None:
        query = query.where(Prescription.status == status)
    if search:
        term = f"%{search.strip()}%"
        query = query.where(
            or_(
                Prescription.original_filename.ilike(term),
                Prescription.patient_name.ilike(term),
                Prescription.doctor_name.ilike(term),
            )
        )
    total = await db.scalar(select(func.count()).select_from(query.subquery()))
    rows = await db.scalars(
        query.order_by(Prescription.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    return list(rows), int(total or 0)


async def delete_prescription(db: AsyncSession, prescription: Prescription) -> None:
    await db.delete(prescription)


# --- Attribute-only mutations (work for both async and sync sessions) --------


def set_status(prescription: Prescription, status: PrescriptionStatus) -> None:
    prescription.status = status
    if status == PrescriptionStatus.PROCESSING:
        prescription.processing_started_at = _utcnow()


def mark_failed(prescription: Prescription, error: str) -> None:
    prescription.status = PrescriptionStatus.FAILED
    prescription.error = error[:2000]
    prescription.completed_at = _utcnow()


def apply_extraction(
    prescription: Prescription,
    extraction,  # noqa: ANN001 - PrescriptionExtraction (avoids worker import cycle)
    *,
    model_name: str,
    raw_output: str,
) -> None:
    """Write inference results onto the prescription (replaces items)."""
    prescription.patient_name = extraction.patient_name
    prescription.patient_age = extraction.patient_age
    prescription.doctor_name = extraction.doctor_name
    prescription.prescribed_date = extraction.prescribed_date
    prescription.notes = extraction.notes
    prescription.confidence = extraction.confidence
    prescription.model_name = model_name
    prescription.raw_output = raw_output
    prescription.error = None
    prescription.status = PrescriptionStatus.COMPLETED
    prescription.completed_at = _utcnow()
    prescription.items = [
        PrescriptionItem(
            medication=med.name,
            dosage=med.dosage,
            frequency=med.frequency,
            duration=med.duration,
            instructions=med.instructions,
        )
        for med in extraction.medications
    ]


async def get_stats(
    db: AsyncSession, *, user: User
) -> tuple[int, dict[str, int], list[Prescription]]:
    query = select(Prescription.status, func.count()).group_by(Prescription.status)
    if user.role != Role.ADMIN:
        query = query.where(Prescription.owner_id == user.id)
    by_status = {row[0]: int(row[1]) for row in await db.execute(query)}

    total_query = select(func.count()).select_from(Prescription)
    if user.role != Role.ADMIN:
        total_query = total_query.where(Prescription.owner_id == user.id)
    total = int(await db.scalar(total_query) or 0)

    recent_query = select(Prescription).order_by(Prescription.created_at.desc()).limit(5)
    if user.role != Role.ADMIN:
        recent_query = recent_query.where(Prescription.owner_id == user.id)
    recent = list(await db.scalars(recent_query))
    return total, by_status, recent

