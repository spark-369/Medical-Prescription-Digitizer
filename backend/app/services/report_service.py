"""AI analytics reports over a user's prescription history.

Aggregation is done with plain SQL (deterministic); the LLM only narrates
the aggregated numbers, so reports stay grounded in real data.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import func, select

from app.core.logging import get_logger
from app.models.prescription import Prescription, PrescriptionItem
from app.schemas.report import ReportContent
from app.services.ollama import structured_chat

logger = get_logger(__name__)

REPORT_SYSTEM_PROMPT = (
    "You are a healthcare analytics assistant. You summarize prescription "
    "activity and output only JSON."
)

REPORT_PROMPT = """\
Analyze the prescription activity summary below and produce a report.

Rules:
- headline: one short title for the report (max ~10 words).
- overview: 2-4 sentences describing overall activity and patterns.
- highlights: 2-4 entries; each with a short title and a 1-2 sentence detail
  (e.g. most prescribed medication, completion rate, data-quality issues).
- recommendations: 2-4 short actionable recommendations (e.g. follow up on
  failed extractions, review medication schedules).
- Base everything ONLY on the numbers below; do not invent medical facts.
- Output only JSON matching the schema.

Activity data:
"""


def collect_activity(session_factory, user_id: uuid.UUID) -> dict[str, Any]:
    """Aggregate a user's prescription history into report-ready numbers."""
    with session_factory() as session:
        status_rows = session.execute(
            select(Prescription.status, func.count())
            .where(Prescription.owner_id == user_id)
            .group_by(Prescription.status)
        ).all()
        by_status = {row[0]: int(row[1]) for row in status_rows}

        med_rows = session.execute(
            select(PrescriptionItem.medication, func.count())
            .join(Prescription, PrescriptionItem.prescription_id == Prescription.id)
            .where(Prescription.owner_id == user_id)
            .group_by(PrescriptionItem.medication)
            .order_by(func.count().desc())
            .limit(6)
        ).all()
        top_medications = [
            {"medication": row[0], "count": int(row[1])} for row in med_rows
        ]

        first_created = session.scalar(
            select(func.min(Prescription.created_at)).where(
                Prescription.owner_id == user_id
            )
        )
        total = int(
            session.scalar(
                select(func.count()).select_from(Prescription).where(
                    Prescription.owner_id == user_id
                )
            )
            or 0
        )
        total_medications = int(
            session.scalar(
                select(func.count())
                .select_from(PrescriptionItem)
                .join(Prescription, PrescriptionItem.prescription_id == Prescription.id)
                .where(Prescription.owner_id == user_id)
            )
            or 0
        )
        distinct_doctors = int(
            session.scalar(
                select(func.count(func.distinct(Prescription.doctor_name))).where(
                    Prescription.owner_id == user_id,
                    Prescription.doctor_name.is_not(None),
                )
            )
            or 0
        )

        return {
            "period_start": first_created.isoformat() if first_created else None,
            "period_end": datetime.now(UTC).isoformat(),
            "total_prescriptions": total,
            "total_medications_prescribed": total_medications,
            "by_status": by_status,
            "top_medications": top_medications,
            "distinct_doctors": distinct_doctors,
        }


def build_report_context(stats: dict[str, Any]) -> str:
    lines = [
        f"period: {stats.get('period_start') or 'n/a'} to {stats.get('period_end')}",
        f"total_prescriptions: {stats.get('total_prescriptions', 0)}",
        f"total_medications_prescribed: {stats.get('total_medications_prescribed', 0)}",
        "by_status: "
        + ", ".join(f"{key} {value}" for key, value in stats.get("by_status", {}).items()),
        "distinct_doctors: " + str(stats.get("distinct_doctors", 0)),
    ]
    for med in stats.get("top_medications", []):
        lines.append(f"- {med['medication']}: prescribed {med['count']} time(s)")
    return "\n".join(lines)


def generate_report_content(context: str) -> ReportContent:
    """One grammar-constrained call narrating the aggregated activity."""
    return structured_chat(REPORT_SYSTEM_PROMPT, REPORT_PROMPT + context, ReportContent)
