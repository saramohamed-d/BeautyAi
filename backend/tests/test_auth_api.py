"""Sprint 5: registration, login, refresh-token rotation, logout."""

from datetime import datetime, timedelta, timezone

import jwt
import pytest
from httpx import AsyncClient
from sqlalchemy import select

from app.core.config import get_settings
from app.core.security import hash_refresh_token
from app.db.session import AsyncSessionLocal
from app.models.enums import UserRole, UserStatus
from app.models.user import RefreshToken
from tests.factories import (
    TEST_PASSWORD,
    create_user,
    make_patient,
    register_patient,
    unique_email,
    unique_phone,
)

COOKIE = get_settings().refresh_cookie_name


async def refresh_with(client: AsyncClient, raw_token: str):
    """POST /auth/refresh sending exactly this refresh token and nothing else."""
    client.cookies.clear()
    client.cookies.set(COOKIE, raw_token)
    return await client.post("/api/v1/auth/refresh")


def refresh_cookie_header(resp) -> str:
    return next(v for k, v in resp.headers.multi_items() if k == "set-cookie" and v.startswith(COOKIE))


async def test_register_creates_patient_account_and_logs_in(client: AsyncClient) -> None:
    email = unique_email()
    session = await register_patient(client, email=email.upper(), full_name="Sara Ahmed", city="Cairo")

    assert session["user"]["role"] == "patient"
    assert session["user"]["email"] == email  # stored lower-cased
    assert session["patient"]["full_name"] == "Sara Ahmed"
    assert session["patient"]["city"] == "Cairo"
    assert session["token_type"] == "bearer" and session["expires_in"] > 0

    me = await client.get("/api/v1/auth/me", headers=session["headers"])
    assert me.status_code == 200
    assert me.json()["patient"]["id"] == session["patient"]["id"]


async def test_register_sets_httponly_refresh_cookie_scoped_to_auth(client: AsyncClient) -> None:
    resp = await client.post(
        "/api/v1/auth/register",
        json={"full_name": "Cookie Test", "email": unique_email(), "phone": unique_phone(), "password": TEST_PASSWORD},
    )
    cookie = refresh_cookie_header(resp).lower()
    assert "httponly" in cookie
    assert "path=/api/v1/auth" in cookie
    assert "samesite=lax" in cookie


@pytest.mark.parametrize("field", ["email", "phone"])
async def test_register_duplicate_returns_409(client: AsyncClient, field: str) -> None:
    first = await register_patient(client)
    payload = {"full_name": "Dup", "email": unique_email(), "phone": unique_phone(), "password": TEST_PASSWORD}
    payload[field] = first["user"][field]
    resp = await client.post("/api/v1/auth/register", json=payload)
    assert resp.status_code == 409


async def test_register_cannot_claim_existing_patient_profile(client: AsyncClient, admin_client: AsyncClient) -> None:
    """A profile without a login (e.g. a clinic walk-in) can't be taken over by typing its phone number."""
    walk_in = await make_patient(admin_client)
    resp = await client.post(
        "/api/v1/auth/register",
        json={"full_name": "Impostor", "email": unique_email(), "phone": walk_in["phone"], "password": TEST_PASSWORD},
    )
    assert resp.status_code == 409


@pytest.mark.parametrize("password", ["short", "ش" * 37])  # 7 chars; 74 bytes (Arabic is 2 bytes/char)
async def test_register_rejects_bad_passwords(client: AsyncClient, password: str) -> None:
    resp = await client.post(
        "/api/v1/auth/register",
        json={"full_name": "Weak", "email": unique_email(), "phone": unique_phone(), "password": password},
    )
    assert resp.status_code == 422


async def test_login_with_email_or_phone(client: AsyncClient) -> None:
    session = await register_patient(client)
    for identifier in (session["user"]["email"].upper(), session["user"]["phone"]):
        resp = await client.post("/api/v1/auth/login", json={"identifier": identifier, "password": TEST_PASSWORD})
        assert resp.status_code == 200, resp.text
        assert resp.json()["patient"]["id"] == session["patient"]["id"]


async def test_login_failures_are_indistinguishable(client: AsyncClient) -> None:
    session = await register_patient(client)
    wrong_password = await client.post(
        "/api/v1/auth/login", json={"identifier": session["user"]["email"], "password": "wrong-password"}
    )
    unknown_user = await client.post(
        "/api/v1/auth/login", json={"identifier": unique_email(), "password": "wrong-password"}
    )
    assert wrong_password.status_code == unknown_user.status_code == 401
    assert wrong_password.json() == unknown_user.json()
    assert wrong_password.headers["www-authenticate"] == "Bearer"


