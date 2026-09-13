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
    idempotency_key: str | None = Field(None, max_length=128)


class AppointmentUpdate(BaseModel):
    status: AppointmentStatus | None = None
    notes: str | None = None
    scheduled_start: datetime | None = None
    scheduled_end: datetime | None = None

    @model_validator(mode="after")
    def check_times(self) -> "AppointmentUpdate":
        if self.scheduled_start and self.scheduled_end and self.scheduled_end <= self.scheduled_start:
            raise ValueError("scheduled_end must be after scheduled_start")
        return self


class AppointmentRead(AppointmentBase):
    id: UUID
    status: AppointmentStatus
    idempotency_key: str | None = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
