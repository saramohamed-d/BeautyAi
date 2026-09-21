"""
Authentication dependencies and the request's `Principal`.

Every route declares who may call it with one of:
    principal: OptionalPrincipal                   # public, but aware of the caller
    principal: CurrentPrincipal                    # any logged-in user
    principal = Depends(require_roles(UserRole.PLATFORM_ADMIN, ...))

Ownership checks ("is this *your* appointment?") live in
app/api/permissions.py and use the profile ids resolved here.
"""

from dataclasses import dataclass, field
from typing import Annotated
from uuid import UUID

from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ForbiddenError, UnauthorizedError
from app.core.security import decode_access_token
from app.db.session import get_db
from app.models.clinic import ClinicStaff
from app.models.doctor import Doctor
from app.models.enums import ClinicStaffRole, UserRole, UserStatus
from app.models.patient import Patient
from app.models.user import User

bearer_scheme = HTTPBearer(auto_error=False, description="Access token from /auth/login")


@dataclass(frozen=True)
class Principal:
    """The authenticated caller plus the profile ids their permissions depend on."""

    user: User
    patient_id: UUID | None = None
    doctor_id: UUID | None = None
    # Clinics where the user is an active clinic admin.
    clinic_ids: frozenset[UUID] = field(default_factory=frozenset)

    @property
    def role(self) -> UserRole:
        return self.user.role

    @property
    def is_admin(self) -> bool:
        return self.user.role == UserRole.PLATFORM_ADMIN


async def _load_principal(db: AsyncSession, user: User) -> Principal:
    if user.role == UserRole.PATIENT:
        patient_id = await db.scalar(select(Patient.id).where(Patient.user_id == user.id))
        return Principal(user=user, patient_id=patient_id)
    if user.role == UserRole.DOCTOR:
        doctor_id = await db.scalar(select(Doctor.id).where(Doctor.user_id == user.id))
        return Principal(user=user, doctor_id=doctor_id)
    if user.role == UserRole.CLINIC_ADMIN:
        rows = await db.scalars(
            select(ClinicStaff.clinic_id).where(
                ClinicStaff.user_id == user.id,
                ClinicStaff.role == ClinicStaffRole.CLINIC_ADMIN,
                ClinicStaff.is_active.is_(True),
            )
        )
        return Principal(user=user, clinic_ids=frozenset(rows.all()))
    return Principal(user=user)


async def get_optional_principal(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)],
    db: AsyncSession = Depends(get_db),
) -> Principal | None:
    """None for anonymous callers. A token that is present but invalid is still a 401."""
    if credentials is None:
        return None
    payload = decode_access_token(credentials.credentials)
    if payload is None:
        raise UnauthorizedError("Invalid or expired access token")
    try:
        user_id = UUID(payload["sub"])
    except ValueError:
        raise UnauthorizedError("Invalid or expired access token") from None
    user = await db.get(User, user_id)
    if user is None or user.status != UserStatus.ACTIVE:
        raise UnauthorizedError("Invalid or expired access token")
    return await _load_principal(db, user)


async def get_current_principal(principal: Annotated[Principal | None, Depends(get_optional_principal)]) -> Principal:
    if principal is None:
        raise UnauthorizedError("Authentication required")
    return principal


OptionalPrincipal = Annotated[Principal | None, Depends(get_optional_principal)]
CurrentPrincipal = Annotated[Principal, Depends(get_current_principal)]


def require_roles(*roles: UserRole):
    """Dependency factory: the caller must be logged in with one of `roles`."""

    async def dependency(principal: CurrentPrincipal) -> Principal:
        if principal.role not in roles:
            raise ForbiddenError("You don't have permission to do this")
        return principal

    return dependency


AdminPrincipal = Annotated[Principal, Depends(require_roles(UserRole.PLATFORM_ADMIN))]
