"""
One patient chat turn: safety screen → model → output checks → persist.

The order is deliberate:
1. Limits (length, messages per hour) protect cost and abuse.
2. The deterministic safety screen (workflows/safety.py) runs before any
   model call. A possible emergency never reaches the model: the patient
   gets a fixed emergency message and a human is alerted.
3. The patient's message is committed before the (slow) model call, so it
   is never lost if the model times out.
4. The consultation checklist (workflows/consultation.py) tells the model
   which detail to ask about next, stores what the patient said, and only
   accepts a preliminary assessment once the checklist is complete.
5. Relevant passages from the approved knowledge library are retrieved
   (app/rag/retrieval.py) and given to the model as numbered references.
   Only citations that point at a passage actually given are kept, and
   they become the "Sources" shown under the reply.
6. The model's answer is structured (agents/schemas.py). Fixed cautions are
   appended in code, so they appear whatever the model writes, and the
   model's own risk rating is a second safety line that can escalate.
7. If the model or the retrieval fails, the patient still gets an answer
   (a polite fallback, or an answer without library references).
"""

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.llm import MAX_REPLY_CHARS, LLMError, LLMProvider, anonymous_user_ref
from app.agents.schemas import AssistantDraft, ChatTurn
from app.core.config import get_settings
from app.core.exceptions import ConflictError, TooManyRequestsError, ValidationAppError
from app.core.logging import get_logger
from app.models.audit import SafetyEvent
from app.models.conversation import Conversation, Message
from app.models.enums import ConversationStatus, MessageRole, RiskLevel
from app.prompts.chat import PROMPT_VERSION, system_prompt
from app.rag.embeddings import Embedder
from app.rag.retrieval import search as search_knowledge
from app.rag.types import Reference
from app.models.enums import IntakeStatus
from app.workflows import booking_agent, consultation
from app.workflows.safety import SafetyAssessment, assess, caution_message, emergency_message, is_arabic

logger = get_logger(__name__)

_FALLBACK = {
    "en": "Sorry, I'm having trouble answering right now. Please try again in a moment, or browse doctors directly.",
    "ar": "آسفة، عندي مشكلة في الرد دلوقتي. حاولي تاني بعد شوية، أو تصفّحي الأطباء مباشرة.",
}
_RANK = {RiskLevel.LOW: 0, RiskLevel.MEDIUM: 1, RiskLevel.HIGH: 2}
REFERENCE_LIMIT = 4
# Short follow-ups ("about 6 months") retrieve nothing on their own, so the
# previous patient message is searched with them.
SHORT_MESSAGE_WORDS = 6


@dataclass
class ChatTurnResult:
    user_message: Message
    assistant_message: Message
    conversation: Conversation
    safety_level: RiskLevel
    suggestion: dict[str, Any] | None
    degraded: bool
    sources: list[dict[str, Any]]
    consultation: dict[str, Any] | None


def _safety_payload(level: RiskLevel, flags: tuple[str, ...] | list[str]) -> dict[str, Any]:
    return {"level": level.value, "flags": list(flags)}


async def _check_limits(db: AsyncSession, patient_id: UUID, text: str) -> None:
    settings = get_settings()
    if not text:
        raise ValidationAppError("Message can't be empty")
    if len(text) > settings.chat_max_message_chars:
        raise ValidationAppError(f"Message is too long (max {settings.chat_max_message_chars} characters)")
    since = datetime.now(timezone.utc) - timedelta(hours=1)
    sent = await db.scalar(
        select(func.count(Message.id))
        .join(Conversation, Conversation.id == Message.conversation_id)
        .where(Conversation.patient_id == patient_id, Message.role == MessageRole.USER, Message.created_at >= since)
    )
    if (sent or 0) >= settings.chat_messages_per_hour:
        raise TooManyRequestsError("You've sent a lot of messages in the last hour. Please try again a little later.")


async def _history(db: AsyncSession, conversation_id: UUID) -> list[ChatTurn]:
    rows = (
        await db.scalars(
            select(Message)
            .where(Message.conversation_id == conversation_id, Message.role.in_([MessageRole.USER, MessageRole.ASSISTANT]))
            .order_by(Message.created_at.desc(), Message.id.desc())
            .limit(get_settings().chat_history_messages)
        )
    ).all()
    return [ChatTurn(role=m.role.value, content=m.content) for m in reversed(rows)]


