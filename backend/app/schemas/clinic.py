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
    is_active: bool | None = None


class ClinicRead(ClinicBase):
    id: UUID
    is_active: bool
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
