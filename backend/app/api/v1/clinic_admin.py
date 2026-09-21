"""
Clinic admin API (Sprint 13; docs/clinic-admin.md).

Everything here is scoped to one clinic and guarded the same way: the
clinic's own admins and platform admins only (`can_manage_clinic`).
Appointments are read and changed through the existing `/appointments`
endpoints, which already scope a clinic admin to their own clinics.
"""

from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import CurrentPrincipal, Principal
from app.api.permissions import can_manage_clinic
from app.core.exceptions import ForbiddenError, NotFoundError
from app.db.session import get_db
from app.models.clinic import Clinic, ClinicHours, ClinicStaff
from app.models.doctor import Doctor
from app.models.procedure import DoctorProcedure, Procedure
from app.schemas.clinic_admin import (
    ClinicHoursRead,
    ClinicSummary,
    ServiceCreate,
    ServiceRead,
    ServiceUpdate,
    SlotGenerateRequest,
    SlotGenerateResult,
    StaffCreate,
    StaffRead,
    StaffUpdate,
    WeeklyHours,
)
from app.services import availability_service, clinic_admin_service

router = APIRouter(prefix="/clinics", tags=["clinic admin"])


async def _managed_clinic(db: AsyncSession, principal: Principal, clinic_id: UUID) -> Clinic:
    clinic = await clinic_admin_service.get_clinic(db, clinic_id)
    if not can_manage_clinic(principal, clinic_id):
        raise ForbiddenError("You can only manage clinics you administer")
    return clinic


async def _staff_read(db: AsyncSession, members: list[ClinicStaff]) -> list[StaffRead]:
    """Adds each doctor's specialty and verification status to their membership row."""
    doctor_ids = [member.doctor_id for member in members if member.doctor_id]
    doctors = {}
    if doctor_ids:
        rows = await db.scalars(select(Doctor).where(Doctor.id.in_(doctor_ids)))
        doctors = {doctor.id: doctor for doctor in rows.all()}
    result = []
    for member in members:
        data = StaffRead.model_validate(member, from_attributes=True)
        doctor = doctors.get(member.doctor_id) if member.doctor_id else None
        result.append(
            data.model_copy(
                update={
                    "verification_status": doctor.verification_status if doctor else None,
                    "specialty": doctor.specialty if doctor else None,
                }
            )
        )
    return result


@router.get("/{clinic_id}/summary", response_model=ClinicSummary)
async def clinic_summary(
    clinic_id: UUID, principal: CurrentPrincipal, db: AsyncSession = Depends(get_db)
) -> ClinicSummary:
    """Today's and upcoming appointment counts, plus what the clinic has set up."""
    clinic = await _managed_clinic(db, principal, clinic_id)
    return ClinicSummary(**await clinic_admin_service.summary(db, clinic))


# --- Team ---------------------------------------------------------------------------------


@router.get("/{clinic_id}/staff", response_model=list[StaffRead])
async def list_staff(
    clinic_id: UUID,
    principal: CurrentPrincipal,
    include_inactive: bool = Query(True),
    db: AsyncSession = Depends(get_db),
) -> list[StaffRead]:
    await _managed_clinic(db, principal, clinic_id)
    members = await clinic_admin_service.list_staff(db, clinic_id, include_inactive=include_inactive)
    return await _staff_read(db, members)


@router.post("/{clinic_id}/staff", response_model=StaffRead, status_code=status.HTTP_201_CREATED)
async def add_staff(
    clinic_id: UUID, payload: StaffCreate, principal: CurrentPrincipal, db: AsyncSession = Depends(get_db)
) -> StaffRead:
    """Adds a doctor (by `doctor_id`) or another staff member to the clinic."""
    await _managed_clinic(db, principal, clinic_id)
    member = await clinic_admin_service.add_staff(db, clinic_id, payload)
    return (await _staff_read(db, [member]))[0]


@router.patch("/{clinic_id}/staff/{staff_id}", response_model=StaffRead)
async def update_staff(
    clinic_id: UUID,
    staff_id: UUID,
    payload: StaffUpdate,
    principal: CurrentPrincipal,
    db: AsyncSession = Depends(get_db),
) -> StaffRead:
    """Edit contact details, the consultation fee, or deactivate the membership."""
    await _managed_clinic(db, principal, clinic_id)
    member = await clinic_admin_service.get_staff(db, clinic_id, staff_id)
    updated = await clinic_admin_service.update_staff(db, member, payload)
    return (await _staff_read(db, [updated]))[0]


@router.delete("/{clinic_id}/staff/{staff_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_staff(
    clinic_id: UUID, staff_id: UUID, principal: CurrentPrincipal, db: AsyncSession = Depends(get_db)
) -> None:
    await _managed_clinic(db, principal, clinic_id)
    member = await clinic_admin_service.get_staff(db, clinic_id, staff_id)
    await clinic_admin_service.remove_staff(db, member)


# --- Opening hours --------------------------------------------------------------------------


