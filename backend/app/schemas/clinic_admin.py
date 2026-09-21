from datetime import date, datetime, time
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field, model_validator

from app.models.enums import ClinicStaffRole, VerificationStatus


# --- Staff ------------------------------------------------------------------------------


class StaffBase(BaseModel):
    full_name: str | None = Field(None, max_length=255)
    email: EmailStr | None = None
    phone: str | None = Field(None, max_length=32)
    # A doctor's consultation fee at this clinic (EGP); null = the clinic
    # confirms the price and only "pay at clinic" is offered (Sprint 11).
    consultation_fee: Decimal | None = Field(None, ge=0, le=100000, decimal_places=2)


class StaffCreate(StaffBase):
    role: ClinicStaffRole = ClinicStaffRole.DOCTOR
    # Required for a doctor membership: links an existing doctor profile.
    doctor_id: UUID | None = None

    @model_validator(mode="after")
    def _name_for_non_doctors(self) -> "StaffCreate":
        if self.role != ClinicStaffRole.DOCTOR and not (self.full_name or "").strip():
            raise ValueError("full_name is required")
        return self


class StaffUpdate(StaffBase):
    is_active: bool | None = None


class StaffRead(BaseModel):
    id: UUID
    clinic_id: UUID
    doctor_id: UUID | None
    role: ClinicStaffRole
    full_name: str
    email: str | None
    phone: str | None
    consultation_fee: Decimal | None
    is_active: bool
    created_at: datetime
    # Filled in for doctors, so the team screen can show who can take bookings.
    verification_status: VerificationStatus | None = None
    specialty: str | None = None

    model_config = ConfigDict(from_attributes=True)


# --- Opening hours ----------------------------------------------------------------------


class ClinicHoursIn(BaseModel):
    # 0 = Monday … 6 = Sunday.
    weekday: int = Field(..., ge=0, le=6)
    opens_at: time
    closes_at: time
    is_closed: bool = False

    @model_validator(mode="after")
    def _closes_after_opens(self) -> "ClinicHoursIn":
        if self.closes_at <= self.opens_at:
            raise ValueError("closes_at must be after opens_at")
        return self


class ClinicHoursRead(ClinicHoursIn):
    model_config = ConfigDict(from_attributes=True)


class WeeklyHours(BaseModel):
    """The whole week at once: the screen always sends every day it knows about."""

    days: list[ClinicHoursIn] = Field(..., max_length=7)

    @model_validator(mode="after")
    def _one_row_per_day(self) -> "WeeklyHours":
        weekdays = [day.weekday for day in self.days]
        if len(set(weekdays)) != len(weekdays):
            raise ValueError("each weekday may appear only once")
        return self


# --- Services and prices ------------------------------------------------------------------


class ServiceCreate(BaseModel):
    doctor_id: UUID
    procedure_id: UUID
    price: Decimal = Field(..., ge=0, le=1000000, decimal_places=2)
    currency: str = Field("EGP", min_length=3, max_length=3)


class ServiceUpdate(BaseModel):
    price: Decimal | None = Field(None, ge=0, le=1000000, decimal_places=2)
    currency: str | None = Field(None, min_length=3, max_length=3)


class ServiceRead(BaseModel):
    id: UUID
    clinic_id: UUID
    doctor_id: UUID
    procedure_id: UUID
    price: Decimal
    currency: str
    created_at: datetime
    # Names, so the screen doesn't need a request per row.
    doctor_name: str | None = None
    procedure_name: str | None = None

    model_config = ConfigDict(from_attributes=True)


# --- Slots ----------------------------------------------------------------------------------


class SlotGenerateRequest(BaseModel):
    doctor_id: UUID
    date_from: date
    date_to: date
    # Defaults to the clinic's own slot length.
    slot_minutes: int | None = Field(None, ge=5, le=240)


class SlotGenerateResult(BaseModel):
    created: int
    # Times that already existed (booked or not): generation never moves them.
    skipped_existing: int
    closed_days: int
    slot_minutes: int


# --- Dashboard ----------------------------------------------------------------------------


class ClinicSummary(BaseModel):
    today: int
    upcoming: int
    pending: int
    doctors: int
    services: int
    open_slots: int
