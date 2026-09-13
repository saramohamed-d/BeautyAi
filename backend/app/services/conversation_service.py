from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.exceptions import NotFoundError
from app.models.conversation import Conversation, Message
from app.models.enums import ConversationChannel, ConversationStatus
from app.models.patient import Patient
from app.schemas.conversation import ConversationCreate, ConversationUpdate, MessageCreate


async def create_conversation(db: AsyncSession, data: ConversationCreate) -> Conversation:
    if data.patient_id:
        patient = await db.get(Patient, data.patient_id)
        if patient is None:
            raise NotFoundError(f"Patient '{data.patient_id}' not found")

    conversation = Conversation(**data.model_dump())
    db.add(conversation)
    await db.commit()
    await db.refresh(conversation)
    return conversation


async def get_conversation(db: AsyncSession, conversation_id: UUID, with_messages: bool = False) -> Conversation:
    query = select(Conversation).where(Conversation.id == conversation_id)
    if with_messages:
        query = query.options(selectinload(Conversation.messages))
    result = await db.execute(query)
    conversation = result.scalar_one_or_none()
    if conversation is None:
        raise NotFoundError(f"Conversation '{conversation_id}' not found")
    return conversation


async def list_conversations(
    db: AsyncSession,
    page: int,
    page_size: int,
    patient_id: UUID | None = None,
    status: ConversationStatus | None = None,
    channel: ConversationChannel | None = None,
) -> tuple[list[Conversation], int]:
    query = select(Conversation)
    if patient_id:
        query = query.where(Conversation.patient_id == patient_id)
    if status is not None:
        query = query.where(Conversation.status == status)
    if channel is not None:
        query = query.where(Conversation.channel == channel)

    total = await db.scalar(select(func.count()).select_from(query.subquery()))
    query = query.order_by(Conversation.created_at.desc()).offset((page - 1) * page_size).limit(page_size)
    result = await db.execute(query)
    return list(result.scalars().all()), total or 0


async def update_conversation(db: AsyncSession, conversation_id: UUID, data: ConversationUpdate) -> Conversation:
    conversation = await get_conversation(db, conversation_id)
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(conversation, field, value)
    await db.commit()
    await db.refresh(conversation)
    return conversation


async def list_messages(db: AsyncSession, conversation_id: UUID, page: int, page_size: int) -> tuple[list[Message], int]:
    await get_conversation(db, conversation_id)  # 404 if conversation doesn't exist

    query = select(Message).where(Message.conversation_id == conversation_id)
    total = await db.scalar(select(func.count()).select_from(query.subquery()))
    query = query.order_by(Message.created_at.asc()).offset((page - 1) * page_size).limit(page_size)
    result = await db.execute(query)
    return list(result.scalars().all()), total or 0


async def add_message(db: AsyncSession, conversation_id: UUID, data: MessageCreate) -> Message:
    await get_conversation(db, conversation_id)  # 404 if conversation doesn't exist

    message = Message(conversation_id=conversation_id, **data.model_dump())
    db.add(message)
    await db.commit()
    await db.refresh(message)
    return message
