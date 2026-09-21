import uuid
from datetime import time

from sqlalchemy import Boolean, CheckConstraint, ForeignKey, Integer, Numeric, String, Text, Time, UniqueConstraint
from sqlalchemy import Enum as SAEnum
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base
from app.models.base import TimestampMixin, UUIDPkMixin
from app.models.enums import ClinicStaffRole


class Clinic(Base, UUIDPkMixin, TimestampMixin):
    __tablename__ = "clinics"

    name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    address: Mapped[str | None] = mapped_column(String(512), nullable=True)
    city: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    country: Mapped[str] = mapped_column(String(128), nullable=False, default="Egypt")
    # Stored as separate lat/lng columns (not PostGIS) — Sprint 1 scope is
    # "location" as a simple filter field. A geospatial type/index is only
    # worth the added dependency once Sprint 11/13 need real proximity
    # search; flagged here rather than silently deferred.
    latitude: Mapped[float | None] = mapped_column(Numeric(9, 6), nullable=True)
    longitude: Mapped[float | None] = mapped_column(Numeric(9, 6), nullable=True)
    phone: Mapped[str | None] = mapped_column(String(32), nullable=True)
    email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    # Clinic policy (spec §3: "cancel/reschedule when allowed by clinic
    # policy"): patients may cancel or reschedule until this many hours
    # before the appointment. Staff can always cancel.
    cancellation_cutoff_hours: Mapped[int] = mapped_column(
        Integer, nullable=False, default=24, server_default="24"
    )
    # Default length of one appointment slot here; used when the clinic
    # generates slots from its opening hours (Sprint 13).
    slot_duration_minutes: Mapped[int] = mapped_column(
        Integer, nullable=False, default=30, server_default="30"
    )

    staff: Mapped[list["ClinicStaff"]] = relationship(
        back_populates="clinic", cascade="all, delete-orphan"
    )
    hours: Mapped[list["ClinicHours"]] = relationship(
        back_populates="clinic", cascade="all, delete-orphan"
    )
    doctor_procedures: Mapped[list["DoctorProcedure"]] = relationship(back_populates="clinic")
    availability_slots: Mapped[list["Availability"]] = relationship(back_populates="clinic")
    appointments: Mapped[list["Appointment"]] = relationship(back_populates="clinic")

    __table_args__ = (
        CheckConstraint("cancellation_cutoff_hours >= 0", name="ck_clinics_cancellation_cutoff_non_negative"),
        CheckConstraint(
            "slot_duration_minutes BETWEEN 5 AND 240", name="ck_clinics_slot_duration_minutes_range"
        ),
    )

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Clinic id={self.id} name={self.name!r}>"


class ClinicStaff(Base, UUIDPkMixin, TimestampMixin):
    """
    Membership of a person at a clinic.

    Design decision: `doctor_id` is nullable because a staff row can
    represent a non-doctor employee (clinic admin, receptionist) who
    doesn't have a `doctors` profile. When `role == DOCTOR`, `doctor_id`
    is expected to be set.

    `user_id` links the membership to a login. A clinic admin's
    permissions are derived from these rows: they manage exactly the
    clinics where they hold an active CLINIC_ADMIN membership. A user
    can be staff at several clinics, so `user_id` is unique per clinic,
    not globally.
    """

    __tablename__ = "clinic_staff"

    clinic_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("clinics.id", ondelete="CASCADE"), nullable=False
    )
    doctor_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("doctors.id", ondelete="CASCADE"), nullable=True
    )
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )
    # For doctors: their consultation fee at this clinic (EGP). Null = the
    # clinic confirms the price; then only "pay at clinic" is offered.
    consultation_fee: Mapped[float | None] = mapped_column(Numeric(10, 2), nullable=True)
    role: Mapped[ClinicStaffRole] = mapped_column(
        SAEnum(
            ClinicStaffRole, name="clinic_staff_role", values_callable=lambda e: [m.value for m in e]
        ),
        nullable=False,
    )
    full_name: Mapped[str] = mapped_column(String(255), nullable=False)
    email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    phone: Mapped[str | None] = mapped_column(String(32), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    clinic: Mapped["Clinic"] = relationship(back_populates="staff")
    doctor: Mapped["Doctor | None"] = relationship(back_populates="clinic_memberships")

    __table_args__ = (
        UniqueConstraint("clinic_id", "doctor_id", name="uq_clinic_staff_clinic_doctor"),
        UniqueConstraint("clinic_id", "user_id", name="uq_clinic_staff_clinic_user"),
    )


class ClinicHours(Base, UUIDPkMixin, TimestampMixin):
    """
    One row per weekday: when this clinic is open (Sprint 13).

    Design decisions:

    - **Opening hours describe the clinic, not the doctors.** They're the
      template the clinic uses to generate a doctor's bookable slots
      (`POST /clinics/{id}/slots/generate`); what a patient can actually
      book is still exactly the `availability` rows, so nothing about
      booking, holds or double-booking changes.
    - **A missing row means "closed"**, and so does `is_closed`, which
      lets a clinic keep the times it usually opens while marking the day
      closed (e.g. Friday) instead of deleting and retyping them.
    - Times are local clinic time (`CLINIC_TIMEZONE`), stored without a
      zone: "we open at 10:00" doesn't move when the offset changes.
    """

    __tablename__ = "clinic_hours"

    clinic_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("clinics.id", ondelete="CASCADE"), nullable=False, index=True
    )
    # 0 = Monday … 6 = Sunday (Python's date.weekday()).
    weekday: Mapped[int] = mapped_column(Integer, nullable=False)
    opens_at: Mapped[time] = mapped_column(Time, nullable=False)
    closes_at: Mapped[time] = mapped_column(Time, nullable=False)
    is_closed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    clinic: Mapped["Clinic"] = relationship(back_populates="hours")

    __table_args__ = (
        UniqueConstraint("clinic_id", "weekday", name="uq_clinic_hours_clinic_weekday"),
        CheckConstraint("weekday BETWEEN 0 AND 6", name="ck_clinic_hours_weekday_range"),
        CheckConstraint("closes_at > opens_at", name="ck_clinic_hours_closes_after_opens"),
    )
