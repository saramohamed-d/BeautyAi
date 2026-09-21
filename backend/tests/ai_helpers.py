"""Builders for scripted model answers in tests."""

from app.agents.schemas import Assessment, AssistantDraft, BookingRequest, IntakeUpdate, empty_intake


def intake(**fields) -> IntakeUpdate:
    return empty_intake().model_copy(update=fields)


def assessment(**overrides) -> Assessment:
    values = {
        "summary": "This may be related to acne; a dermatologist can confirm it in person.",
        "suggested_specialty": "Dermatology",
        "urgency": "routine",
        "visit_preparation": ["When it started"],
        "watch_for": ["Fever or pus"],
    }
    values.update(overrides)
    return Assessment(**values)


def booking(**overrides) -> BookingRequest:
    values = {"specialty": None, "city": None, "date_from": None, "date_to": None, "time_of_day": "any",
              "preferred_time": None, "doctor_name": None}
    values.update(overrides)
    return BookingRequest(**values)


def draft(reply: str = "Thanks. How long have you had it?", *, risk_level: str = "low", assessment: Assessment | None = None,
          booking_request: BookingRequest | None = None, cited_sources: list[int] | None = None,
          **intake_fields) -> AssistantDraft:
    return AssistantDraft(
        reply=reply,
        intake_update=intake(**intake_fields),
        assessment=assessment,
        booking_request=booking_request,
        risk_level=risk_level,
        cited_sources=cited_sources or [],
    )
