"""AI analytics report endpoints (per-user, async generation)."""

from __future__ import annotations

import uuid

from fastapi import APIRouter
from sqlalchemy import select

from app.api.deps import CurrentUser, DbSession
from app.core.errors import NotFoundError
from app.models.ai_report import AiReport
from app.schemas.report import AiReportOut, ReportGeneratedResponse
from app.workers.tasks import generate_report as generate_report_task

router = APIRouter(prefix="/reports", tags=["reports"])


@router.get("", response_model=list[AiReportOut])
async def list_reports(db: DbSession, user: CurrentUser) -> list[AiReport]:
    """List the caller's AI reports, newest first."""
    rows = await db.scalars(
        select(AiReport)
        .where(AiReport.user_id == user.id)
        .order_by(AiReport.created_at.desc())
        .limit(20)
    )
    return list(rows)


@router.post("/generate", response_model=ReportGeneratedResponse, status_code=202)
async def generate_report_endpoint(
    db: DbSession, user: CurrentUser
) -> ReportGeneratedResponse:
    """Create a pending report row and enqueue its generation."""
    report = AiReport(user_id=user.id, status="pending")
    db.add(report)
    await db.commit()
    await db.refresh(report)
    try:
        generate_report_task.delay(str(report.id))
    except Exception as exc:  # broker unreachable — mark and surface
        report.status = "failed"
        report.error = f"Task queue unavailable: {exc}"
        await db.commit()
        raise
    return ReportGeneratedResponse(id=report.id, status=report.status)


@router.delete("/{report_id}", status_code=204)
async def delete_report(
    report_id: uuid.UUID, db: DbSession, user: CurrentUser
) -> None:
    report = await db.scalar(
        select(AiReport).where(AiReport.id == report_id, AiReport.user_id == user.id)
    )
    if report is None:
        raise NotFoundError("Report not found")
    await db.delete(report)
    await db.flush()
