"""
Password hashing (bcrypt).

This talks to the ``bcrypt`` package directly instead of through ``passlib``.
passlib 1.7.x is unmaintained and breaks against current ``bcrypt`` releases
(its backend self-test passes an over-long secret that bcrypt 5 rejects, so
registration and login crash with ``ValueError``).

Hashes created by the previous passlib-based version (``$2b$12$...``) verify
unchanged, so existing users keep their passwords.
"""

import bcrypt

from config.settings import BCRYPT_ROUNDS, PASSWORD_MAX_BYTES

_dummy_hash: bytes | None = None


def _prepare(password: str) -> bytes:
    # bcrypt only ever uses the first 72 bytes. Truncating explicitly keeps
    # verification identical to what the old passlib setup did for legacy
    # accounts; new passwords longer than this are rejected by the policy.
    return password.encode("utf-8")[:PASSWORD_MAX_BYTES]


def hash_password(password: str) -> str:
    return bcrypt.hashpw(
        _prepare(password),
        bcrypt.gensalt(rounds=BCRYPT_ROUNDS),
    ).decode("ascii")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    if not hashed_password:
        return False

    try:
        return bcrypt.checkpw(
            _prepare(plain_password),
            hashed_password.encode("utf-8"),
        )
    except (ValueError, TypeError):
        # Malformed stored hash: treat as a failed login, never as a 500.
        return False


def needs_rehash(hashed_password: str) -> bool:
    """True when the stored hash uses a lower cost than the current setting."""

    try:
        return int(hashed_password.split("$")[2]) < BCRYPT_ROUNDS
    except (IndexError, ValueError, AttributeError):
        return False


def verify_dummy(plain_password: str) -> None:
    """
    Burn the same CPU time as a real verification.

    Called when the account does not exist so the response time does not reveal
    whether an email address is registered.
    """

    global _dummy_hash

    if _dummy_hash is None:
        _dummy_hash = bcrypt.hashpw(
            b"footy254-timing-equaliser",
            bcrypt.gensalt(rounds=BCRYPT_ROUNDS),
        )

    try:
        bcrypt.checkpw(_prepare(plain_password), _dummy_hash)
    except (ValueError, TypeError):
        pass
