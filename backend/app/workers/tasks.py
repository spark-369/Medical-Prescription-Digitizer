"""Celery tasks — the prescription digitization pipeline.

Pipeline: load file -> Ollama vision inference (structured output) ->
persist extraction -> publish progress events on Redis pub/sub, which the
API's SSE endpoint streams to the browser.
"""

from __future__ import annotations

import base64
import json
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from app.core.config import get_settings
from app.core.logging import get_logger
from app.core.redis import event_channel, get_sync_redis, insights_event_channel
from app.db.session import get_sync_session_factory
from app.models.ai_report import AiReport
from app.models.enums import PrescriptionStatus
from app.models.prescription import Prescription
from app.services.inference import (
    PrescriptionExtraction,
    prepare_image_bytes,
    run_inference,
)
from app.services.insights import build_context, generate_insights_report
from app.services.prescription_service import apply_extraction, mark_failed, set_status
from app.services.report_service import (
    build_report_context,
    collect_activity,
    generate_report_content,
)
from app.workers.celery_app import celery_app

logger = get_logger(__name__)


def _publish(prescription_id: str, payload: dict[str, Any]) -> None:
    try:
        get_sync_redis().publish(
            event_channel(prescription_id), json.dumps(payload)
        )
    except Exception:  # pragma: no cover - broker hiccup must not kill the task
        logger.warning(
            "Could not publish progress event for %s", prescription_id, exc_info=True
        )


@celery_app.task(
    name="prescriptions.process",
    bind=True,
    max_retries=0,
    soft_time_limit=600,
    time_limit=660,
)
def process_prescription(self, prescription_id: str) -> dict[str, Any]:  # noqa: ARG001
    settings = get_settings()
    session_factory = get_sync_session_factory()

    _publish(
        prescription_id,
        {"type": "status", "status": "processing", "progress": 5, "message": "Task started"},
    )
    try:
        # --- 1. Load file bytes (short-lived DB session) -------------------
        with session_factory() as session:
            prescription = session.get(Prescription, UUID(prescription_id))
            if prescription is None:
                logger.error("Prescription %s not found", prescription_id)
                _publish(
                    prescription_id,
                    {"type": "failed", "status": "failed", "progress": 100, "error": "not_found"},
                )
                return {"status": "failed", "error": "not_found"}
            set_status(prescription, PrescriptionStatus.PROCESSING)
            session.commit()

            stored = settings.resolved_upload_dir / prescription.stored_path
            if not stored.is_file():
                raise FileNotFoundError(f"Stored file is missing: {prescription.stored_path}")
            image_bytes = prepare_image_bytes(stored.read_bytes())
            image_b64 = base64.b64encode(image_bytes).decode("ascii")

        # --- 2. Vision inference (no DB connection held) --------------------
        _publish(
            prescription_id,
            {"type": "progress", "progress": 35, "message": "Running vision model"},
        )
        extraction: PrescriptionExtraction = run_inference(image_b64)

        # --- 3. Persist extraction ------------------------------------------
        _publish(
            prescription_id,
            {"type": "progress", "progress": 80, "message": "Persisting extraction"},
        )
        with session_factory() as session:
            prescription = session.get(Prescription, UUID(prescription_id))
            if prescription is None:  # pragma: no cover - deleted mid-run
                return {"status": "failed", "error": "not_found"}
            apply_extraction(
                prescription,
                extraction,
                model_name=settings.ollama_model,
                raw_output=json.dumps(extraction.model_dump(mode="json")),
            )
            session.commit()
            medication_count = len(extraction.medications)

        _publish(
            prescription_id,
            {
                "type": "completed",
                "status": "completed",
                "progress": 100,
                "message": f"Extracted {medication_count} medication(s)",
            },
        )
        return {"status": "completed", "id": prescription_id, "medications": medication_count}

    except Exception as exc:
        logger.exception("Processing failed for prescription %s", prescription_id)
        try:
            with session_factory() as session:
                prescription = session.get(Prescription, UUID(prescription_id))
                if prescription is not None:
                    mark_failed(prescription, str(exc))
                    session.commit()
        except Exception:  # pragma: no cover
            logger.exception("Could not persist failure state for %s", prescription_id)
        _publish(
            prescription_id,
            {"type": "failed", "status": "failed", "progress": 100, "error": str(exc)[:500]},
        )
        return {"status": "failed", "error": str(exc)[:500]}


