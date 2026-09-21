"""
The consultation checklist, owned by the platform rather than the model.

Each conversation has one Intake row. Every turn:
1. The stored details are loaded and the state is computed: which of
   REQUIRED_FIELDS are still missing and which one to ask about next
   (always in the same order), or that the assessment is due.
2. The model extracts details from the patient's latest message
   (`intake_update`); they are merged in (lists are combined, known values
   are never erased by a null).
3. An assessment from the model is accepted only when nothing required is
   missing, or after MAX_INTAKE_TURNS patient messages, so a patient
   who can't answer everything still gets guidance. A premature
   assessment is dropped. Once accepted, the intake is COMPLETE.

The accepted assessment's specialty replaces the fixed concern →
specialty lookup the app used before Sprint 9.
"""

from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.schemas import (
    OPTIONAL_FIELDS,
    REQUIRED_FIELDS,
    Assessment,
    ConsultationState,
    IntakeUpdate,
    empty_intake,
)
from app.models.conversation import Conversation, Intake
from app.models.enums import IntakeStatus

MAX_INTAKE_TURNS = 6
_LIST_FIELDS = ("symptoms", "tried")


async def get_or_create_intake(db: AsyncSession, conversation: Conversation) -> Intake:
    intake = await db.scalar(select(Intake).where(Intake.conversation_id == conversation.id))
    if intake is None:
        intake = Intake(
            conversation_id=conversation.id,
            patient_id=conversation.patient_id,
            status=IntakeStatus.IN_PROGRESS,
            structured_data={"data": empty_intake().model_dump(), "assessment": None},
            missing_fields=list(REQUIRED_FIELDS),
        )
        db.add(intake)
        await db.flush()
    return intake


def load_data(intake: Intake) -> IntakeUpdate:
    stored = (intake.structured_data or {}).get("data")
    return IntakeUpdate.model_validate(stored) if stored else empty_intake()


def missing_fields(data: IntakeUpdate) -> tuple[str, ...]:
    # For lists, [] is an answer ("no symptoms"); only None means not asked yet.
    return tuple(name for name in REQUIRED_FIELDS if getattr(data, name) in (None, ""))


def merge(data: IntakeUpdate, update: IntakeUpdate) -> IntakeUpdate:
    merged = data.model_dump()
    for name, value in update.model_dump().items():
        if value is None or value == "":
            continue
        if name in _LIST_FIELDS and merged.get(name):
            merged[name] = list(dict.fromkeys([*merged[name], *value]))
        else:
            merged[name] = value
    return IntakeUpdate.model_validate(merged)


def build_state(
    data: IntakeUpdate,
    *,
    patient_turns: int,
    assessment_done: bool,
    notes: tuple[str, ...] = (),
    today: str = "",
    assessed_specialty: str | None = None,
) -> ConsultationState:
    missing = missing_fields(data)
    return ConsultationState(
        data=data,
        missing=missing,
        next_field=missing[0] if missing else None,
        ready_for_assessment=not missing or patient_turns >= MAX_INTAKE_TURNS,
        assessment_done=assessment_done,
        patient_turns=patient_turns,
        notes=notes,
        today=today,
        assessed_specialty=assessed_specialty,
    )


def accept_assessment(
    assessment: Assessment | None, data_after: IntakeUpdate, *, patient_turns: int, assessment_done: bool
) -> Assessment | None:
    """The platform's gate: an assessment counts only when the checklist is done (or the turn limit is reached)."""
    if assessment is None or assessment_done:
        return None
    if missing_fields(data_after) and patient_turns < MAX_INTAKE_TURNS:
        return None
    return assessment


def save(intake: Intake, data: IntakeUpdate, assessment: Assessment | None) -> None:
    structured: dict[str, Any] = dict(intake.structured_data or {})
    structured["data"] = data.model_dump()
    if assessment is not None:
        structured["assessment"] = assessment.model_dump()
        structured["completed_at"] = datetime.now(timezone.utc).isoformat()
        intake.status = IntakeStatus.COMPLETE
    intake.structured_data = structured
    intake.missing_fields = list(missing_fields(data))
    intake.concern = data.concern
    intake.body_area = data.body_area
    intake.goal = data.goal


def assessed_specialty(intake: Intake) -> str | None:
    assessment = (intake.structured_data or {}).get("assessment")
    return assessment.get("suggested_specialty") if assessment else None


def summary(intake: Intake) -> dict[str, Any]:
    """What the API returns about the consultation after a turn."""
    structured = intake.structured_data or {}
    return {
        "status": intake.status.value,
        "missing_fields": intake.missing_fields or [],
        "data": structured.get("data"),
        "assessment": structured.get("assessment"),
    }


__all__ = [
    "MAX_INTAKE_TURNS", "OPTIONAL_FIELDS", "REQUIRED_FIELDS", "accept_assessment", "build_state",
    "get_or_create_intake", "load_data", "merge", "missing_fields", "save", "summary",
]
