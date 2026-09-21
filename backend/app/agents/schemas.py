"""
Data shapes shared by the model layer, the prompts and the consultation
workflow. Kept separate so none of those modules import each other.

The Pydantic models below are sent to the model as the structured-output
schema, so their docstrings and field descriptions are model-facing.
Strict structured output requires every field; "unknown" is null.
"""

from dataclasses import dataclass, field
from typing import Literal

from pydantic import BaseModel, Field

Concern = Literal["acne", "pigmentation", "hair_loss", "anti_aging", "redness", "dark_spots", "other"]
Specialty = Literal["Dermatology", "Aesthetic Medicine"]
Urgency = Literal["routine", "soon", "urgent"]


class ChatTurn(BaseModel):
    role: Literal["user", "assistant"]
    content: str


class IntakeUpdate(BaseModel):
    """Details the patient stated in their LATEST message only. Null for anything they didn't state."""

    concern: Concern | None = Field(description="Main concern category")
    concern_detail: str | None = Field(description="The concern in a few words, as the patient described it")
    body_area: str | None = Field(description="Where it is, e.g. face, cheeks, scalp, back")
    duration: str | None = Field(description="How long they've had it, e.g. '6 months'")
    symptoms: list[str] | None = Field(description="Symptoms such as itching, pain, bleeding, spreading; [] if they said none")
    tried: list[str] | None = Field(description="What they've already tried; [] if nothing")
    goal: str | None = Field(description="What they hope to achieve")
    pregnancy_or_breastfeeding: bool | None
    medications_or_allergies: str | None


class Assessment(BaseModel):
    """Preliminary assessment, only when the platform says the consultation is ready. Never a diagnosis."""

    summary: str = Field(description="2-4 plain sentences for the patient: what it may be related to, and why a doctor should confirm")
    suggested_specialty: Specialty
    urgency: Urgency = Field(description="routine: book normally; soon: within a few days; urgent: within 24-48 hours")
    visit_preparation: list[str] = Field(description="2-4 things to bring or note for the appointment")
    watch_for: list[str] = Field(description="Signs that mean they should seek care sooner")


TimeOfDay = Literal["morning", "afternoon", "evening", "any"]


class BookingRequest(BaseModel):
    """What the patient wants to book, when they ask to find or book an appointment. The platform does the search."""

    specialty: Specialty | None = Field(description="Only if the patient named or clearly implied one; else null")
    city: str | None = Field(description="City or area the patient asked for, in English, e.g. 'Cairo', 'Giza'")
    date_from: str | None = Field(description="Earliest date, YYYY-MM-DD, resolved from words like 'tomorrow' using today's date")
    date_to: str | None = Field(description="Latest date, YYYY-MM-DD; same as date_from for a single day")
    time_of_day: TimeOfDay
    preferred_time: str | None = Field(description="Preferred start time, 24-hour HH:MM, e.g. '17:00'")
    doctor_name: str | None = Field(description="A specific doctor's name, if the patient asked for one")


class AssistantDraft(BaseModel):
    """Your answer to the patient, following the system instructions."""

    reply: str
    intake_update: IntakeUpdate
    assessment: Assessment | None
    booking_request: BookingRequest | None
    risk_level: Literal["low", "medium", "high"]
    cited_sources: list[int]


# --- Consultation state (computed by the platform, not the model) ------------

REQUIRED_FIELDS = ("concern", "body_area", "duration", "symptoms")
OPTIONAL_FIELDS = ("tried", "goal", "pregnancy_or_breastfeeding", "medications_or_allergies")


@dataclass(frozen=True)
class ConsultationState:
    data: IntakeUpdate
    missing: tuple[str, ...]
    # The one detail to ask about next (None when nothing required is missing).
    next_field: str | None
    # All required details are known, or the turn limit was reached.
    ready_for_assessment: bool
    assessment_done: bool
    patient_turns: int
    notes: tuple[str, ...] = field(default_factory=tuple)
    # Local date for resolving "today"/"tomorrow", e.g. "2026-09-19 (Saturday)".
    today: str = ""
    # Specialty from the accepted assessment, used when a booking request names none.
    assessed_specialty: str | None = None


def empty_intake() -> IntakeUpdate:
    return IntakeUpdate(**{name: None for name in IntakeUpdate.model_fields})