async def test_suspended_user_cannot_log_in(client: AsyncClient) -> None:
    user = await create_user(UserRole.PATIENT, status=UserStatus.SUSPENDED)
    resp = await client.post("/api/v1/auth/login", json={"identifier": user.email, "password": TEST_PASSWORD})
    assert resp.status_code == 403


async def test_me_requires_valid_token(client: AsyncClient) -> None:
    assert (await client.get("/api/v1/auth/me")).status_code == 401
    garbage = await client.get("/api/v1/auth/me", headers={"Authorization": "Bearer not-a-jwt"})
    assert garbage.status_code == 401

    settings = get_settings()
    user = await create_user(UserRole.PATIENT)
    expired = jwt.encode(
        {"sub": str(user.id), "role": "patient", "type": "access", "exp": datetime.now(timezone.utc) - timedelta(minutes=1)},
        settings.jwt_secret_key,
        algorithm=settings.jwt_algorithm,
    )
    resp = await client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {expired}"})
    assert resp.status_code == 401


async def test_token_of_suspended_user_is_rejected(client: AsyncClient) -> None:
    from tests.factories import bearer

    user = await create_user(UserRole.PATIENT, status=UserStatus.SUSPENDED)
    assert (await client.get("/api/v1/auth/me", headers=bearer(user))).status_code == 401


async def _age_used_token(raw: str, seconds: int) -> None:
    """Pretends `raw` was rotated `seconds` ago."""
    async with AsyncSessionLocal() as db:
        token = await db.scalar(select(RefreshToken).where(RefreshToken.token_hash == hash_refresh_token(raw)))
        token.used_at = datetime.now(timezone.utc) - timedelta(seconds=seconds)
        await db.commit()


async def test_refresh_rotates_token(client: AsyncClient) -> None:
    await register_patient(client)
    first_cookie = client.cookies.get(COOKIE)
    assert first_cookie

    rotated = await refresh_with(client, first_cookie)  # also a positive control for the helper
    assert rotated.status_code == 200
    assert rotated.json()["access_token"]
    second_cookie = rotated.cookies.get(COOKIE)
    assert second_cookie and second_cookie != first_cookie
    assert (await refresh_with(client, second_cookie)).status_code == 200


async def test_refresh_reuse_after_grace_period_kills_the_session(client: AsyncClient) -> None:
    await register_patient(client)
    first_cookie = client.cookies.get(COOKIE)
    second_cookie = (await refresh_with(client, first_cookie)).cookies.get(COOKIE)

    # A stolen, already-used token replayed later fails AND revokes the live session.
    await _age_used_token(first_cookie, seconds=120)
    assert (await refresh_with(client, first_cookie)).status_code == 401
    assert (await refresh_with(client, second_cookie)).status_code == 401


async def test_refresh_reuse_within_grace_period_is_tolerated(client: AsyncClient) -> None:
    """Two tabs reloading at once send the same cookie; neither should be logged out."""
    await register_patient(client)
    shared_cookie = client.cookies.get(COOKIE)
    tab_one = await refresh_with(client, shared_cookie)
    tab_two = await refresh_with(client, shared_cookie)
    assert tab_one.status_code == tab_two.status_code == 200
    assert (await refresh_with(client, tab_one.cookies.get(COOKIE))).status_code == 200


async def test_refresh_without_cookie_is_401(client: AsyncClient) -> None:
    assert (await client.post("/api/v1/auth/refresh")).status_code == 401


async def test_logout_revokes_session(client: AsyncClient) -> None:
    await register_patient(client)
    cookie = client.cookies.get(COOKIE)
    assert (await client.post("/api/v1/auth/logout")).status_code == 204

    assert (await refresh_with(client, cookie)).status_code == 401


async def test_refresh_tokens_are_stored_hashed(client: AsyncClient) -> None:
    await register_patient(client)
    raw = client.cookies.get(COOKIE)
    async with AsyncSessionLocal() as db:
        stored = await db.scalar(select(RefreshToken).where(RefreshToken.token_hash == hash_refresh_token(raw)))
        assert stored is not None
        assert stored.token_hash != raw
