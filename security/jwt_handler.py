"""
JWT creation and validation.

Access tokens are short-lived and authorise API calls. Refresh tokens are
long-lived, carry a ``jti`` and are tracked (hashed) in the database so they
can be rotated and revoked. The signing secret has no default: ``main.py``
calls ``config.settings.validate_jwt_secret()`` at startup so a missing or
guessable secret stops the server instead of silently making tokens forgeable.
"""

import uuid
from datetime import datetime, timedelta, timezone

from jose import JWTError, jwt

from config.settings import (
    ACCESS_TOKEN_EXPIRE_MINUTES,
    JWT_ALGORITHM,
    JWT_ISSUER,
    JWT_SECRET_KEY,
    REFRESH_TOKEN_EXPIRE_DAYS,
)

ALGORITHM = JWT_ALGORITHM

__all__ = [
    "ACCESS_TOKEN_EXPIRE_MINUTES",
    "REFRESH_TOKEN_EXPIRE_DAYS",
    "create_access_token",
    "create_refresh_token",
    "decode_access_token",
    "decode_refresh_token",
    "create_two_factor_challenge",
    "decode_two_factor_challenge",
]


def _secret() -> str:
    if not JWT_SECRET_KEY:
        raise RuntimeError("JWT_SECRET_KEY is not set.")

    return JWT_SECRET_KEY


# =========================
# CREATE ACCESS TOKEN
# =========================

def create_access_token(user_id: int) -> str:
    """
    Short-lived token used to authorise API requests.

    It deliberately carries no profile data (email, role, ...): the API reads
    the live account on every request, so a demoted or disabled user loses
    access immediately rather than when the token expires.
    """

    now = datetime.now(timezone.utc)

    payload = {
        "sub": str(user_id),
        "type": "access",
        "iss": JWT_ISSUER,
        "iat": int(now.timestamp()),
        "exp": now + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES),
    }

    return jwt.encode(payload, _secret(), algorithm=ALGORITHM)


# =========================
# CREATE REFRESH TOKEN
# =========================

def create_refresh_token(user_id: int):
    """
    Long-lived token used only to obtain new access tokens.

    Returns ``(token, jti, expires_at)``. The caller persists a hash of the
    token keyed by ``jti`` so it can be revoked/rotated; the raw token is never
    stored server-side.
    """

    now = datetime.now(timezone.utc)
    jti = str(uuid.uuid4())
    expires_at = now + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)

    payload = {
        "sub": str(user_id),
        "type": "refresh",
        "iss": JWT_ISSUER,
        "jti": jti,
        "iat": int(now.timestamp()),
        "exp": expires_at,
    }

    token = jwt.encode(payload, _secret(), algorithm=ALGORITHM)

    return token, jti, expires_at


# =========================
# DECODE HELPERS
# =========================

def _decode(token: str, expected_type: str):
    """Return the claims if the token is valid and of the expected type."""

    if not token or not isinstance(token, str):
        return None

    try:
        payload = jwt.decode(
            token,
            _secret(),
            algorithms=[ALGORITHM],
            issuer=JWT_ISSUER,
        )
    except JWTError:
        return None

    if payload.get("type") != expected_type:
        return None

    # Never trust a token missing the claims the API relies on, and never
    # accept a subject that is not a plain integer id.
    if payload.get("exp") is None:
        return None

    try:
        payload["sub"] = int(payload["sub"])
    except (KeyError, TypeError, ValueError):
        return None

    return payload


def decode_access_token(token: str):
    return _decode(token, "access")


def decode_refresh_token(token: str):
    payload = _decode(token, "refresh")

    if payload is None or not payload.get("jti"):
        return None

    return payload


# =========================
# TWO-FACTOR CHALLENGE
# =========================

def create_two_factor_challenge(user_id: int) -> str:
    """Five-minute proof that the password step passed; useless as a session."""

    now = datetime.now(timezone.utc)

    return jwt.encode(
        {
            "sub": str(user_id),
            "type": "2fa_challenge",
            "iss": JWT_ISSUER,
            "iat": int(now.timestamp()),
            "exp": now + timedelta(minutes=5),
        },
        _secret(),
        algorithm=ALGORITHM,
    )


def decode_two_factor_challenge(token: str):
    return _decode(token, "2fa_challenge")