async def _retrieve(db: AsyncSession, history: list[ChatTurn], lang: str, embedder: Embedder) -> list[Reference]:
    user_turns = [turn.content for turn in history if turn.role == "user"]
    if not user_turns:
        return []
    query = user_turns[-1]
    if len(query.split()) < SHORT_MESSAGE_WORDS and len(user_turns) > 1:
        query = f"{user_turns[-2]}\n{query}"
    try:
        return await search_knowledge(db, query, embedder, language=lang, limit=REFERENCE_LIMIT)
    except Exception:  # noqa: BLE001 - the chat must answer even if search is down
        logger.exception("chat.retrieval_failed")
        await db.rollback()
        return []


def _cited_sources(draft: AssistantDraft, references: list[Reference]) -> list[dict[str, Any]]:
    """Valid citations only (numbers of passages actually given), one entry per document."""
    sources: dict[str, dict[str, Any]] = {}
    for number in draft.cited_sources:
        if 1 <= number <= len(references):
            ref = references[number - 1]
            sources.setdefault(
                str(ref.document_id),
                {"document_id": str(ref.document_id), "title": ref.title, "heading": ref.heading, "language": ref.language},
            )
    return list(sources.values())


def _safety_event(conversation: Conversation, level: RiskLevel, flags: list[dict[str, str]], *, requires_human: bool) -> SafetyEvent:
    return SafetyEvent(
        conversation_id=conversation.id,
        patient_id=conversation.patient_id,
        risk_level=level,
        red_flags=flags,
        requires_human=requires_human,
    )


