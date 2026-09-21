from collections import defaultdict
from datetime import datetime, timezone
from typing import Literal
from uuid import UUID

from sqlalchemy import exists, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ConflictError, NotFoundError
from app.models.clinic import Clinic, ClinicStaff
from app.models.doctor import Doctor
from app.models.enums import VerificationStatus
from app.models.procedure import DoctorProcedure
from app.models.scheduling import Availability
from app.schemas.doctor import DoctorCreate, DoctorSearchResult, DoctorUpdate
from app.services.availability_service import bookable_conditions

SearchSort = Literal["soonest", "rating", "price"]


async def create_doctor(db: AsyncSession, data: DoctorCreate) -> Doctor:
    if data.email:
        existing = await db.execute(select(Doctor).where(Doctor.email == data.email))
        if existing.scalar_one_or_none() is not None:
            raise ConflictError(f"A doctor with email '{data.email}' already exists")

    doctor = Doctor(**data.model_dump())
    db.add(doctor)
    await db.commit()
    await db.refresh(doctor)
    return doctor


async def get_doctor(db: AsyncSession, doctor_id: UUID) -> Doctor:
    doctor = await db.get(Doctor, doctor_id)
    if doctor is None:
        raise NotFoundError(f"Doctor '{doctor_id}' not found")
    return doctor


async def list_doctors(
    db: AsyncSession,
    page: int,
    page_size: int,
    specialty: str | None = None,
    is_active: bool | None = None,
    verification_status: VerificationStatus | None = None,
) -> tuple[list[Doctor], int]:
    query = select(Doctor)
    if specialty:
        query = query.where(Doctor.specialty.ilike(f"%{specialty}%"))
    if is_active is not None:
        query = query.where(Doctor.is_active == is_active)
    if verification_status is not None:
        query = query.where(Doctor.verification_status == verification_status)

    total = await db.scalar(select(func.count()).select_from(query.subquery()))
    query = query.order_by(Doctor.created_at.desc()).offset((page - 1) * page_size).limit(page_size)
    result = await db.execute(query)
    return list(result.scalars().all()), total or 0


async def update_doctor(db: AsyncSession, doctor_id: UUID, data: DoctorUpdate) -> Doctor:
    doctor = await get_doctor(db, doctor_id)

    updates = data.model_dump(exclude_unset=True)
    if "email" in updates and updates["email"] and updates["email"] != doctor.email:
        existing = await db.execute(
            select(Doctor).where(Doctor.email == updates["email"], Doctor.id != doctor_id)
        )
        if existing.scalar_one_or_none() is not None:
            raise ConflictError(f"A doctor with email '{updates['email']}' already exists")

    for field, value in updates.items():
        setattr(doctor, field, value)

    await db.commit()
    await db.refresh(doctor)
    return doctor


