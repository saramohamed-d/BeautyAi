from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import ConversationChannel, ConversationStatus, Language, MessageRole


class ConversationCreate(BaseModel):
    patient_id: UUID | None = None
    channel: ConversationChannel = ConversationChannel.WEB
    language: Language = Language.AR


class ConversationUpdate(BaseModel):
    status: ConversationStatus | None = None
    patient_id: UUID | None = None


class MessageCreate(BaseModel):
    """
    Appends a raw message to a conversation. This is pure data storage —
    no LLM call, no agent reasoning. Sprint 6+ will have agents write
    messages via this same underlying service function, not this HTTP
    endpoint directly.
    """

    role: MessageRole
    content: str = Field(..., min_length=1)
    extra_data: dict | None = None


class MessageRead(BaseModel):
    id: UUID
    conversation_id: UUID
    role: MessageRole
    content: str
    extra_data: dict | None = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ConversationRead(BaseModel):
    id: UUID
    patient_id: UUID | None = None
    channel: ConversationChannel
    language: Language
    status: ConversationStatus
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ConversationDetailRead(ConversationRead):
    messages: list[MessageRead] = []
