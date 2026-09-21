"""
Authentication service: registration, login, and refresh-token sessions.

See app/core/security.py for the cryptographic choices and
app/models/user.py for the refresh-token rotation scheme.
"""

import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.exceptions import ConflictError, ForbiddenError, UnauthorizedError
from app.core.logging import get_logger
from app.core.security import hash_password, hash_refresh_token, new_refresh_token, verify_password
from app.models.clinic import Clinic, ClinicStaff
from app.models.enums import ClinicStaffRole, UserRole, UserStatus
from app.models.patient import Patient
from app.models.user import RefreshToken, User
from app.schemas.auth import RegisterRequest

logger = get_logger(__name__)

INVALID_CREDENTIALS = "Invalid email/phone or password"
INVALID_SESSION = "Session expired or invalid. Please log in again."

# How long a just-rotated refresh token may still be exchanged (see RefreshToken).
REFRESH_REUSE_GRACE = timedelta(seconds=30)


def normalize_email(email: str) -> str:
    return email.strip().lower()


def normalize_phone(phone: str) -> str:
    return "".join(ch for ch in phone if ch.isdigit() or ch == "+")


async def register_patient(db: AsyncSession, data: RegisterRequest) -> tuple[User, Patient]:
    """
    Creates a patient login and its patient profile in one transaction.

    An existing patient *profile* with the same phone/email (e.g. a
    walk-in created by a clinic, or a Sprint 3 phone-only record) is NOT
    silently attached to the new account: without phone/email
    verification (Sprint 15) that would let anyone claim someone else's
    medical history by typing their phone number.
    """
    email = normalize_email(data.email)
    phone = normalize_phone(data.phone)

    taken_user = await db.scalar(select(User).where(or_(User.email == email, User.phone == phone)))
    taken_patient = await db.scalar(select(Patient).where(or_(Patient.email == email, Patient.phone == phone)))
    for taken in (taken_user, taken_patient):
        if taken is not None:
            field = "email" if taken.email == email else "phone number"
            raise ConflictError(f"An account with this {field} already exists")

    user = User(email=email, phone=phone, password_hash=hash_password(data.password), role=UserRole.PATIENT)
    db.add(user)
    await db.flush()

    patient = Patient(
        user_id=user.id,
        full_name=data.full_name,
        email=email,
        phone=phone,
        date_of_birth=data.date_of_birth,
        gender=data.gender,
        city=data.city,
        preferred_language=data.preferred_language,
    )
    db.add(patient)
    await db.commit()
    await db.refresh(user)
    await db.refresh(patient)
    logger.info("auth.registered", user_id=str(user.id), role=user.role.value)
    return user, patient


async def authenticate(db: AsyncSession, identifier: str, password: str) -> User:
    """Email or phone + password. The same generic error for every failure, so accounts can't be enumerated."""
    identifier = identifier.strip()
    if "@" in identifier:
        condition = User.email == normalize_email(identifier)
    else:
        condition = User.phone == normalize_phone(identifier)
    user = await db.scalar(select(User).where(condition))

    # verify_password runs first even when the user doesn't exist (it checks a
    # dummy hash), so response time doesn't reveal which accounts exist.
    if not verify_password(password, user.password_hash if user else None) or user is None:
        logger.info("auth.login_failed")
        raise UnauthorizedError(INVALID_CREDENTIALS)
    ensure_can_sign_in(user)

    user.last_login_at = datetime.now(timezone.utc)
    await db.commit()
    logger.info("auth.login", user_id=str(user.id), role=user.role.value)
    return user


def ensure_can_sign_in(user: User) -> None:
    if user.status == UserStatus.SUSPENDED:
        raise ForbiddenError("This account is suspended")
    if user.status == UserStatus.PENDING:
        raise ForbiddenError("This account is awaiting approval")


async def issue_refresh_token(db: AsyncSession, user: User, family_id: uuid.UUID | None = None) -> str:
    """Stores a new refresh token (hashed) and returns the raw value for the cookie."""
    raw = new_refresh_token()
    db.add(
        RefreshToken(
            user_id=user.id,
            token_hash=hash_refresh_token(raw),
            family_id=family_id or uuid.uuid4(),
            expires_at=datetime.now(timezone.utc) + timedelta(days=get_settings().refresh_token_expire_days),
        )
    )
    await db.commit()
    return raw


async def rotate_refresh_token(db: AsyncSession, raw: str | None) -> tuple[User, str]:
    """
    Exchanges a valid refresh token for a new one.

    Replaying an already-used token after the grace period revokes its
    whole family (see RefreshToken for why).
    """
    if not raw:
        raise UnauthorizedError(INVALID_SESSION)
    token = await db.scalar(select(RefreshToken).where(RefreshToken.token_hash == hash_refresh_token(raw)))
    now = datetime.now(timezone.utc)

    if token is None or token.revoked_at is not None or token.expires_at <= now:
        raise UnauthorizedError(INVALID_SESSION)
    if token.used_at is not None and now - token.used_at > REFRESH_REUSE_GRACE:
        await _revoke_family(db, token.family_id, now)
        logger.warning("auth.refresh_token_reuse", user_id=str(token.user_id), family_id=str(token.family_id))
        raise UnauthorizedError(INVALID_SESSION)

    user = await db.get(User, token.user_id)
    if user is None:
        raise UnauthorizedError(INVALID_SESSION)
    ensure_can_sign_in(user)

    if token.used_at is None:
        token.used_at = now
    return user, await issue_refresh_token(db, user, family_id=token.family_id)


async def revoke_session(db: AsyncSession, raw: str | None) -> None:
    """Logout: revokes the presented token's whole family (this device's session). Unknown tokens are ignored."""
    if not raw:
        return
    token = await db.scalar(select(RefreshToken).where(RefreshToken.token_hash == hash_refresh_token(raw)))
    if token is not None:
        await _revoke_family(db, token.family_id, datetime.now(timezone.utc))


async def _revoke_family(db: AsyncSession, family_id: uuid.UUID, now: datetime) -> None:
    await db.execute(
        update(RefreshToken)
        .where(RefreshToken.family_id == family_id, RefreshToken.revoked_at.is_(None))
        .values(revoked_at=now)
    )
    await db.commit()


async def get_patient_for_user(db: AsyncSession, user: User) -> Patient | None:
    return await db.scalar(select(Patient).where(Patient.user_id == user.id))


async def clinics_for_user(db: AsyncSession, user: User) -> list[Clinic]:
    """The clinics a clinic admin manages (Sprint 13); empty for every other role."""
    if user.role != UserRole.CLINIC_ADMIN:
        return []
    rows = await db.scalars(
        select(Clinic)
        .join(ClinicStaff, ClinicStaff.clinic_id == Clinic.id)
        .where(
            ClinicStaff.user_id == user.id,
            ClinicStaff.role == ClinicStaffRole.CLINIC_ADMIN,
            ClinicStaff.is_active.is_(True),
        )
        .order_by(Clinic.name)
    )
    return list(rows.all())
