"""
Clinic admin operations (Sprint 13; docs/clinic-admin.md).

What a clinic runs day to day: its doctors, the services and prices they
offer here, the opening hours, the bookable slots generated from those
hours, and the appointments that result.

Design decisions:

- **Opening hours are a template, not a booking rule.** What a patient
  can book is still exactly the `availability` rows. Generation turns
  "Sun-Thu, 10:00-18:00, 30 minutes" into those rows; everything after
  that (holds, one active appointment per slot, cancellation windows)
  is the Sprint 6 code, untouched.
- **Generation never disturbs what exists.** It skips any slot that would
  overlap one the doctor already has at this clinic — so running it twice
  is safe, and a booked or held slot is never moved or duplicated.
- **Times are clinic-local** (`CLINIC_TIMEZONE`) and stored as UTC
  instants, so a clinic types 10:00 and patients see 10:00 in Cairo.
- **Nothing here bypasses verification**: slots can only be generated for
  a verified, active doctor (`ensure_can_practise`).
"""

from datetime import date, datetime, time, timedelta
from uuid import UUID
from zoneinfo import ZoneInfo

from sqlalchemy import and_, func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.exceptions import ConflictError, NotFoundError, ValidationAppError
from app.core.logging import get_logger
from app.models.clinic import Clinic, ClinicHours, ClinicStaff
from app.models.doctor import Doctor
from app.models.enums import AppointmentStatus, ClinicStaffRole
from app.models.procedure import DoctorProcedure, Procedure
from app.models.scheduling import Appointment, Availability
from app.schemas.clinic_admin import (
    ClinicHoursIn,
    ServiceCreate,
    ServiceUpdate,
    SlotGenerateRequest,
    StaffCreate,
    StaffUpdate,
)
from app.services import doctor_verification_service

logger = get_logger(__name__)

# How far ahead a clinic may generate in one go: a year of slots created by
# a mistyped date would be a mess to undo.
MAX_GENERATION_DAYS = 90
NOT_AT_CLINIC = "doctor_not_at_clinic"


def clinic_timezone() -> ZoneInfo:
    return ZoneInfo(get_settings().clinic_timezone)


async def get_clinic(db: AsyncSession, clinic_id: UUID) -> Clinic:
    clinic = await db.get(Clinic, clinic_id)
    if clinic is None:
        raise NotFoundError(f"Clinic '{clinic_id}' not found")
    return clinic


# --- Staff ------------------------------------------------------------------------------


async def list_staff(db: AsyncSession, clinic_id: UUID, *, include_inactive: bool = True) -> list[ClinicStaff]:
    query = select(ClinicStaff).where(ClinicStaff.clinic_id == clinic_id)
    if not include_inactive:
        query = query.where(ClinicStaff.is_active.is_(True))
    rows = await db.scalars(query.order_by(ClinicStaff.role, ClinicStaff.full_name))
    return list(rows.all())


async def get_staff(db: AsyncSession, clinic_id: UUID, staff_id: UUID) -> ClinicStaff:
    member = await db.get(ClinicStaff, staff_id)
    if member is None or member.clinic_id != clinic_id:
        raise NotFoundError(f"Staff member '{staff_id}' not found")
    return member


async def add_staff(db: AsyncSession, clinic_id: UUID, data: StaffCreate) -> ClinicStaff:
    """
    Adds someone to the clinic. For a doctor, `doctor_id` links an existing
    doctor profile (the doctor keeps their own login and verification).
    """
    doctor: Doctor | None = None
    if data.role == ClinicStaffRole.DOCTOR:
        if data.doctor_id is None:
            raise ValidationAppError("A doctor membership needs a doctor_id")
        doctor = await db.get(Doctor, data.doctor_id)
        if doctor is None:
            raise NotFoundError(f"Doctor '{data.doctor_id}' not found")
        existing = await db.scalar(
            select(ClinicStaff).where(
                ClinicStaff.clinic_id == clinic_id, ClinicStaff.doctor_id == data.doctor_id
            )
        )
        if existing is not None:
            raise ConflictError("This doctor is already on the clinic's team")

    member = ClinicStaff(
        clinic_id=clinic_id,
        doctor_id=data.doctor_id if data.role == ClinicStaffRole.DOCTOR else None,
        role=data.role,
        full_name=data.full_name or (doctor.full_name if doctor else ""),
        email=data.email or (doctor.email if doctor else None),
        phone=data.phone or (doctor.phone if doctor else None),
        consultation_fee=data.consultation_fee,
    )
    db.add(member)
    await db.commit()
    await db.refresh(member)
    return member


async def update_staff(db: AsyncSession, member: ClinicStaff, data: StaffUpdate) -> ClinicStaff:
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(member, field, value)
    await db.commit()
    await db.refresh(member)
    return member