async def search_doctors(
    db: AsyncSession,
    page: int,
    page_size: int,
    *,
    q: str | None = None,
    specialty: str | None = None,
    city: str | None = None,
    procedure_id: UUID | None = None,
    max_price: float | None = None,
    available_before: datetime | None = None,
    verified_only: bool = True,
    sort: SearchSort = "soonest",
    for_patient_id: UUID | None = None,
) -> tuple[list[DoctorSearchResult], int]:
    """
    Doctor matching on structured data (spec §13): specialty, text, city,
    procedure, price and availability, returned with each doctor's next
    bookable slot, starting price and bookable clinics.

    This is deliberately plain SQL, not AI: the Booking Agent (Sprint 10)
    calls this same function as its search tool.
    """
    now = datetime.now(timezone.utc)
    city_clinics = None
    if city:
        city_clinics = select(Clinic.id).where(Clinic.city.ilike(f"%{city}%"), Clinic.is_active.is_(True))

    # Bookable slots of the doctor in the current row (correlated subqueries).
    slot_filter = [
        Availability.doctor_id == Doctor.id,
        *bookable_conditions(now, for_patient_id),
        Availability.clinic_id.in_(city_clinics if city_clinics is not None else select(Clinic.id).where(Clinic.is_active.is_(True))),
    ]
    next_start = select(func.min(Availability.start_time)).where(*slot_filter).correlate(Doctor).scalar_subquery()

    price_filter = [DoctorProcedure.doctor_id == Doctor.id]
    if procedure_id:
        price_filter.append(DoctorProcedure.procedure_id == procedure_id)
    price_from = select(func.min(DoctorProcedure.price)).where(*price_filter).correlate(Doctor).scalar_subquery()

    query = select(Doctor, next_start.label("next_start"), price_from.label("price_from")).where(Doctor.is_active.is_(True))
    if verified_only:
        query = query.where(Doctor.verification_status == VerificationStatus.VERIFIED)
    if specialty:
        query = query.where(Doctor.specialty.ilike(f"%{specialty}%"))
    if q:
        pattern = f"%{q.strip()}%"
        query = query.where(or_(Doctor.full_name.ilike(pattern), Doctor.specialty.ilike(pattern)))
    if city_clinics is not None:
        # Practises in the city: a membership there, or slots there (booked or not).
        query = query.where(
            or_(
                exists().where(
                    ClinicStaff.doctor_id == Doctor.id,
                    ClinicStaff.is_active.is_(True),
                    ClinicStaff.clinic_id.in_(city_clinics),
                ),
                exists().where(
                    Availability.doctor_id == Doctor.id,
                    Availability.start_time > now,
                    Availability.clinic_id.in_(city_clinics),
                ),
            )
        )
    if procedure_id:
        query = query.where(price_from.is_not(None))
    if max_price is not None:
        query = query.where(price_from <= max_price)
    if available_before is not None:
        query = query.where(next_start <= available_before)

    total = await db.scalar(select(func.count()).select_from(query.subquery()))

    order = {
        "soonest": [next_start.asc().nulls_last(), Doctor.rating.desc().nulls_last()],
        "rating": [Doctor.rating.desc().nulls_last(), next_start.asc().nulls_last()],
        "price": [price_from.asc().nulls_last(), next_start.asc().nulls_last()],
    }[sort]
    rows = (await db.execute(query.order_by(*order, Doctor.id).offset((page - 1) * page_size).limit(page_size))).all()
    if not rows:
        return [], total or 0

    # Two batch queries for the whole page (not one per doctor).
    doctor_ids = [row.Doctor.id for row in rows]
    page_slot_filter = [
        Availability.doctor_id.in_(doctor_ids),
        *bookable_conditions(now, for_patient_id),
        Clinic.is_active.is_(True),
    ]
    if city:
        page_slot_filter.append(Clinic.city.ilike(f"%{city}%"))

    next_slots = (
        await db.scalars(
            select(Availability)
            .join(Clinic, Clinic.id == Availability.clinic_id)
            .where(*page_slot_filter)
            .distinct(Availability.doctor_id)
            .order_by(Availability.doctor_id, Availability.start_time)
        )
    ).all()
    next_by_doctor = {slot.doctor_id: slot for slot in next_slots}

    clinics_by_doctor: dict[UUID, list[Clinic]] = defaultdict(list)
    for doctor_id, clinic in (
        await db.execute(
            select(Availability.doctor_id, Clinic)
            .join(Clinic, Clinic.id == Availability.clinic_id)
            .where(*page_slot_filter)
            .distinct()
            .order_by(Availability.doctor_id, Clinic.name)
        )
    ).all():
        clinics_by_doctor[doctor_id].append(clinic)

    results = [
        DoctorSearchResult(
            doctor=row.Doctor,
            next_slot=next_by_doctor.get(row.Doctor.id),
            price_from=float(row.price_from) if row.price_from is not None else None,
            clinics=clinics_by_doctor.get(row.Doctor.id, []),
        )
        for row in rows
    ]
    return results, total or 0
