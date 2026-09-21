"""
Ownership rules: which records a given caller may see or change.

Role checks ("only admins may create procedures") are done with
`require_roles` in app/api/deps.py. The functions here answer the finer
question "is this particular record yours?".

Convention: when a caller asks for a specific record they may not see,
routes answer 404, not 403, so the API doesn't confirm that someone
else's appointment or patient record exists. 403 is used when the
caller may see the record but not perform the action (e.g. a doctor
editing their own verification status).
"""

from uuid import UUID

from sqlalchemy import exists, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import Principal
from app.models.conversation import Conversation
from app.models.scheduling import Appointment


def can_manage_clinic(principal: Principal, clinic_id: UUID) -> bool:
    return principal.is_admin or clinic_id in principal.clinic_ids


def can_manage_schedule(principal: Principal, doctor_id: UUID, clinic_id: UUID) -> bool:
    """Admins, the clinic's admins, and the doctor themself manage a doctor's slots at a clinic."""
    return (
        principal.is_admin
        or clinic_id in principal.clinic_ids
        or (principal.doctor_id is not None and principal.doctor_id == doctor_id)
    )


def can_view_appointment(principal: Principal, appointment: Appointment) -> bool:
    return (
        principal.is_admin
        or (principal.patient_id is not None and appointment.patient_id == principal.patient_id)
        or (principal.doctor_id is not None and appointment.doctor_id == principal.doctor_id)
        or appointment.clinic_id in principal.clinic_ids
    )


async def can_view_patient(db: AsyncSession, principal: Principal, patient_id: UUID) -> bool:
    """The patient themself, admins, and doctors/clinic admins who have an appointment with them."""
    if principal.is_admin or principal.patient_id == patient_id:
        return True
    if principal.doctor_id is None and not principal.clinic_ids:
        return False
    care_team = []
    if principal.doctor_id is not None:
        care_team.append(Appointment.doctor_id == principal.doctor_id)
    if principal.clinic_ids:
        care_team.append(Appointment.clinic_id.in_(principal.clinic_ids))
    return bool(await db.scalar(select(exists().where(Appointment.patient_id == patient_id, or_(*care_team)))))


def can_access_conversation(principal: Principal, conversation: Conversation) -> bool:
    """Conversations are private between the patient and the platform (and its admins)."""
    return principal.is_admin or (
        principal.patient_id is not None and conversation.patient_id == principal.patient_id
    )
