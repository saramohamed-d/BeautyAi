"""
Password hashing and token primitives.

Design decisions:
- bcrypt (cost 12) for passwords. bcrypt only uses the first 72 bytes of
  a password, so the API rejects longer passwords instead of silently
  truncating them (see schemas/auth.py).
- Access tokens are short-lived JWTs (HS256) carrying only the user id
  and role. They are never stored server-side.
- Refresh tokens are random opaque strings. Only their SHA-256 hash is
  stored, so a database leak doesn't hand out live sessions. SHA-256 (not
  bcrypt) is fine here because the tokens have 256 bits of entropy and
  can't be guessed.
"""

import hashlib
import secrets
import uuid
from datetime import datetime, timedelta, timezone

import bcrypt
import jwt

from app.core.config import get_settings
from app.models.enums import UserRole

BCRYPT_ROUNDS = 12
ACCESS_TOKEN_TYPE = "access"

# Checked against when the login identifier doesn't exist, so a failed
# login takes the same time whether or not the account exists.
_DUMMY_HASH = bcrypt.hashpw(b"not-a-real-password", bcrypt.gensalt(BCRYPT_ROUNDS))


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt(BCRYPT_ROUNDS)).decode("utf-8")


def verify_password(password: str, password_hash: str | None) -> bool:
    if password_hash is None:
        bcrypt.checkpw(password.encode("utf-8"), _DUMMY_HASH)
        return False
    return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))


def create_access_token(user_id: uuid.UUID, role: UserRole) -> tuple[str, int]:
    """Returns (token, lifetime in seconds)."""
    settings = get_settings()
    lifetime = settings.jwt_access_token_expire_minutes * 60
    now = datetime.now(timezone.utc)
    payload = {
        "sub": str(user_id),
        "role": role.value,
        "type": ACCESS_TOKEN_TYPE,
        "iat": now,
        "exp": now + timedelta(seconds=lifetime),
    }
    return jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm), lifetime


def decode_access_token(token: str) -> dict | None:
    """Returns the payload, or None if the token is invalid, expired or not an access token."""
    settings = get_settings()
    try:
        payload = jwt.decode(
            token,
            settings.jwt_secret_key,
            algorithms=[settings.jwt_algorithm],
            options={"require": ["sub", "exp", "type"]},
        )
    except jwt.PyJWTError:
        return None
    return payload if payload.get("type") == ACCESS_TOKEN_TYPE else None


def new_refresh_token() -> str:
    return secrets.token_urlsafe(32)


def hash_refresh_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()
