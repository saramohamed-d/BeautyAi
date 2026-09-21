from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.llm import LLMProvider, get_llm
from app.rag.embeddings import Embedder, get_embedder
from app.api.deps import AdminPrincipal, Principal, require_roles
from app.api.permissions import can_access_conversation
from app.core.exceptions import ForbiddenError, NotFoundError
from app.db.session import get_db
from app.models.conversation import Conversation
from app.models.enums import ConversationChannel, ConversationStatus, UserRole
from app.schemas.common import PaginatedResponse
from app.schemas.availability import HoldRead
from app.schemas.conversation import (
    BookingReservation,
    ChatRequest,
    ReserveRequest,
    ChatTurnRead,
    ConversationCreate,
    ConversationDetailRead,
    ConversationRead,
    ConversationUpdate,
    MessageCreate,
    MessageRead,
)
from app.models.clinic import Clinic
from app.models.conversation import Message
from app.models.doctor import Doctor
from app.models.enums import MessageRole
from app.services import availability_service, consent_service, conversation_service
from app.workflows import booking_agent
from app.workflows.chat import run_chat_turn

# Conversations are between a patient and the platform. Doctors and clinic
# admins get consultation summaries through their dashboards (Sprints
# 12-13), not raw chat access.
router = APIRouter(prefix="/conversations", tags=["conversations"])
PatientOrAdmin = require_roles(UserRole.PATIENT, UserRole.PLATFORM_ADMIN)
PatientOnly = require_roles(UserRole.PATIENT)


async def _get_accessible(db: AsyncSession, principal: Principal, conversation_id: UUID, with_messages: bool = False) -> Conversation:
    conversation = await conversation_service.get_conversation(db, conversation_id, with_messages=with_messages)
    if not can_access_conversation(principal, conversation):
        raise NotFoundError(f"Conversation '{conversation_id}' not found")
    return conversation


@router.get("", response_model=PaginatedResponse[ConversationRead])
async def list_conversations(
    principal: Principal = Depends(PatientOrAdmin),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    patient_id: UUID | None = Query(None),
    status_filter: ConversationStatus | None = Query(None, alias="status"),
    channel: ConversationChannel | None = Query(None),
    db: AsyncSession = Depends(get_db),
) -> PaginatedResponse[ConversationRead]:
    if not principal.is_admin:
        if principal.patient_id is None:
            return PaginatedResponse.build([], 0, page, page_size)
        if patient_id is not None and patient_id != principal.patient_id:
            raise ForbiddenError("You can only list your own conversations")
        patient_id = principal.patient_id
    items, total = await conversation_service.list_conversations(
        db, page, page_size, patient_id=patient_id, status=status_filter, channel=channel
    )
    return PaginatedResponse.build(items, total, page, page_size)


@router.post("", response_model=ConversationRead, status_code=status.HTTP_201_CREATED)
async def create_conversation(
    payload: ConversationCreate, principal: Principal = Depends(PatientOrAdmin), db: AsyncSession = Depends(get_db)
) -> ConversationRead:
    if not principal.is_admin:
        if principal.patient_id is None or payload.patient_id not in (None, principal.patient_id):
            raise ForbiddenError("You can only start conversations for yourself")
        payload = payload.model_copy(update={"patient_id": principal.patient_id})
        await consent_service.ensure_chat_consent(db, principal.patient_id, payload.accept_ai_terms)
    return await conversation_service.create_conversation(db, payload)


@router.get("/{conversation_id}", response_model=ConversationDetailRead)
async def get_conversation(
    conversation_id: UUID, principal: Principal = Depends(PatientOrAdmin), db: AsyncSession = Depends(get_db)
) -> ConversationDetailRead:
    return await _get_accessible(db, principal, conversation_id, with_messages=True)


@router.patch("/{conversation_id}", response_model=ConversationRead)
async def update_conversation(
    conversation_id: UUID,
    payload: ConversationUpdate,
    principal: Principal = Depends(PatientOrAdmin),
    db: AsyncSession = Depends(get_db),
) -> ConversationRead:
    await _get_accessible(db, principal, conversation_id)
    if not principal.is_admin and "patient_id" in payload.model_fields_set:
        raise ForbiddenError("You can't reassign a conversation")
    return await conversation_service.update_conversation(db, conversation_id, payload)


