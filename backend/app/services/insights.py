"""AI insight generation: summary, interaction check, and daily schedule.

Runs three focused, grammar-constrained Ollama calls over the *extracted*
prescription data (not the raw image), so results are deterministic-ish,
schema-valid, and cheap to regenerate.
"""

from __future__ import annotations

import re
from collections.abc import Callable
from typing import Any

from app.core.logging import get_logger
from app.schemas.insights import (
    InteractionReport,
    MedicationSchedule,
    PrescriptionInsights,
    PrescriptionSummary,
)
from app.services.ollama import structured_chat

logger = get_logger(__name__)

_TIME_RE = re.compile(r"^\d{1,2}:\d{2}$")
_DAY_PART_WORDS = {"morning", "midday", "afternoon", "evening", "night"}
_DAYS_IN_TEXT_RE = re.compile(r"days?\s*[:=]?\s*(\d+)", re.IGNORECASE)

StepCallback = Callable[[int, str], None]

SUMMARY_SYSTEM_PROMPT = (
    "You are a pharmacy assistant. You explain prescriptions in simple, "
    "patient-friendly language and output only JSON."
)

SUMMARY_PROMPT = """\
Write a patient-friendly explanation of the prescription below.

Rules:
- summary: 2-4 short sentences in plain language — what was prescribed and
  how to take it.
- key_points: 3-5 short bullets (max ~12 words each) with the most important
  things to remember.
- Use only the information in the data below; never invent medical facts.
- Output only JSON matching the schema.

Prescription data:
"""

INTERACTIONS_SYSTEM_PROMPT = (
    "You are a cautious pharmacology assistant. You output only JSON."
)

INTERACTIONS_PROMPT = """\
Review the medication list below for potential drug-drug interactions and
duplicate therapies.

Rules:
- risk_level: the overall risk — "none" for a single medication with no
  known issues, otherwise "low", "moderate" or "high".
- findings: one entry per potential interaction or duplication; an empty
  list when there are none.
  - medications: the drug names involved
  - severity: "low", "moderate", "high", or "unknown" when unsure
  - description: what the concern is
  - recommendation: what the patient should do (e.g. "ask the doctor
    before combining these")
- general_advice: one short sentence of general advice, or null.
- Only report concerns you are reasonably confident about.
- Output only JSON matching the schema.

Medication list:
"""

SCHEDULE_SYSTEM_PROMPT = (
    "You are a medication scheduling assistant. You output only JSON."
)

SCHEDULE_PROMPT = """\
Build a daily medication schedule from the data below.

Rules:
- daily_plan: exactly one entry per medication.
  - medication: the drug name
  - times: ONLY clock times in 24-hour "HH:MM" derived from the frequency
    ("3x daily" -> ["08:00", "14:00", "20:00"];
     "2x daily" -> ["08:00", "20:00"];
     "as needed" -> [] and put "as needed" in instructions)
    Never put days or instructions inside "times".
  - days: the number of days from the duration as a number (e.g. "7 days" -> 7);
    use 0 when the duration is not stated
  - instructions: special instructions such as "after meals", or null
- notes: one short sentence summarizing the schedule, or null.
- Derive times only from the frequency text; never invent doses.
- Output only JSON matching the schema.

Medication data:
"""


def build_context(data: dict[str, Any]) -> str:
    """Compact, model-friendly rendering of the extracted prescription."""
    lines: list[str] = [
        f"patient: {data.get('patient_name') or 'unknown'}",
        "patient_age: "
        f"{data.get('patient_age') if data.get('patient_age') is not None else 'unknown'}",
        f"doctor: {data.get('doctor_name') or 'unknown'}",
        f"prescribed_date: {data.get('prescribed_date') or 'unknown'}",
    ]
    for index, med in enumerate(data.get("medications", []), start=1):
        parts = [f"{index}. {med.get('medication') or 'unknown'}"]
        if med.get("dosage"):
            parts.append(f"dosage: {med['dosage']}")
        if med.get("frequency"):
            parts.append(f"frequency: {med['frequency']}")
        if med.get("duration"):
            parts.append(f"duration: {med['duration']}")
        if med.get("instructions"):
            parts.append(f"instructions: {med['instructions']}")
        lines.append(" | ".join(parts))
    if data.get("notes"):
        lines.append(f"notes: {data['notes']}")
    return "\n".join(lines)


