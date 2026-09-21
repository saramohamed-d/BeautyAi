"""
Password reset, contact verification, and a patient's data rights
(Sprint 17; docs/security.md and docs/privacy.md).

Design decisions:

- **Nothing here tells a stranger whether an account exists.** "Forgot
  password" answers the same way for a known and an unknown address; the
  message only reaches a real mailbox or phone.
- **One-time tokens are stored hashed**, are short-lived, and using one
  revokes the rest for that purpose — an old link in an inbox stops
  working the moment a newer one is used.
- **Resetting a password ends every session.** If the reset was needed
  because someone else had the account, their open sessions must die
  with it.
- **Deleting an account keeps what the clinic must keep.** Egypt's PDPL
  (Law 151/2018) gives a right to erasure, but a clinic also has records
  of real appointments and payments. The login and the personal details
  are erased; appointments and payments stay, de-identified, with the
  reason recorded in the audit log.
"""

import secrets
from datetime import datetime, timedelta, timezone
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.exceptions import ConflictError, NotFoundError, UnauthorizedError, ValidationAppError
from app.core.logging import get_logger
from app.core.security import hash_password, hash_refresh_token, verify_password
from app.models.auth_token import AuthToken
from app.models.conversation import Conversation, Message
from app.models.enums import AuthTokenPurpose, Language, NotificationChannel
from app.models.notification import Notification
from app.models.patient import Patient, PatientConsent
from app.models.payment import Payment
from app.models.scheduling import Appointment
from app.models.user import RefreshToken, User
from app.notifications import templates
from app.services import audit_service, notification_service

logger = get_logger(__name__)

RESET_TOKEN_MINUTES = 30
CODE_MINUTES = 15
MAX_CODE_ATTEMPTS = 5
INVALID_TOKEN = "invalid_token"
# The same answer whether or not the address is known, so the endpoint
# can't be used to find out who has an account.
NEUTRAL_REPLY = "If that account exists, we've sent it instructions."


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _hash(value: str) -> str:
    return hash_refresh_token(value)


async def _issue(
    db: AsyncSession, user: User, purpose: AuthTokenPurpose, *, sent_to: str, minutes: int, token: str
) -> AuthToken:
    """Replaces any outstanding token for this purpose with a new one."""
    await db.execute(
        update(AuthToken)
        .where(AuthToken.user_id == user.id, AuthToken.purpose == purpose, AuthToken.used_at.is_(None))
        .values(revoked_at=_now())
    )
    record = AuthToken(
        user_id=user.id,
        purpose=purpose,
        token_hash=_hash(token),
        sent_to=sent_to,
        expires_at=_now() + timedelta(minutes=minutes),
    )
    db.add(record)
    return record


async def _consume(db: AsyncSession, purpose: AuthTokenPurpose, token: str, *, user_id: UUID | None = None) -> AuthToken:
    """Finds a usable token and marks it used, or refuses."""
    query = select(AuthToken).where(AuthToken.token_hash == _hash(token), AuthToken.purpose == purpose)
    if user_id is not None:
        query = query.where(AuthToken.user_id == user_id)
    record = await db.scalar(query.with_for_update())
    if record is None or record.used_at or record.revoked_at or record.expires_at <= _now():
        raise UnauthorizedError("This link or code is invalid or has expired.", code=INVALID_TOKEN)
    record.used_at = _now()
    return record


# --- Password reset --------------------------------------------------------------------------


async def request_password_reset(db: AsyncSession, identifier: str) -> None:
    """Sends a reset link if the account exists. Says nothing either way."""
    from app.services.auth_service import normalize_email, normalize_phone

    identifier = identifier.strip()
    condition = (
        User.email == normalize_email(identifier) if "@" in identifier else User.phone == normalize_phone(identifier)
    )
    user = await db.scalar(select(User).where(condition))
    if user is None:
        logger.info("auth.reset_requested_unknown")
        return

    token = secrets.token_urlsafe(32)
    address = user.email or user.phone or ""
    await _issue(db, user, AuthTokenPurpose.PASSWORD_RESET, sent_to=address, minutes=RESET_TOKEN_MINUTES, token=token)

    settings = get_settings()
    patient = await db.scalar(select(Patient).where(Patient.user_id == user.id))
    channel = NotificationChannel.EMAIL if user.email else NotificationChannel.SMS
    await notification_service.enqueue(
        db,
        template=templates.PASSWORD_RESET,
        context={
            "name": patient.full_name if patient else "",
            "reset_url": f"{settings.frontend_url}/reset-password?token={token}",
            "minutes": RESET_TOKEN_MINUTES,
        },
        language=patient.preferred_language if patient else Language.EN,
        # A reset always goes out, whatever the marketing preferences say.
        recipients={channel: address},
        dedupe_key=f"password-reset:{user.id}:{_now().isoformat()}",
        user_id=user.id,
        patient_id=patient.id if patient else None,
    )
    await db.commit()
    logger.info("auth.reset_requested", user_id=str(user.id))


