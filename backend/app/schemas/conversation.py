from datetime import datetime
from uuid import UUID

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import ConversationChannel, ConversationStatus, Language, MessageRole, RiskLevel
from app.schemas.availability import AvailabilityRead, HoldRead
from app.schemas.clinic import ClinicRead
from app.schemas.doctor import DoctorRead


class ConversationCreate(BaseModel):
    patient_id: UUID | None = None
    channel: ConversationChannel = ConversationChannel.WEB
    language: Language = Language.AR
    # Patients must accept the AI chat terms (not a diagnosis; messages are
    # processed by an AI service) once before their first conversation.
    accept_ai_terms: bool = False


class ConversationUpdate(BaseModel):
    status: ConversationStatus | None = None
    patient_id: UUID | None = None


class MessageCreate(BaseModel):
    """
    Appends a raw message to a conversation (admins only): pure storage,
    no model call and no safety screening. Patients talk through
    POST /conversations/{id}/chat, which screens every message.
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


class ChatRequest(BaseModel):
    # Hard cap here; the configurable limit (CHAT_MAX_MESSAGE_CHARS) is enforced in the workflow.
    content: str = Field(..., min_length=1, max_length=4000)


class ChatSuggestion(BaseModel):
    specialty: str
    concern: str | None = None


class ConsultationSummary(BaseModel):
    status: str  # "in_progress" | "complete"
    missing_fields: list[str]
    data: dict | None = None
    assessment: dict | None = None


class ChatSource(BaseModel):
    document_id: UUID
    title: str
    heading: str | None = None
    language: str


class ChatTurnRead(BaseModel):
    user_message: MessageRead
    assistant_message: MessageRead
    conversation_status: ConversationStatus
    safety_level: RiskLevel
    suggestion: ChatSuggestion | None = None
    # "demo" when the offline stand-in answered (local development only).
    ai_mode: Literal["live", "demo"]
    # True when the model failed and a fallback message was sent.
    degraded: bool = False
    # Library articles the reply is based on (also in assistant_message.extra_data.sources).
    sources: list[ChatSource] = []
    # The consultation checklist after this turn (null for emergency replies).
    consultation: ConsultationSummary | None = None


class ReserveRequest(BaseModel):
    availability_id: UUID


class BookingReservation(BaseModel):
    """A held option, with everything the app needs to continue to payment."""

    hold: HoldRead
    slot: AvailabilityRead
    doctor: DoctorRead
    clinic: ClinicRead
    message: MessageRead
