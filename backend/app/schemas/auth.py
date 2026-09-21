from datetime import date, datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

from app.models.enums import Language, UserRole, UserStatus
from app.schemas.patient import PatientRead, _validate_phone
from app.schemas.validators import validate_password as _validate_password


class RegisterRequest(BaseModel):
    """Patient self-registration. Doctors and clinics get their own flows (Sprints 12-13)."""

    full_name: str = Field(..., min_length=2, max_length=255)
    email: EmailStr
    phone: str
    password: str
    date_of_birth: date | None = None
    gender: str | None = Field(None, max_length=20)
    city: str | None = Field(None, max_length=128)
    preferred_language: Language = Language.EN

    @field_validator("phone")
    @classmethod
    def validate_phone(cls, v: str) -> str:
        return _validate_phone(v)

    @field_validator("password")
    @classmethod
    def validate_password(cls, v: str) -> str:
        return _validate_password(v)


class LoginRequest(BaseModel):
    identifier: str = Field(..., min_length=3, max_length=255, description="Email address or phone number")
    password: str = Field(..., min_length=1, max_length=255)


class UserRead(BaseModel):
    id: UUID
    email: str | None
    phone: str | None
    role: UserRole
    status: UserStatus
    # Null until the address is confirmed with a code (Sprint 17).
    email_verified_at: datetime | None = None
    phone_verified_at: datetime | None = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ClinicMembership(BaseModel):
    """A clinic this user administers (role=clinic_admin)."""

    id: UUID
    name: str
    city: str

    model_config = ConfigDict(from_attributes=True)


class MeResponse(BaseModel):
    user: UserRead
    # Set when the user has a patient profile (always, for role=patient).
    patient: PatientRead | None = None
    # Set for role=doctor: the dashboard needs the verification status.
    doctor: "DoctorRead | None" = None
    # Set for role=clinic_admin: the clinics whose dashboard they can open.
    clinics: list[ClinicMembership] = []


class SessionResponse(MeResponse):
    access_token: str
    token_type: Literal["bearer"] = "bearer"
    expires_in: int = Field(..., description="Access token lifetime in seconds")


# Imported at the end: app.schemas.doctor imports this module for its
# password/phone validators, so the type is resolved after both exist.
from app.schemas.doctor import DoctorRead  # noqa: E402

MeResponse.model_rebuild()


# --- Password reset and verification (Sprint 17) ----------------------------------------------


class ForgotPasswordRequest(BaseModel):
    identifier: str = Field(..., min_length=3, max_length=255, description="Email address or phone number")


class ResetPasswordRequest(BaseModel):
    token: str = Field(..., min_length=16, max_length=255)
    password: str

    @field_validator("password")
    @classmethod
    def validate_password(cls, v: str) -> str:
        return _validate_password(v)


class VerificationRequest(BaseModel):
    channel: Literal["email", "phone"] = "email"


class VerificationConfirm(VerificationRequest):
    code: str = Field(..., min_length=4, max_length=8)


class MessageResponse(BaseModel):
    """A plain acknowledgement, for endpoints that must not reveal anything."""

    message: str


class DeleteAccountRequest(BaseModel):
    password: str = Field(..., min_length=1, max_length=255)


class DeleteAccountResponse(BaseModel):
    message: str
    # What had to be kept, de-identified, and why (docs/privacy.md).
    kept: dict[str, int]
