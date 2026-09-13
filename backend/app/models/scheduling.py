import uuid
from datetime import datetime

from sqlalchemy import Boolean, CheckConstraint, DateTime, ForeignKey, Index, String, Text, UniqueConstraint
from sqlalchemy import Enum as SAEnum
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base
from app.models.base import TimestampMixin, UUIDPkMixin
from app.models.enums import AppointmentStatus


class Availability(Base, UUIDPkMixin, TimestampMixin):
    """
    A single bookable time slot for a doctor at a clinic.

    Design decision: slots are pre-materialized rows (one row per
    bookable interval), not computed on the fly from a recurring
    schedule. This is simpler to query ("all open slots for doctor X
    next week" is one indexed SELECT) and simpler to lock at booking time
    (one row to mark `is_booked=True`). The trade-off — a background job
    must generate future slots from doctors' recurring schedules — is a
    Sprint 13 concern; Sprint 1 only models the resulting row shape.
    """

    __tablename__ = "availability"

    doctor_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("doctors.id", ondelete="CASCADE"), nullable=False
    )
    clinic_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("clinics.id", ondelete="CASCADE"), nullable=False
    )
    start_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    end_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    is_booked: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    doctor: Mapped["Doctor"] = relationship(back_populates="availability_slots")
    clinic: Mapped["Clinic"] = relationship(back_populates="availability_slots")
    appointment: Mapped["Appointment | None"] = relationship(
        back_populates="availability", uselist=False
    )

    __table_args__ = (
        Index("ix_availability_doctor_id_start_time", "doctor_id", "start_time"),
        Index("ix_availability_clinic_id_start_time", "clinic_id", "start_time"),
        CheckConstraint("end_time > start_time", name="ck_availability_end_after_start"),
    )


class Appointment(Base, UUIDPkMixin, TimestampMixin):
    """
    A confirmed (or pending/cancelled) booking.

    `availability_id` is UNIQUE — a slot can back at most one appointment,
    which is the database-level guarantee against double-booking (see
    architecture notes). `scheduled_start`/`scheduled_end` are
    denormalized copies of the slot's times at booking time: appointment
    history must stay accurate even if the `availability` row is later
    deleted or its parent doctor's schedule changes.

    `idempotency_key` backs Sprint 14's booking tool: the client (or
    LangGraph tool call) generates a key per booking attempt; retrying
    the same attempt (e.g. after a network timeout) reuses the same key,
    and the UNIQUE constraint makes a duplicate INSERT fail instead of
    creating a second appointment.
    """

    __tablename__ = "appointments"

    patient_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("patients.id", ondelete="CASCADE"), nullable=False
    )
    doctor_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("doctors.id", ondelete="RESTRICT"), nullable=False
    )
    clinic_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("clinics.id", ondelete="RESTRICT"), nullable=False
    )
    procedure_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("procedures.id", ondelete="SET NULL"), nullable=True
    )
    availability_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("availability.id", ondelete="SET NULL"),
        nullable=True,
        unique=True,
    )
    status: Mapped[AppointmentStatus] = mapped_column(
        SAEnum(
            AppointmentStatus,
            name="appointment_status",
            values_callable=lambda e: [m.value for m in e],
        ),
        nullable=False,
        default=AppointmentStatus.PENDING,
        index=True,
    )
    scheduled_start: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    scheduled_end: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    idempotency_key: Mapped[str | None] = mapped_column(String(128), unique=True, nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    patient: Mapped["Patient"] = relationship(back_populates="appointments")
    doctor: Mapped["Doctor"] = relationship(back_populates="appointments")
    clinic: Mapped["Clinic"] = relationship(back_populates="appointments")
    availability: Mapped["Availability | None"] = relationship(back_populates="appointment")

    __table_args__ = (
        Index("ix_appointments_patient_id", "patient_id"),
        Index("ix_appointments_doctor_id_scheduled_start", "doctor_id", "scheduled_start"),
        CheckConstraint(
            "scheduled_end > scheduled_start", name="ck_appointments_end_after_start"
        ),
    )
