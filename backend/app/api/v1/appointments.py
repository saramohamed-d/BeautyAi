from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import CurrentPrincipal
from app.api.permissions import can_manage_clinic, can_view_appointment
from app.core.exceptions import ForbiddenError, NotFoundError
from app.db.session import get_db
from app.models.enums import AppointmentStatus, UserRole
from app.schemas.appointment import AppointmentCreate, AppointmentRead, AppointmentUpdate, RescheduleRequest
from app.payments.gateways import PaymentGateway, get_gateway
from app.schemas.common import PaginatedResponse
from app.services import appointment_service, availability_service, payment_service

router = APIRouter(prefix="/appointments", tags=["appointments"])

# A patient may cancel or annotate their own appointment (and reschedule
# it via /reschedule), nothing else: confirming or completing it is the
# clinic's decision.
PATIENT_EDITABLE_FIELDS = {"status", "notes", "cancellation_reason"}


def _scope_filter(requested: UUID | None, own: UUID) -> UUID:
    """Forces a list filter to the caller's own id; asking for someone else's is a 403."""
    if requested is not None and requested != own:
        raise ForbiddenError("You can only list your own appointments")
    return own


@router.get("", response_model=PaginatedResponse[AppointmentRead])
async def list_appointments(
    principal: CurrentPrincipal,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    patient_id: UUID | None = Query(None),
    doctor_id: UUID | None = Query(None),
    clinic_id: UUID | None = Query(None),
    status_filter: AppointmentStatus | None = Query(None, alias="status"),
    db: AsyncSession = Depends(get_db),
) -> PaginatedResponse[AppointmentRead]:
    """Scoped by role: patients see their own, doctors theirs, clinic admins their clinics', admins all."""
    empty = PaginatedResponse.build([], 0, page, page_size)
    clinic_ids = None
    if principal.role == UserRole.PATIENT:
        if principal.patient_id is None:  # login without a linked profile
            return empty
        patient_id = _scope_filter(patient_id, principal.patient_id)
    elif principal.role == UserRole.DOCTOR:
        if principal.doctor_id is None:
            return empty
        doctor_id = _scope_filter(doctor_id, principal.doctor_id)
    elif principal.role == UserRole.CLINIC_ADMIN:
        if clinic_id is not None and clinic_id not in principal.clinic_ids:
            raise ForbiddenError("You can only list appointments at clinics you manage")
        clinic_ids = principal.clinic_ids

    items, total = await appointment_service.list_appointments(
        db, page, page_size, patient_id=patient_id, doctor_id=doctor_id, clinic_id=clinic_id,
        clinic_ids=clinic_ids, status=status_filter,
    )
    return PaginatedResponse.build(items, total, page, page_size)


@router.post("", response_model=AppointmentRead, status_code=status.HTTP_201_CREATED)
async def create_appointment(
    payload: AppointmentCreate, principal: CurrentPrincipal, db: AsyncSession = Depends(get_db)
) -> AppointmentRead:
    """Patients book for themselves; clinic admins book at their clinics; admins book anything."""
    if principal.role == UserRole.PATIENT:
        if principal.patient_id is None or payload.patient_id != principal.patient_id:
            raise ForbiddenError("You can only book appointments for yourself")
    elif principal.role == UserRole.CLINIC_ADMIN:
        if payload.clinic_id not in principal.clinic_ids:
            raise ForbiddenError("You can only book appointments at clinics you manage")
    elif not principal.is_admin:
        raise ForbiddenError("You don't have permission to book appointments")
    return await appointment_service.create_appointment(db, payload)


@router.get("/{appointment_id}", response_model=AppointmentRead)
async def get_appointment(
    appointment_id: UUID, principal: CurrentPrincipal, db: AsyncSession = Depends(get_db)
) -> AppointmentRead:
    appointment = await appointment_service.get_appointment(db, appointment_id)
    if not can_view_appointment(principal, appointment):
        raise NotFoundError(f"Appointment '{appointment_id}' not found")
    return appointment


@router.patch("/{appointment_id}", response_model=AppointmentRead)
async def update_appointment(
    appointment_id: UUID,
    payload: AppointmentUpdate,
    principal: CurrentPrincipal,
    db: AsyncSession = Depends(get_db),
    gateway: PaymentGateway = Depends(get_gateway),
) -> AppointmentRead:
    appointment = await appointment_service.get_appointment(db, appointment_id)
    if not can_view_appointment(principal, appointment):
        raise NotFoundError(f"Appointment '{appointment_id}' not found")
    is_patient = principal.role == UserRole.PATIENT
    if is_patient:
        changing_other_fields = payload.model_fields_set - PATIENT_EDITABLE_FIELDS
        if changing_other_fields or payload.status not in (None, AppointmentStatus.CANCELLED):
            raise ForbiddenError("Patients can only cancel an appointment or edit its notes")
    updated = await appointment_service.update_appointment(
        db, appointment_id, payload, actor_user_id=principal.user.id, enforce_patient_window=is_patient
    )
    if payload.status == AppointmentStatus.CANCELLED:
        # A cancelled appointment that was paid online is refunded in full.
        await payment_service.refund_for_appointment(db, appointment_id, gateway)
        await db.refresh(updated)
    return updated


@router.post("/{appointment_id}/reschedule", response_model=AppointmentRead)
async def reschedule_appointment(
    appointment_id: UUID, payload: RescheduleRequest, principal: CurrentPrincipal, db: AsyncSession = Depends(get_db)
) -> AppointmentRead:
    """
    Moves the appointment to another open slot with the same doctor. Patients
    may do this until the clinic's cancellation cutoff; the appointment then
    returns to `pending` for the clinic to confirm.
    """
    appointment = await appointment_service.get_appointment(db, appointment_id)
    if not can_view_appointment(principal, appointment):
        raise NotFoundError(f"Appointment '{appointment_id}' not found")
    if principal.role == UserRole.CLINIC_ADMIN:
        new_slot = await availability_service.get_availability(db, payload.availability_id)
        if not can_manage_clinic(principal, new_slot.clinic_id):
            raise ForbiddenError("You can only move appointments to clinics you manage")
    return await appointment_service.reschedule_appointment(
        db, appointment_id, payload.availability_id, enforce_patient_window=principal.role == UserRole.PATIENT
    )
