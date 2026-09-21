from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import IntakeStatus


class IntakeCreate(BaseModel):
    conversation_id: UUID
    patient_id: UUID | None = None
    concern: str | None = Field(None, max_length=255)
    body_area: str | None = Field(None, max_length=255)
    goal: str | None = Field(None, max_length=255)
    structured_data: dict | None = None
    missing_fields: list[str] | None = None


class IntakeUpdate(BaseModel):
    concern: str | None = Field(None, max_length=255)
    body_area: str | None = Field(None, max_length=255)
    goal: str | None = Field(None, max_length=255)
    structured_data: dict | None = None
    missing_fields: list[str] | None = None
    status: IntakeStatus | None = None


class IntakeRead(BaseModel):
    id: UUID
    conversation_id: UUID
    patient_id: UUID | None = None
    concern: str | None = None
    body_area: str | None = None
    goal: str | None = None
    structured_data: dict | None = None
    missing_fields: list | None = None
    status: IntakeStatus
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
