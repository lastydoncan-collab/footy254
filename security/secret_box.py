"""Encrypt small secrets (the TOTP seed) at rest, keyed from JWT_SECRET_KEY."""

import base64
import hashlib

from cryptography.fernet import Fernet, InvalidToken

from config.settings import JWT_SECRET_KEY


def _fernet() -> Fernet:
    if not JWT_SECRET_KEY:
        raise RuntimeError("JWT_SECRET_KEY is not set.")

    key = base64.urlsafe_b64encode(
        hashlib.sha256(b"footy254-secret-box:" + JWT_SECRET_KEY.encode()).digest()
    )
    return Fernet(key)


def seal(plain: str) -> str:
    return _fernet().encrypt(plain.encode()).decode()


def unseal(token: str) -> str | None:
    try:
        return _fernet().decrypt(token.encode()).decode()
    except (InvalidToken, ValueError):
        return None
