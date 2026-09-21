from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import RiskLevel


class SafetyEventRead(BaseModel):
    id: UUID
    conversation_id: UUID | None
    patient_id: UUID | None
    risk_level: RiskLevel
    red_flags: list | None
    requires_human: bool
    resolved: bool
    resolved_at: datetime | None
    notes: str | None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class SafetyEventUpdate(BaseModel):
    resolved: bool | None = None
    notes: str | None = Field(None, max_length=2000)