def _sanitize_schedule(schedule: MedicationSchedule) -> MedicationSchedule:
    """Normalize the schedule the model produced.

    Small models sometimes merge other fields into ``times`` (e.g.
    ``["08:00", "days: 7", "instructions: after meals"]``) or zero out
    ``days``. Keep only valid clock times / day-part words and harvest any
    stray ``days`` / ``instructions`` values back where they belong.
    """
    for entry in schedule.daily_plan:
        clean_times: list[str] = []
        for raw_value in entry.times:
            value = raw_value.strip()
            lowered = value.lower()
            if _TIME_RE.match(lowered) or lowered in _DAY_PART_WORDS:
                clean_times.append(value)
                continue
            if lowered in {"as needed", "when needed", "prn"}:
                if not entry.instructions:
                    entry.instructions = "as needed"
                continue
            days_match = _DAYS_IN_TEXT_RE.search(lowered)
            if days_match and entry.days == 0:
                entry.days = int(days_match.group(1))
            if lowered.startswith("instructions") and ":" in value:
                recovered = value.split(":", 1)[1].strip()
                if recovered and not entry.instructions:
                    entry.instructions = recovered
        entry.times = clean_times
    return schedule


_ONLY_DAYS_RE = re.compile(r"^(?:for\s+)?(\d+)\s*days?\.?$", re.IGNORECASE)


def _normalize_schedule(
    schedule: MedicationSchedule, medication_count: int
) -> MedicationSchedule:
    """Normalize the schedule the model produced.

    Small models sometimes merge other fields into ``times`` (e.g.
    ``["08:00", "days: 7", "instructions: after meals"]``), zero out
    ``days``, or emit duplicate entries. Keep only valid clock times /
    day-part words, harvest stray values back where they belong, and
    collapse duplicates.
    """
    normalized: list = []
    seen: set[str] = set()
    for entry in schedule.daily_plan:
        key = entry.medication.strip().lower()
        if key in seen:
            continue
        seen.add(key)

        clean_times: list[str] = []
        for raw_value in entry.times:
            value = raw_value.strip()
            lowered = value.lower()
            if _TIME_RE.match(lowered) or lowered in _DAY_PART_WORDS:
                clean_times.append(value)
                continue
            if lowered in {"as needed", "when needed", "prn"}:
                if not entry.instructions:
                    entry.instructions = "as needed"
                continue
            days_match = _DAYS_IN_TEXT_RE.search(lowered)
            if days_match and entry.days == 0:
                entry.days = int(days_match.group(1))
            if lowered.startswith("instructions") and ":" in value:
                recovered = value.split(":", 1)[1].strip()
                if recovered and not entry.instructions:
                    entry.instructions = recovered
        entry.times = clean_times

        # Harvest a bare day count from the instructions text.
        if entry.days == 0 and entry.instructions:
            only_days = _ONLY_DAYS_RE.match(entry.instructions.strip())
            if only_days:
                entry.days = int(only_days.group(1))
                entry.instructions = None
        normalized.append(entry)

    # Defensive bound: dedupe may not always shrink a drifted list.
    schedule.daily_plan = normalized[:medication_count] if medication_count else normalized
    return schedule


def generate_insights_report(
    context: str,
    *,
    medication_count: int = 0,
    on_step: StepCallback | None = None,
) -> PrescriptionInsights:
    """Run the three insight passes and bundle the results."""
    step: StepCallback = on_step or (lambda _pct, _msg: None)

    step(25, "Writing patient-friendly summary")
    summary: PrescriptionSummary = structured_chat(
        SUMMARY_SYSTEM_PROMPT, SUMMARY_PROMPT + context, PrescriptionSummary
    )

    step(55, "Checking for drug interactions")
    interactions: InteractionReport = structured_chat(
        INTERACTIONS_SYSTEM_PROMPT, INTERACTIONS_PROMPT + context, InteractionReport
    )

    if medication_count > 0:
        step(85, "Building the daily schedule")
        # Never ask the grammar for more entries than the schema accepts.
        schedule_count = min(medication_count, 20)
        schedule: MedicationSchedule = structured_chat(
            SCHEDULE_SYSTEM_PROMPT,
            SCHEDULE_PROMPT + context,
            MedicationSchedule,
            # One entry per medication — the grammar cannot loop extras.
            exact_items={"daily_plan": schedule_count},
        )
        schedule = _normalize_schedule(schedule, medication_count)
    else:
        schedule = MedicationSchedule()

    logger.info(
        "Insights generated: %d key point(s), %d interaction finding(s), %d schedule entr(ies)",
        len(summary.key_points),
        len(interactions.findings),
        len(schedule.daily_plan),
    )
    return PrescriptionInsights(
        summary=summary.summary,
        key_points=summary.key_points,
        interactions=interactions,
        schedule=schedule,
    )
