"""Account API: profile editing, preferences and two-factor authentication."""

import logging
import re

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field, field_validator

from database import account_repository as repo
from database.user_repository import DuplicateUserError, get_user_by_email, get_user_by_id
from security import totp
from security.dependencies import get_current_user, serialize_user
from security.hashing import verify_password
from security.rate_limiter import limiter
from security.secret_box import seal, unseal

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/account", tags=["Account"])

_USERNAME_RE = re.compile(r"^[A-Za-z0-9_.-]{3,30}$")
LEAGUES = {
    "All Leagues",
    "Premier League",
    "La Liga",
    "Serie A",
    "Bundesliga",
    "Ligue 1",
    "Champions League",
}


def _strip(value):
    return value.strip() if isinstance(value, str) else value


class ProfileRequest(BaseModel):
    first_name: str = Field(min_length=1, max_length=100)
    last_name: str = Field(min_length=1, max_length=100)
    username: str = Field(min_length=3, max_length=50)
    phone_number: str | None = Field(default=None, max_length=20)

    _strip_all = field_validator(
        "first_name", "last_name", "username", "phone_number", mode="before"
    )(_strip)

    @field_validator("username")
    @classmethod
    def _valid_username(cls, value):
        if not _USERNAME_RE.match(value):
            raise ValueError(
                "Username must be 3-30 characters: letters, numbers, dots, "
                "underscores or hyphens."
            )
        return value

    @field_validator("phone_number")
    @classmethod
    def _valid_phone(cls, value):
        if not value:
            return None
        digits = re.sub(r"[\s\-()]", "", value)
        if not re.fullmatch(r"\+?\d{9,15}", digits):
            raise ValueError("Enter a valid phone number, e.g. 0712345678.")
        return digits


class PreferencesRequest(BaseModel):
    notifications_enabled: bool = True
    match_alerts: bool = True
    login_alerts: bool = True
    favorite_league: str = "All Leagues"
    refresh_rate_seconds: int = 30

    @field_validator("favorite_league")
    @classmethod
    def _league(cls, value):
        if value not in LEAGUES:
            raise ValueError("Unknown league.")
        return value

    @field_validator("refresh_rate_seconds")
    @classmethod
    def _rate(cls, value):
        if value not in (15, 30, 60):
            raise ValueError("Refresh rate must be 15, 30 or 60 seconds.")
        return value


class PasswordOnly(BaseModel):
    password: str = Field(min_length=1, max_length=256)


class CodeOnly(BaseModel):
    code: str = Field(min_length=6, max_length=20)


class DisableRequest(BaseModel):
    password: str = Field(min_length=1, max_length=256)
    code: str = Field(min_length=6, max_length=20)


def _check_password(current_user, password: str):
    row = get_user_by_email(current_user["email"])
    if row is None or not verify_password(password, row["password_hash"]):
        raise HTTPException(status_code=400, detail="Password is incorrect.")


# ==========================================
# PROFILE + PREFERENCES
# ==========================================

@router.patch("/profile")
@limiter.limit("20/minute")
def update_profile(
    request: Request,
    payload: ProfileRequest,
    current_user=Depends(get_current_user),
):
    try:
        repo.update_profile(
            current_user["id"],
            payload.first_name,
            payload.last_name,
            payload.username,
            payload.phone_number,
        )
    except DuplicateUserError:
        raise HTTPException(status_code=409, detail="That username is already taken.")

    fresh = get_user_by_id(current_user["id"])
    return {"success": True, "message": "Profile updated.", "user": serialize_user(fresh)}


@router.put("/preferences")
@limiter.limit("60/minute")
def update_preferences(
    request: Request,
    payload: PreferencesRequest,
    current_user=Depends(get_current_user),
):
    repo.update_preferences(
        current_user["id"],
        payload.notifications_enabled,
        payload.match_alerts,
        payload.login_alerts,
        payload.favorite_league,
        payload.refresh_rate_seconds,
    )

    fresh = get_user_by_id(current_user["id"])
    return {"success": True, "message": "Preferences saved.", "user": serialize_user(fresh)}


# ==========================================
# TWO-FACTOR AUTHENTICATION
# ==========================================

@router.post("/2fa/setup")
@limiter.limit("10/minute")
def two_factor_setup(
    request: Request,
    payload: PasswordOnly,
    current_user=Depends(get_current_user),
):
    """Start enrolment: returns the secret to add to an authenticator app."""

    _check_password(current_user, payload.password)

    state = repo.get_two_factor_row(current_user["id"])
    if state and state["totp_enabled"]:
        raise HTTPException(status_code=409, detail="Two-factor is already on.")

    secret = totp.new_secret()
    repo.store_pending_totp_secret(current_user["id"], seal(secret))

    return {
        "success": True,
        "secret": secret,
        "otpauth_uri": totp.provisioning_uri(secret, current_user["email"]),
    }


@router.post("/2fa/enable")
@limiter.limit("10/minute")
def two_factor_enable(
    request: Request,
    payload: CodeOnly,
    current_user=Depends(get_current_user),
):
    state = repo.get_two_factor_row(current_user["id"])

    if not state or state["totp_enabled"] or not state["totp_secret"]:
        raise HTTPException(status_code=400, detail="Start two-factor setup first.")

    secret = unseal(state["totp_secret"])
    step = totp.verify(secret, payload.code) if secret else None

    if step is None:
        raise HTTPException(
            status_code=400,
            detail="That code didn't match. Check your phone's clock and try again.",
        )

    codes = totp.new_recovery_codes()
    repo.enable_totp(
        current_user["id"], step, [totp.hash_recovery_code(c) for c in codes]
    )

    return {
        "success": True,
        "message": "Two-factor authentication is on.",
        # Shown exactly once; only hashes are stored.
        "recovery_codes": codes,
    }


@router.post("/2fa/disable")
@limiter.limit("10/minute")
def two_factor_disable(
    request: Request,
    payload: DisableRequest,
    current_user=Depends(get_current_user),
):
    _check_password(current_user, payload.password)

    state = repo.get_two_factor_row(current_user["id"])
    if not state or not state["totp_enabled"]:
        raise HTTPException(status_code=400, detail="Two-factor is not on.")

    if not verify_second_factor(current_user["id"], state, payload.code):
        raise HTTPException(status_code=400, detail="That code didn't match.")

    repo.disable_totp(current_user["id"])
    return {"success": True, "message": "Two-factor authentication is off."}


def verify_second_factor(user_id: int, state, code: str) -> bool:
    """Accept a current authenticator code or an unused recovery code."""

    secret = unseal(state["totp_secret"]) if state["totp_secret"] else None

    if secret:
        step = totp.verify(secret, code, last_step=state["totp_last_step"] or 0)
        if step is not None and repo.advance_totp_step(user_id, step):
            return True

    cleaned = "".join(ch for ch in code if ch.isalnum())
    if len(cleaned) == 10:
        return repo.consume_recovery_code(user_id, totp.hash_recovery_code(cleaned))

    return False