@celery_app.task(
    name="prescriptions.generate_insights",
    bind=True,
    max_retries=0,
    soft_time_limit=300,
    time_limit=360,
)
def generate_insights(self, prescription_id: str) -> dict[str, Any]:  # noqa: ARG001
    """Generate AI insights (summary / interaction check / schedule).

    Runs three focused grammar-constrained Ollama calls over the extracted
    prescription data and stores the bundle on the row.
    """
    settings = get_settings()
    session_factory = get_sync_session_factory()
    channel = insights_event_channel(prescription_id)

    def publish_progress(progress: int, message: str) -> None:
        _publish(channel, {"type": "progress", "progress": progress, "message": message})

    try:
        # --- 1. Load the extraction context --------------------------------
        with session_factory() as session:
            prescription = session.get(Prescription, UUID(prescription_id))
            if prescription is None:
                logger.error("Prescription %s not found for insights", prescription_id)
                _publish(
                    channel,
                    {"type": "insights_failed", "error": "not_found"},
                )
                return {"status": "failed", "error": "not_found"}

            context = build_context(
                {
                    "patient_name": prescription.patient_name,
                    "patient_age": prescription.patient_age,
                    "doctor_name": prescription.doctor_name,
                    "prescribed_date": prescription.prescribed_date,
                    "notes": prescription.notes,
                    "medications": [
                        {
                            "medication": item.medication,
                            "dosage": item.dosage,
                            "frequency": item.frequency,
                            "duration": item.duration,
                            "instructions": item.instructions,
                        }
                        for item in prescription.items
                    ],
                }
            )
            prescription.ai_insights_status = "pending"
            session.commit()

        # --- 2. Run the three AI passes -------------------------------------
        report = generate_insights_report(
            context,
            medication_count=len(prescription.items),
            on_step=lambda progress, message: publish_progress(progress, message),
        )

        # --- 3. Persist -------------------------------------------------------
        with session_factory() as session:
            prescription = session.get(Prescription, UUID(prescription_id))
            if prescription is None:  # pragma: no cover - deleted mid-run
                return {"status": "failed", "error": "not_found"}
            prescription.ai_insights = report.model_dump(mode="json")
            prescription.ai_insights_model = settings.ollama_model
            prescription.ai_insights_generated_at = datetime.now(UTC)
            prescription.ai_insights_status = "ready"
            session.commit()

        _publish(
            channel,
            {"type": "insights_completed", "progress": 100, "message": "AI insights ready"},
        )
        return {"status": "completed", "id": prescription_id}

    except Exception as exc:
        logger.exception("Insight generation failed for %s", prescription_id)
        try:
            with session_factory() as session:
                prescription = session.get(Prescription, UUID(prescription_id))
                if prescription is not None:
                    prescription.ai_insights_status = "failed"
                    session.commit()
        except Exception:  # pragma: no cover
            logger.exception("Could not persist insight failure for %s", prescription_id)
        _publish(
            channel,
            {"type": "insights_failed", "error": str(exc)[:300]},
        )
        return {"status": "failed", "error": str(exc)[:500]}




@celery_app.task(
    name="reports.generate_report",
    bind=True,
    max_retries=0,
    soft_time_limit=300,
    time_limit=360,
)
def generate_report(self, report_id: str) -> dict[str, Any]:  # noqa: ARG001
    """Generate an AI analytics report over a user's prescription history."""
    settings = get_settings()
    session_factory = get_sync_session_factory()

    try:
        with session_factory() as session:
            report = session.get(AiReport, UUID(report_id))
            if report is None:
                logger.error("Report %s not found", report_id)
                return {"status": "failed", "error": "not_found"}
            user_id = report.user_id

        stats = collect_activity(session_factory, user_id)
        context = build_report_context(stats)
        content = generate_report_content(context)

        with session_factory() as session:
            report = session.get(AiReport, UUID(report_id))
            if report is None:  # pragma: no cover - deleted mid-run
                return {"status": "failed", "error": "not_found"}
            report.content = content.model_dump(mode="json")
            report.model = settings.ollama_model
            report.status = "ready"
            report.error = None
            session.commit()

        logger.info("Report %s generated", report_id)
        return {"status": "completed", "id": report_id}

    except Exception as exc:
        logger.exception("Report generation failed for %s", report_id)
        try:
            with session_factory() as session:
                report = session.get(AiReport, UUID(report_id))
                if report is not None:
                    report.status = "failed"
                    report.error = str(exc)[:500]
                    session.commit()
        except Exception:  # pragma: no cover
            logger.exception("Could not persist report failure for %s", report_id)
        return {"status": "failed", "error": str(exc)[:500]}