async def remove_staff(db: AsyncSession, member: ClinicStaff) -> None:
    """
    Removes the membership. Their past appointments at this clinic stay
    (history), and so do the slots they've already published — those are
    cancelled by the clinic if needed, never silently deleted.
    """
    await db.delete(member)
    await db.commit()


# --- Opening hours ----------------------------------------------------------------------


async def get_hours(db: AsyncSession, clinic_id: UUID) -> list[ClinicHours]:
    rows = await db.scalars(
        select(ClinicHours).where(ClinicHours.clinic_id == clinic_id).order_by(ClinicHours.weekday)
    )
    return list(rows.all())


async def replace_hours(db: AsyncSession, clinic_id: UUID, days: list[ClinicHoursIn]) -> list[ClinicHours]:
    """Replaces the whole week in one transaction: the screen always sends all seven days."""
    existing = {row.weekday: row for row in await get_hours(db, clinic_id)}
    for day in days:
        row = existing.pop(day.weekday, None)
        if row is None:
            db.add(
                ClinicHours(
                    clinic_id=clinic_id,
                    weekday=day.weekday,
                    opens_at=day.opens_at,
                    closes_at=day.closes_at,
                    is_closed=day.is_closed,
                )
            )
        else:
            row.opens_at, row.closes_at, row.is_closed = day.opens_at, day.closes_at, day.is_closed
    for leftover in existing.values():  # days the clinic removed entirely
        await db.delete(leftover)
    await db.commit()
    return await get_hours(db, clinic_id)


# --- Services and prices ------------------------------------------------------------------


async def list_services(db: AsyncSession, clinic_id: UUID) -> list[DoctorProcedure]:
    rows = await db.scalars(
        select(DoctorProcedure).where(DoctorProcedure.clinic_id == clinic_id).order_by(DoctorProcedure.created_at)
    )
    return list(rows.all())


async def get_service(db: AsyncSession, clinic_id: UUID, service_id: UUID) -> DoctorProcedure:
    service = await db.get(DoctorProcedure, service_id)
    if service is None or service.clinic_id != clinic_id:
        raise NotFoundError(f"Service '{service_id}' not found")
    return service


async def add_service(db: AsyncSession, clinic_id: UUID, data: ServiceCreate) -> DoctorProcedure:
    await _ensure_doctor_at_clinic(db, clinic_id, data.doctor_id)
    if await db.get(Procedure, data.procedure_id) is None:
        raise NotFoundError(f"Procedure '{data.procedure_id}' not found")
    service = DoctorProcedure(
        clinic_id=clinic_id, doctor_id=data.doctor_id, procedure_id=data.procedure_id,
        price=data.price, currency=data.currency,
    )
    db.add(service)
    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise ConflictError("This doctor already offers this service at this clinic") from None
    await db.refresh(service)
    return service


async def update_service(db: AsyncSession, service: DoctorProcedure, data: ServiceUpdate) -> DoctorProcedure:
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(service, field, value)
    await db.commit()
    await db.refresh(service)
    return service


async def remove_service(db: AsyncSession, service: DoctorProcedure) -> None:
    await db.delete(service)
    await db.commit()


async def _ensure_doctor_at_clinic(db: AsyncSession, clinic_id: UUID, doctor_id: UUID) -> Doctor:
    doctor = await db.get(Doctor, doctor_id)
    if doctor is None:
        raise NotFoundError(f"Doctor '{doctor_id}' not found")
    member = await db.scalar(
        select(ClinicStaff).where(
            ClinicStaff.clinic_id == clinic_id,
            ClinicStaff.doctor_id == doctor_id,
            ClinicStaff.is_active.is_(True),
        )
    )
    if member is None:
        raise ConflictError("This doctor isn't on the clinic's team", code=NOT_AT_CLINIC)
    return doctor


# --- Slot generation ----------------------------------------------------------------------


def _slots_for_day(day: date, hours: ClinicHours, minutes: int, tz: ZoneInfo) -> list[tuple[datetime, datetime]]:
    """Clinic-local opening hours for one day, cut into slots, as UTC instants."""
    slots: list[tuple[datetime, datetime]] = []
    start = datetime.combine(day, hours.opens_at, tz)
    closing = datetime.combine(day, hours.closes_at, tz)
    step = timedelta(minutes=minutes)
    while start + step <= closing:
        slots.append((start.astimezone(ZoneInfo("UTC")), (start + step).astimezone(ZoneInfo("UTC"))))
        start += step
    return slots