async def reset_password(db: AsyncSession, token: str, new_password: str) -> User:
    """Sets a new password, ends every session, and tells the account it happened."""
    record = await _consume(db, AuthTokenPurpose.PASSWORD_RESET, token)
    user = await db.get(User, record.user_id)
    if user is None:  # pragma: no cover - the FK makes this unreachable
        raise NotFoundError("Account not found")

    user.password_hash = hash_password(new_password)
    await db.execute(
        update(RefreshToken)
        .where(RefreshToken.user_id == user.id, RefreshToken.revoked_at.is_(None))
        .values(revoked_at=_now())
    )
    audit_service.record(
        db, actor=None, action="user.password_reset", resource_type="user", resource_id=user.id
    )
    await db.commit()
    await db.refresh(user)
    logger.info("auth.password_reset", user_id=str(user.id))
    return user


# --- Verifying an email address or phone number -----------------------------------------------


def _code() -> str:
    return f"{secrets.randbelow(1_000_000):06d}"


async def request_verification(db: AsyncSession, user: User, purpose: AuthTokenPurpose) -> None:
    """Sends a 6-digit code to the address being verified."""
    address = user.email if purpose == AuthTokenPurpose.EMAIL_VERIFICATION else user.phone
    if not address:
        raise ValidationAppError("There's no address on this account to verify")
    if purpose == AuthTokenPurpose.EMAIL_VERIFICATION and user.email_verified_at:
        raise ConflictError("This email address is already verified")
    if purpose == AuthTokenPurpose.PHONE_VERIFICATION and user.phone_verified_at:
        raise ConflictError("This phone number is already verified")

    code = _code()
    await _issue(db, user, purpose, sent_to=address, minutes=CODE_MINUTES, token=code)
    patient = await db.scalar(select(Patient).where(Patient.user_id == user.id))
    channel = (
        NotificationChannel.EMAIL if purpose == AuthTokenPurpose.EMAIL_VERIFICATION else NotificationChannel.SMS
    )
    await notification_service.enqueue(
        db,
        template=templates.VERIFY_CONTACT,
        context={"name": patient.full_name if patient else "", "code": code, "minutes": CODE_MINUTES},
        language=patient.preferred_language if patient else Language.EN,
        recipients={channel: address},
        dedupe_key=f"verify:{user.id}:{purpose.value}:{_now().isoformat()}",
        user_id=user.id,
        patient_id=patient.id if patient else None,
    )
    await db.commit()


async def confirm_verification(db: AsyncSession, user: User, purpose: AuthTokenPurpose, code: str) -> User:
    """Checks the code, counting wrong guesses against the outstanding token."""
    outstanding = await db.scalar(
        select(AuthToken)
        .where(
            AuthToken.user_id == user.id,
            AuthToken.purpose == purpose,
            AuthToken.used_at.is_(None),
            AuthToken.revoked_at.is_(None),
        )
        .order_by(AuthToken.created_at.desc())
        .with_for_update()
    )
    if outstanding is None or outstanding.expires_at <= _now():
        raise UnauthorizedError("This code is invalid or has expired.", code=INVALID_TOKEN)
    if outstanding.attempts >= MAX_CODE_ATTEMPTS:
        raise UnauthorizedError("Too many wrong codes. Please request a new one.", code=INVALID_TOKEN)

    outstanding.attempts += 1
    if outstanding.token_hash != _hash(code.strip()):
        await db.commit()
        raise UnauthorizedError("This code is invalid or has expired.", code=INVALID_TOKEN)

    outstanding.used_at = _now()
    if purpose == AuthTokenPurpose.EMAIL_VERIFICATION:
        user.email_verified_at = _now()
    else:
        user.phone_verified_at = _now()
    await db.commit()
    await db.refresh(user)
    logger.info("auth.contact_verified", user_id=str(user.id), purpose=purpose.value)
    return user


