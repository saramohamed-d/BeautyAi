from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.models.enums import AppointmentStatus


class AppointmentBase(BaseModel):
    patient_id: UUID
    doctor_id: UUID
    clinic_id: UUID
    procedure_id: UUID | None = None
    availability_id: UUID | None = None
    scheduled_start: datetime
    scheduled_end: datetime
    notes: str | None = None

    @model_validator(mode="after")
    def check_times(self) -> "AppointmentBase":
        if self.scheduled_end <= self.scheduled_start:
            raise ValueError("scheduled_end must be after scheduled_start")
        return self


class AppointmentCreate(AppointmentBase):
    """
    When `availability_id` is given (the normal case), the appointment's
    times always come from that slot; `scheduled_start`/`scheduled_end`
    in the request are ignored. They're only used for appointments
    staff create without a slot.
    """

    idempotency_key: str | None = Field(None, max_length=128)


class AppointmentUpdate(BaseModel):
    """
    Status and notes only. Times change through POST /appointments/{id}/reschedule,
    which moves the slot booking with them.
    """

    model_config = ConfigDict(extra="forbid")

    status: AppointmentStatus | None = None
    notes: str | None = None
    cancellation_reason: str | None = Field(None, max_length=500)

    @model_validator(mode="after")
    def reason_only_when_cancelling(self) -> "AppointmentUpdate":
        if self.cancellation_reason is not None and self.status != AppointmentStatus.CANCELLED:
            raise ValueError("cancellation_reason can only be given when cancelling")
        return self


class RescheduleRequest(BaseModel):
    availability_id: UUID


class AppointmentRead(AppointmentBase):
    id: UUID
    status: AppointmentStatus
    idempotency_key: str | None = None
    cancellable_until: datetime | None = None
    cancelled_at: datetime | None = None
    cancellation_reason: str | None = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
