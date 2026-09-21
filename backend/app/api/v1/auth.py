"""
Auth endpoints.

Session model:
- The access token (30 min) is returned in the JSON body. The frontend
  keeps it in memory only and sends it as `Authorization: Bearer`.
- The refresh token is an httpOnly cookie scoped to /api/v1/auth, so page
  JavaScript can never read it and it's only sent to these endpoints.
  On page load the frontend calls POST /auth/refresh to restore the
  session. SameSite=Lax stops other sites from triggering that request
  with the user's cookie.
"""

from typing import Annotated

from fastapi import APIRouter, Cookie, Depends, Request, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import CurrentPrincipal
from app.core.config import get_settings
from app.core.security import create_access_token
from app.db.session import get_db
from app.models.clinic import Clinic
from app.models.doctor import Doctor
from app.models.patient import Patient
from app.models.user import User
from app.core import rate_limit
from app.core.exceptions import TooManyRequestsError
from app.core.logging import get_logger
from app.core.rate_limit import limit
from app.models.enums import AuthTokenPurpose
from app.schemas.auth import (
    DeleteAccountRequest,
    DeleteAccountResponse,
    ForgotPasswordRequest,
    LoginRequest,
    MeResponse,
    MessageResponse,
    RegisterRequest,
    ResetPasswordRequest,
    SessionResponse,
    VerificationConfirm,
    VerificationRequest,
)
from app.schemas.doctor import DoctorRegisterRequest
from app.services import account_service, auth_service, doctor_verification_service

router = APIRouter(prefix="/auth", tags=["auth"])
logger = get_logger(__name__)
settings = get_settings()

RefreshCookie = Annotated[str | None, Cookie(alias=settings.refresh_cookie_name)]


def _cookie_path() -> str:
    return f"{settings.api_v1_prefix}/auth"


def _set_refresh_cookie(response: Response, raw_token: str) -> None:
    response.set_cookie(
        key=settings.refresh_cookie_name,
        value=raw_token,
        max_age=settings.refresh_token_expire_days * 24 * 60 * 60,
        httponly=True,
        secure=settings.cookie_secure,
        samesite="lax",
        path=_cookie_path(),
    )


def _clear_refresh_cookie(response: Response) -> None:
    response.delete_cookie(
        key=settings.refresh_cookie_name,
        httponly=True,
        secure=settings.cookie_secure,
        samesite="lax",
        path=_cookie_path(),
    )


def _session(
    response: Response,
    user: User,
    patient: Patient | None,
    refresh_token: str,
    doctor: Doctor | None = None,
    clinics: list[Clinic] | None = None,
) -> SessionResponse:
    _set_refresh_cookie(response, refresh_token)
    access_token, expires_in = create_access_token(user.id, user.role)
    return SessionResponse(
        access_token=access_token, expires_in=expires_in, user=user, patient=patient, doctor=doctor,
        clinics=clinics or [],
    )


@router.post(
    "/register",
    response_model=SessionResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[limit("register", times=5, seconds=3600)],
)
async def register(payload: RegisterRequest, response: Response, db: AsyncSession = Depends(get_db)) -> SessionResponse:
    """Patient self-registration. Logs the new patient in immediately."""
    user, patient = await auth_service.register_patient(db, payload)
    refresh_token = await auth_service.issue_refresh_token(db, user)
    return _session(response, user, patient, refresh_token)


@router.post(
    "/register/doctor",
    response_model=SessionResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[limit("register", times=5, seconds=3600)],
)
async def register_doctor(
    payload: DoctorRegisterRequest, response: Response, db: AsyncSession = Depends(get_db)
) -> SessionResponse:
    """
    Doctor self-registration ("Join as a Doctor"). Logs them in right away
    so they can upload their documents, but the profile stays unverified:
    not listed, not bookable, no slots, until an admin approves it.
    """
    user, doctor = await doctor_verification_service.register_doctor(db, payload)
    refresh_token = await auth_service.issue_refresh_token(db, user)
    return _session(response, user, None, refresh_token, doctor)


@router.post(
    "/login",
    response_model=SessionResponse,
    # A loose per-address cap catches floods. Guessing one account is
    # throttled per identifier below, because many patients share one
    # carrier-grade NAT address and a clinic shares one office address:
    # a tight per-IP limit would lock all of them out at once.
    dependencies=[limit("login_ip", times=30, seconds=300)],
)
async def login(
    payload: LoginRequest, request: Request, response: Response, db: AsyncSession = Depends(get_db)
) -> SessionResponse:
    if not await rate_limit.hit("login_identifier", payload.identifier.strip().lower(), times=8, seconds=900):
        logger.info("auth.login_throttled")
        raise TooManyRequestsError("Too many attempts on this account. Please wait a few minutes and try again.")
    user = await auth_service.authenticate(db, payload.identifier, payload.password)
    refresh_token = await auth_service.issue_refresh_token(db, user)
    patient = await auth_service.get_patient_for_user(db, user)
    doctor = await doctor_verification_service.get_doctor_for_user(db, user)
    clinics = await auth_service.clinics_for_user(db, user)
    return _session(response, user, patient, refresh_token, doctor, clinics)


