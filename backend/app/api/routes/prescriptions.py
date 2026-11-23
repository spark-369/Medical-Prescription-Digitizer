"""Prescription endpoints: multipart upload, CRUD, SSE progress stream, stats."""

from __future__ import annotations

import json
import uuid
from collections.abc import AsyncIterator

from fastapi import APIRouter, Query, UploadFile, status
from fastapi.responses import FileResponse, StreamingResponse
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.api.deps import CurrentUser, DbSession, RedisClient
from app.core.config import get_settings
from app.core.errors import ConflictError, InferenceError, NotFoundError
from app.core.redis import event_channel
from app.models.enums import PrescriptionStatus
from app.models.prescription import Prescription
from app.schemas.prescription import (
    InsightsStatusResponse,
    PrescriptionBrief,
    PrescriptionListOut,
    PrescriptionOut,
    StatsOut,
)
from app.services.files import delete_stored_file, save_upload, validate_upload
from app.services.prescription_service import (
    create_prescription,
    delete_prescription,
    get_prescription,
    get_stats,
    list_prescriptions,
    mark_failed,
    set_status,
)
from app.workers.tasks import generate_insights, process_prescription

router = APIRouter(prefix="/prescriptions", tags=["prescriptions"])


async def _reload_with_items(db: DbSession, prescription_id: uuid.UUID) -> Prescription:
    """Re-query a prescription with items eagerly loaded (fresh worker state)."""
    result = await db.execute(
        select(Prescription)
        .options(selectinload(Prescription.items))
        .where(Prescription.id == prescription_id)
        .execution_options(populate_existing=True)
    )
    return result.scalar_one()


@router.post("", response_model=PrescriptionOut, status_code=status.HTTP_201_CREATED)
async def upload_prescription(
    db: DbSession, user: CurrentUser, file: UploadFile
) -> Prescription:
    """Accept a prescription image (multipart/form-data) and enqueue processing."""
    settings = get_settings()
    limit_bytes = settings.max_upload_size_mb * 1024 * 1024
    # limit_bytes == 0 disables the cap — read the whole stream.
    data = await file.read(limit_bytes + 1) if limit_bytes > 0 else await file.read()
    suffix = validate_upload(
        filename=file.filename or "upload",
        content_type=file.content_type or "",
        size=len(data),
    )
    await file.close()

    stored_path, _, checksum = save_upload(data, suffix)
    prescription = await create_prescription(
        db,
        owner=user,
        original_filename=file.filename or "upload",
        stored_path=stored_path,
        mime_type=file.content_type or "application/octet-stream",
        file_size=len(data),
        checksum=checksum,
    )
    # Commit BEFORE enqueueing so workers (and eager test tasks) always see the row.
    await db.commit()
    try:
        process_prescription.delay(str(prescription.id))
        prescription = await _reload_with_items(db, prescription.id)
        if prescription.status == PrescriptionStatus.UPLOADED:
            set_status(prescription, PrescriptionStatus.QUEUED)
            await db.commit()
    except Exception as exc:  # broker unreachable — fail fast, keep the upload
        mark_failed(prescription, f"Task queue unavailable: {exc}")
        await db.commit()
    return prescription


@router.get("/stats", response_model=StatsOut)
async def prescription_stats(db: DbSession, user: CurrentUser) -> StatsOut:
    total, by_status, recent = await get_stats(db, user=user)
    return StatsOut(
        total=total,
        by_status=by_status,
        recent=[PrescriptionBrief.model_validate(p) for p in recent],
    )