# --- A patient's data rights (PDPL) ------------------------------------------------------------


async def export_my_data(db: AsyncSession, user: User) -> dict:
    """
    Everything the platform holds about this person, in one JSON document
    (PDPL right of access and portability).
    """
    patient = await db.scalar(select(Patient).where(Patient.user_id == user.id))

    async def rows(model, *conditions):
        result = await db.scalars(select(model).where(*conditions))
        return [
            {
                column.name: _plain(getattr(row, column.name))
                for column in model.__table__.columns
                if column.name not in _SECRET_COLUMNS
            }
            for row in result.all()
        ]

    data: dict = {
        "exported_at": _now().isoformat(),
        "account": {
            "id": str(user.id),
            "email": user.email,
            "phone": user.phone,
            "role": user.role.value,
            "created_at": _plain(user.created_at),
            "email_verified_at": _plain(user.email_verified_at),
            "phone_verified_at": _plain(user.phone_verified_at),
        },
        "patient_profile": None,
        "consents": [],
        "appointments": [],
        "payments": [],
        "conversations": [],
        "messages_to_you": [],
    }
    if patient is None:
        return data

    data["patient_profile"] = {
        column.name: _plain(getattr(patient, column.name)) for column in Patient.__table__.columns
    }
    data["consents"] = await rows(PatientConsent, PatientConsent.patient_id == patient.id)
    data["appointments"] = await rows(Appointment, Appointment.patient_id == patient.id)
    data["payments"] = await rows(Payment, Payment.patient_id == patient.id)
    data["conversations"] = await rows(Conversation, Conversation.patient_id == patient.id)
    conversation_ids = [row["id"] for row in data["conversations"]]
    if conversation_ids:
        data["messages"] = await rows(Message, Message.conversation_id.in_([UUID(cid) for cid in conversation_ids]))
    data["messages_to_you"] = await rows(Notification, Notification.patient_id == patient.id)
    return data


# Never exported: they're secrets or internal plumbing.
_SECRET_COLUMNS = {"password_hash", "token_hash", "stored_path", "embedding", "search_vector"}


def _plain(value):
    if isinstance(value, datetime):
        return value.isoformat()
    if hasattr(value, "value"):  # enums
        return value.value
    if isinstance(value, UUID):
        return str(value)
    if isinstance(value, (dict, list, str, int, float, bool)) or value is None:
        return value
    return str(value)


async def delete_my_account(db: AsyncSession, user: User, *, password: str) -> dict:
    """
    Erases the login and the personal details, and de-identifies what the
    clinic has to keep (PDPL right of erasure, balanced against medical
    and financial record-keeping).

    Returns what happened, so the person can be told plainly.
    """
    if not verify_password(password, user.password_hash):
        raise UnauthorizedError("Password is incorrect")

    patient = await db.scalar(select(Patient).where(Patient.user_id == user.id))
    kept = {"appointments": 0, "payments": 0}
    if patient is not None:
        kept["appointments"] = len(
            (await db.scalars(select(Appointment.id).where(Appointment.patient_id == patient.id))).all()
        )
        kept["payments"] = len((await db.scalars(select(Payment.id).where(Payment.patient_id == patient.id))).all())

        # Conversations are the patient's own words: deleted outright.
        conversations = (
            await db.scalars(select(Conversation).where(Conversation.patient_id == patient.id))
        ).all()
        for conversation in conversations:
            await db.delete(conversation)
        for notification in (
            await db.scalars(select(Notification).where(Notification.patient_id == patient.id))
        ).all():
            await db.delete(notification)

        # The profile stays attached to its appointments, with nothing
        # identifying left on it.
        marker = str(patient.id)[:8]
        patient.full_name = "Deleted patient"
        patient.phone = f"deleted-{marker}"
        patient.email = None
        patient.date_of_birth = None
        patient.gender = None
        patient.city = None
        patient.user_id = None
        patient.notify_email = patient.notify_sms = patient.notify_whatsapp = False

    await db.execute(
        update(RefreshToken).where(RefreshToken.user_id == user.id).values(revoked_at=_now())
    )
    audit_service.record(
        db,
        actor=None,
        action="user.deleted",
        resource_type="user",
        resource_id=user.id,
        extra={"kept": kept, "reason": "requested by the account holder"},
    )
    await db.delete(user)
    await db.commit()
    logger.info("account.deleted", kept=kept)
    return kept
