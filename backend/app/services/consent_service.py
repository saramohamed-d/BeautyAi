"""
Patient consents for the AI chat.

Before a patient's first AI conversation they accept, once, that (1) the
chat gives preliminary guidance, not a diagnosis, and (2) their messages
are processed by an AI service. Both are stored as versioned, append-only
PatientConsent rows. Bumping CHAT_CONSENT_VERSION (when the wording
changes) asks everyone to accept again.
"""

from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ConflictError
from app.models.enums import ConsentType
from app.models.patient import PatientConsent

CHAT_CONSENT_VERSION = "chat-2026-09-v1"
CHAT_CONSENTS = (ConsentType.MEDICAL_ADVICE_DISCLAIMER, ConsentType.DATA_PROCESSING)


async def has_chat_consent(db: AsyncSession, patient_id: UUID) -> bool:
    granted = await db.scalars(
        select(PatientConsent.consent_type).where(
            PatientConsent.patient_id == patient_id,
            PatientConsent.consent_type.in_(CHAT_CONSENTS),
            PatientConsent.consent_text_version == CHAT_CONSENT_VERSION,
            PatientConsent.granted.is_(True),
            PatientConsent.revoked_at.is_(None),
        )
    )
    return set(granted.all()) == set(CHAT_CONSENTS)


async def ensure_chat_consent(db: AsyncSession, patient_id: UUID, accept_now: bool) -> None:
    """Records the consents if the patient accepts now; 409 `consent_required` if they never have."""
    if await has_chat_consent(db, patient_id):
        return
    if not accept_now:
        raise ConflictError("Please accept the AI chat terms before starting a conversation.", code="consent_required")
    now = datetime.now(timezone.utc)
    for consent_type in CHAT_CONSENTS:
        db.add(
            PatientConsent(
                patient_id=patient_id,
                consent_type=consent_type,
                granted=True,
                consent_text_version=CHAT_CONSENT_VERSION,
                granted_at=now,
            )
        )
    await db.flush()
