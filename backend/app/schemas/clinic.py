from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class ClinicBase(BaseModel):
    name: str = Field(..., min_length=2, max_length=255)
    description: str | None = None
    address: str | None = Field(None, max_length=512)
    city: str = Field(..., min_length=2, max_length=128)
    country: str = Field("Egypt", max_length=128)
    latitude: float | None = Field(None, ge=-90, le=90)
    longitude: float | None = Field(None, ge=-180, le=180)
    phone: str | None = Field(None, max_length=32)
    email: EmailStr | None = None
    # Patients may cancel/reschedule until this many hours before the appointment.
    cancellation_cutoff_hours: int = Field(24, ge=0, le=720)
    # Default length of one slot when generating from the opening hours (Sprint 13).
    slot_duration_minutes: int = Field(30, ge=5, le=240)


class ClinicCreate(ClinicBase):
    pass


class ClinicUpdate(BaseModel):
    name: str | None = Field(None, min_length=2, max_length=255)
    description: str | None = None
    address: str | None = Field(None, max_length=512)
    city: str | None = Field(None, min_length=2, max_length=128)
    country: str | None = Field(None, max_length=128)
    latitude: float | None = Field(None, ge=-90, le=90)
    longitude: float | None = Field(None, ge=-180, le=180)
    phone: str | None = Field(None, max_length=32)
    email: EmailStr | None = None
    cancellation_cutoff_hours: int | None = Field(None, ge=0, le=720)
    slot_duration_minutes: int | None = Field(None, ge=5, le=240)
    is_active: bool | None = None


class ClinicRead(ClinicBase):
    id: UUID
    is_active: bool
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
