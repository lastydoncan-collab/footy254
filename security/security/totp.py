"""RFC 6238 time-based one-time passwords using only the standard library."""

import base64
import hashlib
import hmac
import secrets
import struct
import time
from urllib.parse import quote

STEP_SECONDS = 30
DIGITS = 6


def new_secret() -> str:
    """160-bit random secret, base32 encoded (what authenticator apps expect)."""

    return base64.b32encode(secrets.token_bytes(20)).decode("ascii").rstrip("=")


def _code_for_step(secret: str, step: int) -> str:
    padded = secret + "=" * (-len(secret) % 8)
    key = base64.b32decode(padded, casefold=True)
    digest = hmac.new(key, struct.pack(">Q", step), hashlib.sha1).digest()
    offset = digest[-1] & 0x0F
    value = struct.unpack(">I", digest[offset : offset + 4])[0] & 0x7FFFFFFF
    return str(value % (10**DIGITS)).zfill(DIGITS)


def current_step(now: float | None = None) -> int:
    return int((time.time() if now is None else now) // STEP_SECONDS)


def verify(secret: str, code: str, last_step: int = 0, now: float | None = None):
    """
    Check a user-supplied code, allowing one step of clock drift either way.

    Returns the matching step (to be stored as ``last_step``) or ``None``.
    A step at or before ``last_step`` is rejected so a code works once.
    """

    code = "".join(ch for ch in (code or "") if ch.isdigit())

    if len(code) != DIGITS:
        return None

    step_now = current_step(now)

    for step in (step_now, step_now - 1, step_now + 1):
        if step <= last_step:
            continue
        if hmac.compare_digest(_code_for_step(secret, step), code):
            return step

    return None


def provisioning_uri(secret: str, account: str, issuer: str = "FOOTY254") -> str:
    return (
        f"otpauth://totp/{quote(issuer)}:{quote(account)}"
        f"?secret={secret}&issuer={quote(issuer)}&digits={DIGITS}&period={STEP_SECONDS}"
    )


def new_recovery_codes(count: int = 8) -> list[str]:
    alphabet = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
    return [
        "".join(secrets.choice(alphabet) for _ in range(5))
        + "-"
        + "".join(secrets.choice(alphabet) for _ in range(5))
        for _ in range(count)
    ]


def hash_recovery_code(code: str) -> str:
    normalised = "".join(ch for ch in code.upper() if ch.isalnum())
    return hashlib.sha256(normalised.encode()).hexdigest()