async def generate_slots(
    db: AsyncSession, clinic: Clinic, data: SlotGenerateRequest, *, now: datetime | None = None
) -> dict:
    """
    Creates bookable slots for one doctor from the clinic's opening hours.

    Returns what happened: how many were created, how many were skipped
    because they clashed with existing slots, and which days were closed.
    Nothing existing is changed, so it's safe to run again after adding a day.
    """
    doctor = await _ensure_doctor_at_clinic(db, clinic.id, data.doctor_id)
    doctor_verification_service.ensure_can_practise(doctor)

    span = (data.date_to - data.date_from).days + 1
    if span < 1:
        raise ValidationAppError("The end date can't be before the start date")
    if span > MAX_GENERATION_DAYS:
        raise ValidationAppError(f"Please generate at most {MAX_GENERATION_DAYS} days at a time")

    tz = clinic_timezone()
    now = now or datetime.now(tz)
    minutes = data.slot_minutes or clinic.slot_duration_minutes
    hours_by_weekday = {row.weekday: row for row in await get_hours(db, clinic.id) if not row.is_closed}
    if not hours_by_weekday:
        raise ValidationAppError("Set the clinic's opening hours first", code="no_opening_hours")

    candidates: list[tuple[datetime, datetime]] = []
    closed_days = 0
    for offset in range(span):
        day = data.date_from + timedelta(days=offset)
        hours = hours_by_weekday.get(day.weekday())
        if hours is None:
            closed_days += 1
            continue
        candidates.extend(
            (start, end) for start, end in _slots_for_day(day, hours, minutes, tz) if start > now
        )

    created = 0
    skipped = 0
    for start, end in candidates:
        clash = await db.scalar(
            select(func.count())
            .select_from(Availability)
            .where(
                Availability.doctor_id == doctor.id,
                Availability.clinic_id == clinic.id,
                # Any overlap, not just an exact match.
                and_(Availability.start_time < end, Availability.end_time > start),
            )
        )
        if clash:
            skipped += 1
            continue
        db.add(Availability(doctor_id=doctor.id, clinic_id=clinic.id, start_time=start, end_time=end))
        created += 1
    await db.commit()
    logger.info(
        "clinic.slots_generated", clinic_id=str(clinic.id), doctor_id=str(doctor.id), created=created, skipped=skipped
    )
    return {
        "created": created,
        "skipped_existing": skipped,
        "closed_days": closed_days,
        "slot_minutes": minutes,
    }


async def delete_slot(db: AsyncSession, slot: Availability) -> None:
    """Removes an unbooked slot. A booked one must be cancelled through its appointment."""
    if slot.is_booked:
        raise ConflictError("This time is booked. Cancel the appointment first.", code="slot_booked")
    booked = await db.scalar(
        select(func.count())
        .select_from(Appointment)
        .where(Appointment.availability_id == slot.id, Appointment.status != AppointmentStatus.CANCELLED)
    )
    if booked:
        raise ConflictError("This time is booked. Cancel the appointment first.", code="slot_booked")
    await db.delete(slot)
    await db.commit()


# --- Dashboard summary ----------------------------------------------------------------------


async def summary(db: AsyncSession, clinic: Clinic, *, now: datetime | None = None) -> dict:
    """The numbers the dashboard opens with, in one round trip per figure."""
    tz = clinic_timezone()
    now = now or datetime.now(tz)
    local_day_start = datetime.combine(now.astimezone(tz).date(), time.min, tz)
    day_end = local_day_start + timedelta(days=1)

    async def count(model, *conditions) -> int:
        return await db.scalar(select(func.count()).select_from(model).where(*conditions)) or 0

    active = Appointment.status.in_([AppointmentStatus.PENDING, AppointmentStatus.CONFIRMED])
    return {
        "today": await count(
            Appointment,
            Appointment.clinic_id == clinic.id,
            Appointment.scheduled_start >= local_day_start,
            Appointment.scheduled_start < day_end,
            Appointment.status != AppointmentStatus.CANCELLED,
        ),
        "upcoming": await count(Appointment, Appointment.clinic_id == clinic.id, Appointment.scheduled_start >= now, active),
        "pending": await count(
            Appointment, Appointment.clinic_id == clinic.id, Appointment.status == AppointmentStatus.PENDING,
            Appointment.scheduled_start >= now,
        ),
        "doctors": await count(
            ClinicStaff,
            ClinicStaff.clinic_id == clinic.id,
            ClinicStaff.role == ClinicStaffRole.DOCTOR,
            ClinicStaff.is_active.is_(True),
        ),
        "services": await count(DoctorProcedure, DoctorProcedure.clinic_id == clinic.id),
        "open_slots": await count(
            Availability,
            Availability.clinic_id == clinic.id,
            Availability.start_time >= now,
            Availability.is_booked.is_(False),
            or_(Availability.held_until.is_(None), Availability.held_until <= now),
        ),
    }
