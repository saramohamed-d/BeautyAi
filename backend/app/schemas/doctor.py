from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from app.models.enums import VerificationStatus


class DoctorBase(BaseModel):
    full_name: str = Field(..., min_length=2, max_length=255)
    specialty: str = Field(..., min_length=2, max_length=255)
    bio: str | None = None
    years_experience: int | None = Field(None, ge=0, le=80)
    phone: str | None = Field(None, max_length=32)
    email: EmailStr | None = None


class DoctorCreate(DoctorBase):
    pass


class DoctorUpdate(BaseModel):
    full_name: str | None = Field(None, min_length=2, max_length=255)
    specialty: str | None = Field(None, min_length=2, max_length=255)
    bio: str | None = None
    years_experience: int | None = Field(None, ge=0, le=80)
    phone: str | None = Field(None, max_length=32)
    email: EmailStr | None = None
    verification_status: VerificationStatus | None = None
    is_active: bool | None = None


class DoctorRead(DoctorBase):
    id: UUID
    rating: float | None = None
    verification_status: VerificationStatus
    is_active: bool
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