@router.get("/{conversation_id}/messages", response_model=PaginatedResponse[MessageRead])
async def list_messages(
    conversation_id: UUID,
    principal: Principal = Depends(PatientOrAdmin),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
) -> PaginatedResponse[MessageRead]:
    await _get_accessible(db, principal, conversation_id)
    items, total = await conversation_service.list_messages(db, conversation_id, page, page_size)
    return PaginatedResponse.build(items, total, page, page_size)


@router.post("/{conversation_id}/messages", response_model=MessageRead, status_code=status.HTTP_201_CREATED)
async def add_message(
    conversation_id: UUID, payload: MessageCreate, _: AdminPrincipal, db: AsyncSession = Depends(get_db)
) -> MessageRead:
    """Admins only: raw storage without screening. Patients use /chat."""
    return await conversation_service.add_message(db, conversation_id, payload)


@router.post("/{conversation_id}/chat", response_model=ChatTurnRead)
async def chat(
    conversation_id: UUID,
    payload: ChatRequest,
    principal: Principal = Depends(PatientOnly),
    db: AsyncSession = Depends(get_db),
    llm: LLMProvider = Depends(get_llm),
    embedder: Embedder = Depends(get_embedder),
) -> ChatTurnRead:
    """
    Sends the patient's message and returns the assistant's reply. Every
    message is safety-screened first (see app/workflows/chat.py). A possible
    emergency gets a fixed emergency message and alerts the team instead of
    an AI answer. 429 `rate_limited` above CHAT_MESSAGES_PER_HOUR.
    """
    conversation = await _get_accessible(db, principal, conversation_id)
    result = await run_chat_turn(
        db, conversation=conversation, user_id=principal.user.id, content=payload.content, llm=llm, embedder=embedder
    )
    return ChatTurnRead(
        user_message=result.user_message,
        assistant_message=result.assistant_message,
        conversation_status=result.conversation.status,
        safety_level=result.safety_level,
        suggestion=result.suggestion,
        ai_mode="demo" if llm.name == "demo" else "live",
        degraded=result.degraded,
        sources=result.sources,
        consultation=result.consultation,
    )


@router.post("/{conversation_id}/booking/reserve", response_model=BookingReservation)
async def reserve_booking_option(
    conversation_id: UUID,
    payload: ReserveRequest,
    principal: Principal = Depends(PatientOnly),
    db: AsyncSession = Depends(get_db),
) -> BookingReservation:
    """
    The patient picked one of the booking agent's options: place the usual
    payment-step hold on it. Only slots the agent offered in this
    conversation are accepted (404 otherwise). Nothing is booked yet; the
    patient confirms on the payment screen. 409 `slot_unavailable` if
    someone else got it first.
    """
    conversation = await _get_accessible(db, principal, conversation_id)
    extras = (
        await db.scalars(
            select(Message.extra_data).where(
                Message.conversation_id == conversation.id, Message.role == MessageRole.ASSISTANT
            )
        )
    ).all()
    if booking_agent.offered_option(list(extras), payload.availability_id) is None:
        raise NotFoundError("That time wasn't offered in this conversation")

    slot = await availability_service.hold_slot(db, payload.availability_id, principal.patient_id)
    doctor = await db.get(Doctor, slot.doctor_id)
    clinic = await db.get(Clinic, slot.clinic_id)
    message = Message(
        conversation_id=conversation.id,
        role=MessageRole.ASSISTANT,
        content=booking_agent.hold_message(doctor.full_name, clinic.name, slot.start_time, conversation.language.value),
        extra_data={"kind": "booking_hold", "availability_id": str(slot.id), "held_until": slot.held_until.isoformat()},
    )
    db.add(message)
    await db.commit()
    await db.refresh(message)
    return BookingReservation(
        hold=HoldRead(availability_id=slot.id, held_until=slot.held_until),
        slot=slot,
        doctor=doctor,
        clinic=clinic,
        message=message,
    )