async def run_chat_turn(
    db: AsyncSession,
    *,
    conversation: Conversation,
    user_id: UUID,
    content: str,
    llm: LLMProvider,
    embedder: Embedder,
) -> ChatTurnResult:
    if conversation.status == ConversationStatus.COMPLETED:
        raise ConflictError("This conversation has ended. Please start a new one.")
    text = content.strip()
    await _check_limits(db, conversation.patient_id, text)

    screen: SafetyAssessment = assess(text)
    lang = "ar" if is_arabic(text) else "en"

    user_message = Message(
        conversation_id=conversation.id,
        role=MessageRole.USER,
        content=text,
        extra_data={"safety": _safety_payload(screen.level, screen.flags)} if screen.flags else None,
    )
    db.add(user_message)
    if screen.level != RiskLevel.LOW:
        rule_flags = [{"source": "rules", "rule": flag} for flag in screen.flags]
        db.add(_safety_event(conversation, screen.level, rule_flags, requires_human=screen.is_emergency))
    if screen.is_emergency:
        conversation.status = ConversationStatus.ESCALATED
        logger.warning("chat.emergency_detected", conversation_id=str(conversation.id), flags=list(screen.flags))
    await db.commit()
    await db.refresh(user_message)  # load server-generated id/created_at before the session is used async again

    if screen.is_emergency:
        assistant_message = Message(
            conversation_id=conversation.id,
            role=MessageRole.ASSISTANT,
            content=emergency_message(screen, lang),
            extra_data={"kind": "emergency", "safety": _safety_payload(screen.level, screen.flags), "ai": None},
        )
        return await _finish(db, user_message, assistant_message, conversation, screen.level, None, degraded=False)

    caution_flags = screen.flags if screen.level == RiskLevel.MEDIUM else ()
    history = await _history(db, conversation.id)
    references = await _retrieve(db, history, lang, embedder)

    intake = await consultation.get_or_create_intake(db, conversation)
    data = consultation.load_data(intake)
    notes_for_model: tuple[str, ...] = ()
    if "pregnancy" in screen.flags:
        # The safety rules noticed pregnancy/breastfeeding: record it in code, not via the model.
        data = data.model_copy(update={"pregnancy_or_breastfeeding": True})
        notes_for_model = ("The patient may be pregnant or breastfeeding; some treatments aren't suitable.",)
    patient_turns = sum(1 for turn in history if turn.role == "user")
    assessment_done = intake.status == IntakeStatus.COMPLETE
    today = booking_agent.local_today()
    state = consultation.build_state(
        data,
        patient_turns=patient_turns,
        assessment_done=assessment_done,
        notes=notes_for_model,
        today=f"{today.isoformat()} ({today.strftime('%A')})",
        assessed_specialty=consultation.assessed_specialty(intake),
    )

    draft: AssistantDraft | None = None
    try:
        draft = await llm.respond(
            instructions=system_prompt(caution_flags),
            history=history,
            references=references,
            consultation=state,
            user_ref=anonymous_user_ref(user_id),
        )
    except LLMError:
        logger.warning("chat.model_failed", conversation_id=str(conversation.id), provider=llm.name)

    ai_info = {"provider": llm.name, "model": llm.model, "prompt_version": PROMPT_VERSION}
    # What the model was shown, for later evaluation of retrieval quality.
    retrieval_info = [{"chunk_id": str(r.chunk_id), "score": r.score, "similarity": r.similarity} for r in references]
    if draft is None:
        consultation.save(intake, data, None)
        assistant_message = Message(
            conversation_id=conversation.id,
            role=MessageRole.ASSISTANT,
            content=_FALLBACK[lang],
            extra_data={
                "kind": "fallback", "safety": _safety_payload(screen.level, screen.flags), "ai": ai_info,
                "retrieval": retrieval_info,
            },
        )
        return await _finish(
            db, user_message, assistant_message, conversation, screen.level, None, degraded=True, intake=intake
        )

    data = consultation.merge(data, draft.intake_update)
    assessment = consultation.accept_assessment(
        draft.assessment, data, patient_turns=patient_turns, assessment_done=assessment_done
    )
    if draft.assessment is not None and assessment is None and not assessment_done:
        logger.info("chat.premature_assessment_dropped", conversation_id=str(conversation.id))
    consultation.save(intake, data, assessment)

    # Second safety line: the model's own risk rating (an "urgent" assessment counts as medium).
    model_level = RiskLevel(draft.risk_level)
    if assessment is not None and assessment.urgency == "urgent" and model_level == RiskLevel.LOW:
        model_level = RiskLevel.MEDIUM
    notes = [caution_message(caution_flags, lang)] if caution_flags else []
    if model_level == RiskLevel.HIGH:
        conversation.status = ConversationStatus.ESCALATED
        db.add(_safety_event(conversation, RiskLevel.HIGH, [{"source": "model"}], requires_human=True))
        notes.append(caution_message(("model_flagged",), lang))
        logger.warning("chat.model_flagged_high", conversation_id=str(conversation.id))
    elif model_level == RiskLevel.MEDIUM and screen.level == RiskLevel.LOW:
        db.add(_safety_event(conversation, RiskLevel.MEDIUM, [{"source": "model"}], requires_human=False))

    level = max(screen.level, model_level, key=_RANK.__getitem__)
    # The suggestion comes only from an accepted assessment, and never while
    # the model thinks this may be an emergency.
    suggestion = (
        {"specialty": assessment.suggested_specialty, "concern": data.concern}
        if assessment is not None and model_level != RiskLevel.HIGH
        else None
    )
    reply = draft.reply.strip()[:MAX_REPLY_CHARS]
    sources = _cited_sources(draft, references)

    # Booking agent: the model understood a booking request; the platform
    # searches, ranks and words the answer. Never during a possible emergency.
    booking = None
    if draft.booking_request is not None and model_level != RiskLevel.HIGH:
        criteria = booking_agent.criteria_from_request(
            draft.booking_request,
            fallback_specialty=(assessment.suggested_specialty if assessment else None) or state.assessed_specialty,
        )
        options, relaxed = await booking_agent.find_options(db, criteria, patient_id=conversation.patient_id)
        booking = {"criteria": booking_agent.criteria_payload(criteria), "options": options, "relaxed": relaxed}
        reply = booking_agent.options_message(options, relaxed, lang)
        logger.info("chat.booking_search", conversation_id=str(conversation.id), options=len(options), relaxed=relaxed)
    assistant_message = Message(
        conversation_id=conversation.id,
        role=MessageRole.ASSISTANT,
        content="\n\n".join([reply, *notes]),
        extra_data={
            "kind": "reply",
            "safety": _safety_payload(level, screen.flags),
            "model_risk": draft.risk_level,
            "concern": data.concern,
            "suggestion": suggestion,
            "assessment": assessment.model_dump() if assessment is not None and model_level != RiskLevel.HIGH else None,
            "consultation": {"status": intake.status.value, "missing_fields": intake.missing_fields},
            "sources": sources,
            "booking": booking,
            "retrieval": retrieval_info,
            "ai": ai_info,
        },
    )
    return await _finish(
        db, user_message, assistant_message, conversation, level, suggestion, degraded=False, sources=sources,
        intake=intake,
    )


async def _finish(
    db: AsyncSession,
    user_message: Message,
    assistant_message: Message,
    conversation: Conversation,
    level: RiskLevel,
    suggestion: dict[str, Any] | None,
    *,
    degraded: bool,
    sources: list[dict[str, Any]] | None = None,
    intake=None,
) -> ChatTurnResult:
    db.add(assistant_message)
    await db.commit()
    await db.refresh(assistant_message)
    await db.refresh(conversation)
    if intake is not None:
        await db.refresh(intake)
    return ChatTurnResult(
        user_message, assistant_message, conversation, level, suggestion, degraded, sources or [],
        consultation.summary(intake) if intake is not None else None,
    )