@router.get("/{clinic_id}/hours", response_model=list[ClinicHoursRead])
async def get_hours(
    clinic_id: UUID, principal: CurrentPrincipal, db: AsyncSession = Depends(get_db)
) -> list[ClinicHours]:
    await _managed_clinic(db, principal, clinic_id)
    return await clinic_admin_service.get_hours(db, clinic_id)


@router.put("/{clinic_id}/hours", response_model=list[ClinicHoursRead])
async def replace_hours(
    clinic_id: UUID, payload: WeeklyHours, principal: CurrentPrincipal, db: AsyncSession = Depends(get_db)
) -> list[ClinicHours]:
    """Replaces the week's opening hours. Days left out are removed (= closed)."""
    await _managed_clinic(db, principal, clinic_id)
    return await clinic_admin_service.replace_hours(db, clinic_id, payload.days)


# --- Services and prices ----------------------------------------------------------------------


@router.get("/{clinic_id}/services", response_model=list[ServiceRead])
async def list_services(
    clinic_id: UUID, principal: CurrentPrincipal, db: AsyncSession = Depends(get_db)
) -> list[ServiceRead]:
    await _managed_clinic(db, principal, clinic_id)
    services = await clinic_admin_service.list_services(db, clinic_id)
    return await _services_read(db, services)


async def _services_read(db: AsyncSession, services: list[DoctorProcedure]) -> list[ServiceRead]:
    doctor_ids = {service.doctor_id for service in services}
    procedure_ids = {service.procedure_id for service in services}
    doctors = (
        {row.id: row.full_name for row in (await db.scalars(select(Doctor).where(Doctor.id.in_(doctor_ids)))).all()}
        if doctor_ids
        else {}
    )
    procedures = (
        {
            row.id: row.name
            for row in (await db.scalars(select(Procedure).where(Procedure.id.in_(procedure_ids)))).all()
        }
        if procedure_ids
        else {}
    )
    return [
        ServiceRead.model_validate(service, from_attributes=True).model_copy(
            update={
                "doctor_name": doctors.get(service.doctor_id),
                "procedure_name": procedures.get(service.procedure_id),
            }
        )
        for service in services
    ]


@router.post("/{clinic_id}/services", response_model=ServiceRead, status_code=status.HTTP_201_CREATED)
async def add_service(
    clinic_id: UUID, payload: ServiceCreate, principal: CurrentPrincipal, db: AsyncSession = Depends(get_db)
) -> ServiceRead:
    """Prices one of the catalogue's procedures for one of the clinic's doctors."""
    await _managed_clinic(db, principal, clinic_id)
    service = await clinic_admin_service.add_service(db, clinic_id, payload)
    return (await _services_read(db, [service]))[0]


@router.patch("/{clinic_id}/services/{service_id}", response_model=ServiceRead)
async def update_service(
    clinic_id: UUID,
    service_id: UUID,
    payload: ServiceUpdate,
    principal: CurrentPrincipal,
    db: AsyncSession = Depends(get_db),
) -> ServiceRead:
    await _managed_clinic(db, principal, clinic_id)
    service = await clinic_admin_service.get_service(db, clinic_id, service_id)
    updated = await clinic_admin_service.update_service(db, service, payload)
    return (await _services_read(db, [updated]))[0]


@router.delete("/{clinic_id}/services/{service_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_service(
    clinic_id: UUID, service_id: UUID, principal: CurrentPrincipal, db: AsyncSession = Depends(get_db)
) -> None:
    await _managed_clinic(db, principal, clinic_id)
    service = await clinic_admin_service.get_service(db, clinic_id, service_id)
    await clinic_admin_service.remove_service(db, service)


# --- Slots ------------------------------------------------------------------------------------


@router.post("/{clinic_id}/slots/generate", response_model=SlotGenerateResult)
async def generate_slots(
    clinic_id: UUID, payload: SlotGenerateRequest, principal: CurrentPrincipal, db: AsyncSession = Depends(get_db)
) -> SlotGenerateResult:
    """
    Turns the clinic's opening hours into bookable slots for one doctor over
    a date range (at most 90 days). Times that already exist are skipped, so
    running it again after adding a day is safe. 403 `doctor_not_verified`
    for a doctor who isn't verified yet.
    """
    clinic = await _managed_clinic(db, principal, clinic_id)
    return SlotGenerateResult(**await clinic_admin_service.generate_slots(db, clinic, payload))


@router.delete("/{clinic_id}/slots/{availability_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_slot(
    clinic_id: UUID, availability_id: UUID, principal: CurrentPrincipal, db: AsyncSession = Depends(get_db)
) -> None:
    """Removes a free slot. A booked one is refused (409 `slot_booked`) — cancel the appointment instead."""
    await _managed_clinic(db, principal, clinic_id)
    slot = await availability_service.get_availability(db, availability_id)
    if slot.clinic_id != clinic_id:
        raise NotFoundError(f"Availability slot '{availability_id}' not found")
    await clinic_admin_service.delete_slot(db, slot)
