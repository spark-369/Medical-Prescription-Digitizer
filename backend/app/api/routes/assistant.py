"""AI assistant endpoint — structured (JSON-schema) chat replies."""

from __future__ import annotations

from fastapi import APIRouter

from app.api.deps import CurrentUser, DbSession
from app.schemas.assistant import AssistantReply, ChatRequest
from app.services.chat import ASSISTANT_SYSTEM_PROMPT, assistant_reply
from app.services.insights import build_context
from app.services.prescription_service import get_prescription

router = APIRouter(prefix="/assistant", tags=["assistant"])

MAX_HISTORY = 10


@router.post("/chat", response_model=AssistantReply)
async def assistant_chat(
    payload: ChatRequest,
    user: CurrentUser,
    db: DbSession,
) -> AssistantReply:
    """Return a clean, structured assistant reply.

    When ``prescription_id`` is supplied, the reply is grounded in that
    prescription's extracted data (owner/admin visibility enforced).
    """
    context = ""
    if payload.prescription_id is not None:
        prescription = await get_prescription(
            db, payload.prescription_id, user
        )
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

    system_prompt = ASSISTANT_SYSTEM_PROMPT
    if context:
        system_prompt = f"{system_prompt}\n\nPrescription data:\n{context}"

    messages: list[dict[str, str]] = [{"role": "system", "content": system_prompt}]
    for entry in payload.history[-MAX_HISTORY:]:
        messages.append({"role": entry.role, "content": entry.content})
    messages.append({"role": "user", "content": payload.message})

    return assistant_reply(messages)
