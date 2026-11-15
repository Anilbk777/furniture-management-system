"""Password hashing + JWT helpers. Pure functions: no database, no HTTP."""

import hashlib
import uuid
from datetime import datetime, timedelta, timezone

import jwt
from pwdlib import PasswordHash

from app.core.config import settings

_hasher = PasswordHash.recommended()  # argon2


# ---------- passwords ----------
def hash_password(password: str) -> str:
    return _hasher.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    return _hasher.verify(password, password_hash)


# Checked against when the account doesn't exist, so login takes the same time
# either way and doesn't reveal which phone numbers / emails are registered.
DUMMY_HASH = hash_password("not-a-real-password")


# ----------------- Generate tokens ---------------
def _create_token(
    user_id: uuid.UUID,
    token_type: str,
    secret: str,
    lifetime: timedelta,
    extra: dict | None = None,
):
    now = datetime.now(timezone.utc)
    expires_at = now + lifetime
    payload = {
        "sub": str(user_id),
        "type": token_type,
        "jti": uuid.uuid4().hex,  # makes every token unique, even within the same second
        "iat": now,
        "exp": expires_at,
        **(extra or {}),
    }
    return jwt.encode(payload, secret, algorithm=settings.jwt_algorithm), expires_at


def create_access_token(user_id:uuid.UUID) -> str:
    token, _ = _create_token(
        user_id,
        "access",
        settings.jwt_access_secret.get_secret_value(),
        timedelta(minutes=settings.access_token_expire_minutes),
    )
    return token


def create_refresh_token(user_id: uuid.UUID) -> tuple[str, datetime]:
    """Returns (token, expires_at). The caller stores hash_token(token) in the DB."""
    return _create_token(
        user_id,
        "refresh",
        settings.jwt_refresh_secret.get_secret_value(),
        timedelta(days=settings.refresh_token_expire_days),
    )

# ----------------- Decode tokens ---------------


def _decode(token: str, secret: str, expected_type: str) -> dict:
    """Raises jwt.InvalidTokenError (jwt.ExpiredSignatureError is a subclass)."""
    payload = jwt.decode(
        token,
        secret,
        algorithms=[settings.jwt_algorithm],
        options={"require": ["exp", "sub", "type"]},
    )
    if payload["type"] != expected_type:
        raise jwt.InvalidTokenError("Wrong token type")
    return payload


def decode_access_token(token: str) -> dict:
    return _decode(token, settings.jwt_access_secret.get_secret_value(), "access")


def decode_refresh_token(token: str) -> dict:
    return _decode(token, settings.jwt_refresh_secret.get_secret_value(), "refresh")


# -------------- Hash Token ----------------------------
def hash_token(token: str) -> str:
    """SHA-256 of a token. We store this, never the token itself."""
    return hashlib.sha256(token.encode()).hexdigest()