@router.get("", response_model=PrescriptionListOut)
async def list_prescriptions_endpoint(
    db: DbSession,
    user: CurrentUser,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    status_filter: PrescriptionStatus | None = Query(default=None, alias="status"),
    search: str | None = Query(default=None, max_length=100),
) -> PrescriptionListOut:
    prescriptions, total = await list_prescriptions(
        db,
        user=user,
        page=page,
        page_size=page_size,
        status=status_filter,
        search=search,
    )
    return PrescriptionListOut(
        items=[PrescriptionBrief.model_validate(p) for p in prescriptions],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/{prescription_id}", response_model=PrescriptionOut)
async def get_prescription_endpoint(
    prescription_id: uuid.UUID, db: DbSession, user: CurrentUser
) -> Prescription:
    return await get_prescription(db, prescription_id, user)


@router.get("/{prescription_id}/file")
async def download_prescription_file(
    prescription_id: uuid.UUID, db: DbSession, user: CurrentUser
) -> FileResponse:
    """Stream the original uploaded image (authenticated)."""
    prescription = await get_prescription(db, prescription_id, user)
    path = get_settings().resolved_upload_dir / prescription.stored_path
    if not path.is_file():
        raise NotFoundError("Stored file is missing")
    return FileResponse(
        path, media_type=prescription.mime_type, filename=prescription.original_filename
    )


@router.get("/{prescription_id}/events")
async def stream_prescription_events(
    prescription_id: uuid.UUID, db: DbSession, user: CurrentUser, redis: RedisClient
) -> StreamingResponse:
    """Server-Sent Events stream of processing progress.

    Event payloads: ``{"type": "snapshot|progress|completed|failed", ...}``.
    Heartbeat comments are emitted every ~15s so proxies keep the connection
    open. Auth works via Bearer header or ``?access_token=`` (EventSource
    cannot set custom headers).
    """
    prescription = await get_prescription(db, prescription_id, user)
    snapshot = {
        "type": "snapshot",
        "status": prescription.status,
        "progress": 100 if prescription.status == PrescriptionStatus.COMPLETED else 0,
        "error": prescription.error,
    }
    channel = event_channel(str(prescription_id))

    async def event_stream() -> AsyncIterator[str]:
        yield f"data: {json.dumps(snapshot)}\n\n"
        if prescription.status not in PrescriptionStatus.active_states():
            return
        pubsub = redis.pubsub()
        await pubsub.subscribe(channel)
        try:
            while True:
                message = await pubsub.get_message(
                    ignore_subscribe_messages=True, timeout=15.0
                )
                if message is None:
                    yield ": heartbeat\n\n"
                    continue
                data = message["data"]
                yield f"data: {data}\n\n"
                try:
                    payload = json.loads(data)
                except json.JSONDecodeError:
                    continue
                if payload.get("type") in {"completed", "failed"}:
                    break
        finally:
            try:
                await pubsub.unsubscribe(channel)
                await pubsub.aclose()
            except Exception:  # pragma: no cover - connection teardown
                pass

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache, no-transform",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.post("/{prescription_id}/reprocess", response_model=PrescriptionOut)
async def reprocess_prescription(
    prescription_id: uuid.UUID, db: DbSession, user: CurrentUser
) -> Prescription:
    prescription = await get_prescription(db, prescription_id, user)
    if prescription.status in PrescriptionStatus.active_states():
        raise ConflictError("Prescription is already queued or processing")
    set_status(prescription, PrescriptionStatus.QUEUED)
    prescription.error = None
    await db.commit()
    try:
        process_prescription.delay(str(prescription.id))
        prescription = await _reload_with_items(db, prescription_id)
    except Exception as exc:
        mark_failed(prescription, f"Task queue unavailable: {exc}")
        await db.commit()
    return prescription


@router.post("/{prescription_id}/insights", response_model=InsightsStatusResponse, status_code=202)
async def generate_prescription_insights(
    prescription_id: uuid.UUID, db: DbSession, user: CurrentUser
) -> InsightsStatusResponse:
    """Queue AI insight generation (summary, interaction check, schedule).

    Only completed prescriptions qualify. Idempotency: returns 409 while a
    generation is already pending.
    """
    prescription = await get_prescription(db, prescription_id, user)
    if prescription.status != PrescriptionStatus.COMPLETED:
        raise ConflictError("Insights can be generated only after extraction completes")
    # Re-enqueue even when "pending": a hard-killed worker can leave the
    # status stuck, and duplicate runs are idempotent (last write wins).

    prescription.ai_insights_status = "pending"
    await db.commit()
    try:
        generate_insights.delay(str(prescription.id))
    except Exception as exc:
        mark_failed_insights(prescription)
        await db.commit()
        raise InferenceError(f"Task queue unavailable: {exc}") from exc
    return InsightsStatusResponse(status="pending")


def mark_failed_insights(prescription: Prescription) -> None:
    prescription.ai_insights_status = "failed"


@router.delete("/{prescription_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_prescription_endpoint(
    prescription_id: uuid.UUID, db: DbSession, user: CurrentUser
) -> None:
    prescription = await get_prescription(db, prescription_id, user)
    stored_path = prescription.stored_path
    await delete_prescription(db, prescription)
    await db.flush()
    delete_stored_file(stored_path)
