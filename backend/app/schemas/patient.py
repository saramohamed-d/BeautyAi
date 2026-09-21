import re
from datetime import date, datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

from app.models.enums import Language

PHONE_PATTERN = re.compile(r"^\+?[0-9]{8,15}$")


def _validate_phone(value: str) -> str:
    if not PHONE_PATTERN.match(value):
        raise ValueError("phone must be 8-15 digits, optionally prefixed with '+'")
    return value


class PatientBase(BaseModel):
    full_name: str = Field(..., min_length=2, max_length=255)
    phone: str
    email: EmailStr | None = None
    date_of_birth: date | None = None
    gender: str | None = Field(None, max_length=20)
    city: str | None = Field(None, max_length=128)
    preferred_language: Language = Language.AR

    @field_validator("phone")
    @classmethod
    def validate_phone(cls, v: str) -> str:
        return _validate_phone(v)


class PatientCreate(PatientBase):
    pass


class PatientUpdate(BaseModel):
    full_name: str | None = Field(None, min_length=2, max_length=255)
    email: EmailStr | None = None
    date_of_birth: date | None = None
    gender: str | None = Field(None, max_length=20)
    city: str | None = Field(None, max_length=128)
    preferred_language: Language | None = None
    # Which channels this patient wants (Sprint 15).
    notify_email: bool | None = None
    notify_sms: bool | None = None
    notify_whatsapp: bool | None = None


class PatientRead(PatientBase):
    id: UUID
    # Channel preferences, so the account screen can show the toggles.
    notify_email: bool = True
    notify_sms: bool = True
    notify_whatsapp: bool = False
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