@router.post("/refresh", response_model=SessionResponse)
async def refresh(
    response: Response, refresh_token: RefreshCookie = None, db: AsyncSession = Depends(get_db)
) -> SessionResponse:
    """Rotates the refresh cookie and returns a fresh access token."""
    user, new_token = await auth_service.rotate_refresh_token(db, refresh_token)
    patient = await auth_service.get_patient_for_user(db, user)
    doctor = await doctor_verification_service.get_doctor_for_user(db, user)
    clinics = await auth_service.clinics_for_user(db, user)
    return _session(response, user, patient, new_token, doctor, clinics)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(response: Response, refresh_token: RefreshCookie = None, db: AsyncSession = Depends(get_db)) -> None:
    """Ends this device's session. Always succeeds, even without a cookie."""
    await auth_service.revoke_session(db, refresh_token)
    _clear_refresh_cookie(response)


@router.get("/me", response_model=MeResponse)
async def me(principal: CurrentPrincipal, db: AsyncSession = Depends(get_db)) -> MeResponse:
    patient = await db.get(Patient, principal.patient_id) if principal.patient_id else None
    doctor = await db.get(Doctor, principal.doctor_id) if principal.doctor_id else None
    clinics = await auth_service.clinics_for_user(db, principal.user)
    return MeResponse(user=principal.user, patient=patient, doctor=doctor, clinics=clinics)


# --- Password reset and verification (Sprint 17; docs/security.md) ---------------------------


@router.post(
    "/password/forgot",
    response_model=MessageResponse,
    dependencies=[limit("password_forgot", times=5, seconds=900)],
)
async def forgot_password(
    payload: ForgotPasswordRequest, db: AsyncSession = Depends(get_db)
) -> MessageResponse:
    """
    Sends a reset link. Answers the same way whether or not the account
    exists, so it can't be used to find out who has one.
    """
    await account_service.request_password_reset(db, payload.identifier)
    return MessageResponse(message=account_service.NEUTRAL_REPLY)


@router.post(
    "/password/reset",
    response_model=MessageResponse,
    dependencies=[limit("password_reset", times=10, seconds=900)],
)
async def reset_password(payload: ResetPasswordRequest, db: AsyncSession = Depends(get_db)) -> MessageResponse:
    """
    Sets a new password from a reset link and ends every open session on
    that account. 401 `invalid_token` for a used, expired or unknown link.
    """
    await account_service.reset_password(db, payload.token, payload.password)
    return MessageResponse(message="Your password has been changed. Please log in.")


@router.post(
    "/verify/request",
    response_model=MessageResponse,
    dependencies=[limit("verify_request", times=5, seconds=900)],
)
async def request_verification(
    payload: VerificationRequest, principal: CurrentPrincipal, db: AsyncSession = Depends(get_db)
) -> MessageResponse:
    """Sends a 6-digit code to the caller's own email address or phone number."""
    purpose = (
        AuthTokenPurpose.EMAIL_VERIFICATION if payload.channel == "email" else AuthTokenPurpose.PHONE_VERIFICATION
    )
    await account_service.request_verification(db, principal.user, purpose)
    return MessageResponse(message="We've sent you a code.")


@router.post(
    "/verify/confirm",
    response_model=MeResponse,
    dependencies=[limit("verify_confirm", times=10, seconds=900)],
)
async def confirm_verification(
    payload: VerificationConfirm, principal: CurrentPrincipal, db: AsyncSession = Depends(get_db)
) -> MeResponse:
    """Confirms the code. Five wrong guesses and the code is spent."""
    purpose = (
        AuthTokenPurpose.EMAIL_VERIFICATION if payload.channel == "email" else AuthTokenPurpose.PHONE_VERIFICATION
    )
    user = await account_service.confirm_verification(db, principal.user, purpose, payload.code)
    patient = await db.get(Patient, principal.patient_id) if principal.patient_id else None
    doctor = await db.get(Doctor, principal.doctor_id) if principal.doctor_id else None
    clinics = await auth_service.clinics_for_user(db, user)
    return MeResponse(user=user, patient=patient, doctor=doctor, clinics=clinics)


# --- Your data (PDPL rights; docs/privacy.md) --------------------------------------------------


@router.get("/me/data")
async def export_my_data(principal: CurrentPrincipal, db: AsyncSession = Depends(get_db)) -> dict:
    """Everything the platform holds about the caller, as one JSON document."""
    return await account_service.export_my_data(db, principal.user)


@router.post("/me/delete", response_model=DeleteAccountResponse)
async def delete_my_account(
    payload: DeleteAccountRequest,
    response: Response,
    principal: CurrentPrincipal,
    db: AsyncSession = Depends(get_db),
) -> DeleteAccountResponse:
    """
    Deletes the account. The password is required, because this can't be
    undone. Appointments and payments are kept, de-identified, as medical
    and financial records (docs/privacy.md).
    """
    kept = await account_service.delete_my_account(db, principal.user, password=payload.password)
    _clear_refresh_cookie(response)
    return DeleteAccountResponse(message="Your account has been deleted.", kept=kept)
