from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.models.enums import ConversationChannel, ConversationStatus
from app.schemas.common import PaginatedResponse
from app.schemas.conversation import (
    ConversationCreate,
    ConversationDetailRead,
    ConversationRead,
    ConversationUpdate,
    MessageCreate,
    MessageRead,
)
from app.services import conversation_service

router = APIRouter(prefix="/conversations", tags=["conversations"])


@router.get("", response_model=PaginatedResponse[ConversationRead])
async def list_conversations(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    patient_id: UUID | None = Query(None),
    status_filter: ConversationStatus | None = Query(None, alias="status"),
    channel: ConversationChannel | None = Query(None),
    db: AsyncSession = Depends(get_db),
) -> PaginatedResponse[ConversationRead]:
    items, total = await conversation_service.list_conversations(
        db, page, page_size, patient_id=patient_id, status=status_filter, channel=channel
    )
    return PaginatedResponse.build(items, total, page, page_size)


@router.post("", response_model=ConversationRead, status_code=status.HTTP_201_CREATED)
async def create_conversation(payload: ConversationCreate, db: AsyncSession = Depends(get_db)) -> ConversationRead:
    return await conversation_service.create_conversation(db, payload)


@router.get("/{conversation_id}", response_model=ConversationDetailRead)
async def get_conversation(conversation_id: UUID, db: AsyncSession = Depends(get_db)) -> ConversationDetailRead:
    return await conversation_service.get_conversation(db, conversation_id, with_messages=True)


@router.patch("/{conversation_id}", response_model=ConversationRead)
async def update_conversation(
    conversation_id: UUID, payload: ConversationUpdate, db: AsyncSession = Depends(get_db)
) -> ConversationRead:
    return await conversation_service.update_conversation(db, conversation_id, payload)


@router.get("/{conversation_id}/messages", response_model=PaginatedResponse[MessageRead])
async def list_messages(
    conversation_id: UUID,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
) -> PaginatedResponse[MessageRead]:
    items, total = await conversation_service.list_messages(db, conversation_id, page, page_size)
    return PaginatedResponse.build(items, total, page, page_size)


@router.post("/{conversation_id}/messages", response_model=MessageRead, status_code=status.HTTP_201_CREATED)
async def add_message(
    conversation_id: UUID, payload: MessageCreate, db: AsyncSession = Depends(get_db)
) -> MessageRead:
    return await conversation_service.add_message(db, conversation_id, payload)
