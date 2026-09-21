from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, model_validator


class AvailabilityBase(BaseModel):
    doctor_id: UUID
    clinic_id: UUID
    start_time: datetime
    end_time: datetime

    @model_validator(mode="after")
    def check_times(self) -> "AvailabilityBase":
        if self.end_time <= self.start_time:
            raise ValueError("end_time must be after start_time")
        return self


class AvailabilityCreate(AvailabilityBase):
    pass


class AvailabilityUpdate(BaseModel):
    start_time: datetime | None = None
    end_time: datetime | None = None
    is_booked: bool | None = None

    @model_validator(mode="after")
    def check_times(self) -> "AvailabilityUpdate":
        if self.start_time and self.end_time and self.end_time <= self.start_time:
            raise ValueError("end_time must be after start_time")
        return self


class AvailabilityRead(AvailabilityBase):
    id: UUID
    is_booked: bool
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class HoldRead(BaseModel):
    """A slot reserved for the caller during payment. Who holds a slot is never exposed to others."""

    availability_id: UUID
    held_until: datetime
