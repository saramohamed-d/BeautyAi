from datetime import datetime
from uuid import UUID

from typing import Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator, model_validator

from app.schemas.patient import _validate_phone
from app.schemas.validators import validate_password as _validate_password

from app.models.enums import DocumentStatus, DocumentType, VerificationStatus
from app.schemas.availability import AvailabilityRead


# Keys of the illustrated avatars drawn by the frontend (components/ui/avatar.tsx).
AvatarKey = Literal["woman-1", "woman-2", "woman-3", "woman-4", "woman-5", "man-1", "man-2", "man-3"]


class DoctorBase(BaseModel):
    full_name: str = Field(..., min_length=2, max_length=255)
    specialty: str = Field(..., min_length=2, max_length=255)
    sub_specialty: str | None = Field(None, max_length=255)
    license_number: str | None = Field(None, max_length=128)
    medical_degree: str | None = Field(None, max_length=255)
    university: str | None = Field(None, max_length=255)
    city: str | None = Field(None, max_length=128)
    bio: str | None = None
    avatar: AvatarKey | None = None
    years_experience: int | None = Field(None, ge=0, le=80)
    phone: str | None = Field(None, max_length=32)
    email: EmailStr | None = None


class DoctorCreate(DoctorBase):
    # Admin-only endpoint: staff onboarding a doctor they've already checked
    # (e.g. an existing partner) can say so. Self sign-up always starts pending.
    verification_status: VerificationStatus = VerificationStatus.PENDING


class DoctorUpdate(BaseModel):
    full_name: str | None = Field(None, min_length=2, max_length=255)
    specialty: str | None = Field(None, min_length=2, max_length=255)
    sub_specialty: str | None = Field(None, max_length=255)
    license_number: str | None = Field(None, max_length=128)
    medical_degree: str | None = Field(None, max_length=255)
    university: str | None = Field(None, max_length=255)
    city: str | None = Field(None, max_length=128)
    bio: str | None = None
    avatar: AvatarKey | None = None
    years_experience: int | None = Field(None, ge=0, le=80)
    phone: str | None = Field(None, max_length=32)
    email: EmailStr | None = None
    verification_status: VerificationStatus | None = None
    is_active: bool | None = None


class DoctorRead(DoctorBase):
    id: UUID
    rating: float | None = None
    verification_status: VerificationStatus
    # Null until the doctor sends their application in for review.
    submitted_at: datetime | None = None
    reviewed_at: datetime | None = None
    # The admin's reason; the doctor sees it when rejected.
    verification_notes: str | None = None
    is_active: bool
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ClinicSummary(BaseModel):
    id: UUID
    name: str
    city: str

    model_config = ConfigDict(from_attributes=True)


class DoctorSearchResult(BaseModel):
    doctor: DoctorRead
    # Soonest slot bookable right now (respecting the `city` filter).
    next_slot: AvailabilityRead | None = None
    # Cheapest listed price, for `procedure_id` if given, else any procedure.
    price_from: float | None = None
    # Active clinics where this doctor has bookable slots.
    clinics: list[ClinicSummary] = []


# --- Sign-up and verification (Sprint 12) ------------------------------------------------


class DoctorRegisterRequest(BaseModel):
    """Doctor self-registration ("Join as a Doctor", spec section 4)."""

    full_name: str = Field(..., min_length=2, max_length=255)
    email: EmailStr
    phone: str
    password: str
    specialty: str = Field(..., min_length=2, max_length=255)
    sub_specialty: str | None = Field(None, max_length=255)
    license_number: str = Field(..., min_length=3, max_length=128)
    years_experience: int | None = Field(None, ge=0, le=80)
    medical_degree: str | None = Field(None, max_length=255)
    university: str | None = Field(None, max_length=255)
    city: str | None = Field(None, max_length=128)
    avatar: AvatarKey | None = None

    @field_validator("phone")
    @classmethod
    def validate_phone(cls, v: str) -> str:
        return _validate_phone(v)

    @field_validator("password")
    @classmethod
    def validate_password(cls, v: str) -> str:
        return _validate_password(v)


class DoctorDocumentRead(BaseModel):
    id: UUID
    doctor_id: UUID
    document_type: DocumentType
    status: DocumentStatus
    original_filename: str
    content_type: str
    size_bytes: int
    review_notes: str | None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class DocumentReview(BaseModel):
    status: DocumentStatus
    review_notes: str | None = Field(None, max_length=1000)


class VerificationDecision(BaseModel):
    """A platform admin's decision on a doctor's application."""

    status: Literal[VerificationStatus.VERIFIED, VerificationStatus.REJECTED]
    # Required when rejecting: the doctor is told why and can fix it.
    notes: str | None = Field(None, max_length=1000)

    @model_validator(mode="after")
    def _reason_required_for_rejection(self) -> "VerificationDecision":
        if self.status == VerificationStatus.REJECTED and not (self.notes or "").strip():
            raise ValueError("A reason is required when rejecting an application")
        return self


class DoctorApplication(BaseModel):
    """What an admin reviews: the profile plus its documents."""

    doctor: DoctorRead
    documents: list[DoctorDocumentRead] = []
