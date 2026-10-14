"""
Authentication API: register, login, token refresh, logout, sessions,
password change and password reset.

Browser clients authenticate with httpOnly cookies (never readable by
JavaScript, so XSS cannot steal them). Refresh tokens rotate on every use and
reuse of an already-rotated token revokes the whole session family.
"""

import logging
import re
import secrets
import threading
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request, Response
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field, field_validator

from config.settings import (
    ACCESS_COOKIE_NAME,
    ACCESS_TOKEN_EXPIRE_MINUTES,
    COOKIE_DOMAIN,
    COOKIE_SAMESITE,
    COOKIE_SECURE,
    LEGACY_REFRESH_COOKIE_PATH,
    LOCKOUT_MINUTES,
    MAX_FAILED_LOGINS,
    MAX_SESSIONS_PER_USER,
    PASSWORD_RESET_COOLDOWN_SECONDS,
    PASSWORD_RESET_EXPIRE_MINUTES,
    REFRESH_COOKIE_NAME,
    REFRESH_COOKIE_PATH,
    REFRESH_REUSE_GRACE_SECONDS,
    REFRESH_TOKEN_EXPIRE_DAYS,
)
from database.auth_tokens_repository import (
    claim_refresh_token,
    consume_password_reset_token,
    create_password_reset_token,
    enforce_session_limit,
    get_refresh_token,
    get_valid_password_reset_token,
    is_expired,
    list_active_sessions,
    reset_requested_recently,
    revoke_all_refresh_tokens_for_user,
    revoke_all_refresh_tokens_for_user_except,
    revoke_refresh_token,
    revoke_session_owned_by_user,
    set_replaced_by,
    store_refresh_token,
    token_matches,
)
from database.login_attempts_repository import (
    clear_failed_logins,
    get_lock_remaining_seconds,
    record_failed_login,
)
from database.user_repository import (
    DuplicateUserError,
    create_user,
    email_exists,
    get_user_by_email,
    get_user_by_id,
    replace_password_hash_if_unchanged,
    update_last_login,
    update_password,
    username_exists,
)
from security.dependencies import get_current_user, serialize_user
from security.hashing import (
    hash_password,
    needs_rehash,
    verify_dummy,
    verify_password,
)
from security.jwt_handler import (
    create_access_token,
    create_refresh_token,
    create_two_factor_challenge,
    decode_refresh_token,
    decode_two_factor_challenge,
)
from security.password_policy import validate_password
from security.rate_limiter import limiter
from services.email_service import send_login_alert_email, send_password_reset_email

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/auth",
    tags=["Authentication"],
)

_EMAIL_RE = re.compile(r"^[^@\s]{1,64}@[^@\s]+\.[^@\s]{2,}$")
_USERNAME_RE = re.compile(r"^[A-Za-z0-9_.-]{3,30}$")


# ==========================================
# REQUEST MODELS
# ==========================================

def _strip(value):
    return value.strip() if isinstance(value, str) else value


class RegisterRequest(BaseModel):
    first_name: str = Field(min_length=1, max_length=100)
    last_name: str = Field(min_length=1, max_length=100)
    username: str = Field(min_length=3, max_length=50)
    email: str = Field(min_length=3, max_length=254)
    # Length/strength rules live in security.password_policy so the message the
    # user sees is specific; this cap only bounds the payload size.
    password: str = Field(min_length=1, max_length=256)

    _strip_fields = field_validator(
        "first_name", "last_name", "username", "email", mode="before"
    )(_strip)

    @field_validator("email")
    @classmethod
    def _valid_email(cls, value: str) -> str:
        value = value.lower()

        if not _EMAIL_RE.match(value):
            raise ValueError("Enter a valid email address.")

        return value

    @field_validator("username")
    @classmethod
    def _valid_username(cls, value: str) -> str:
        if not _USERNAME_RE.match(value):
            raise ValueError(
                "Username must be 3-30 characters: letters, numbers, "
                "dots, underscores or hyphens."
            )

        return value


class LoginRequest(BaseModel):
    email: str = Field(min_length=3, max_length=254)
    password: str = Field(min_length=1, max_length=256)

    _strip_email = field_validator("email", mode="before")(_strip)

    @field_validator("email")
    @classmethod
    def _lower_email(cls, value: str) -> str:
        return value.lower()


class TwoFactorLoginRequest(BaseModel):
    challenge: str = Field(min_length=1, max_length=1024)
    code: str = Field(min_length=6, max_length=20)


class ChangePasswordRequest(BaseModel):
    current_password: str = Field(min_length=1, max_length=256)
    new_password: str = Field(min_length=1, max_length=256)


class ForgotPasswordRequest(BaseModel):
    email: str = Field(min_length=3, max_length=254)

    _strip_email = field_validator("email", mode="before")(_strip)

    @field_validator("email")
    @classmethod
    def _lower_email(cls, value: str) -> str:
        return value.lower()


class ResetPasswordRequest(BaseModel):
    token: str = Field(min_length=1, max_length=512)
    new_password: str = Field(min_length=1, max_length=256)


# ==========================================
# COOKIE HELPERS
# ==========================================

def _set_auth_cookies(response: Response, access_token: str, refresh_token: str):
    common = {
        "httponly": True,
        "secure": COOKIE_SECURE,
        "samesite": COOKIE_SAMESITE,
        "domain": COOKIE_DOMAIN,
    }

    response.set_cookie(
        key=ACCESS_COOKIE_NAME,
        value=access_token,
        max_age=ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        path="/",
        **common,
    )

    response.set_cookie(
        key=REFRESH_COOKIE_NAME,
        value=refresh_token,
        max_age=REFRESH_TOKEN_EXPIRE_DAYS * 24 * 60 * 60,
        # Scoped to the auth endpoints so it is never sent on ordinary API calls.
        path=REFRESH_COOKIE_PATH,
        **common,
    )


def _clear_auth_cookies(response: Response):
    response.delete_cookie(ACCESS_COOKIE_NAME, path="/", domain=COOKIE_DOMAIN)
    response.delete_cookie(REFRESH_COOKIE_NAME, path=REFRESH_COOKIE_PATH, domain=COOKIE_DOMAIN)

    # Cookie set by releases from before the /api prefix existed.
    if LEGACY_REFRESH_COOKIE_PATH != REFRESH_COOKIE_PATH:
        response.delete_cookie(
            REFRESH_COOKIE_NAME,
            path=LEGACY_REFRESH_COOKIE_PATH,
            domain=COOKIE_DOMAIN,
        )


def _session_expired(detail: str) -> JSONResponse:
    """
    401 that ALSO clears the auth cookies.

    Cookies set on an injected ``Response`` are discarded when an
    HTTPException is raised, so a response object has to be returned instead.
    """

    response = JSONResponse(status_code=401, content={"detail": detail})
    _clear_auth_cookies(response)

    return response


def _client_ip(request: Request) -> str | None:
    return request.client.host if request.client else None


def _issue_session(response: Response, user, request: Request) -> str:
    """Create access + refresh tokens, persist the refresh hash, set cookies."""

    access_token = create_access_token(user["id"])
    refresh_token, jti, expires_at = create_refresh_token(user["id"])

    store_refresh_token(
        user_id=user["id"],
        jti=jti,
        token=refresh_token,
        expires_at=expires_at,
        user_agent=request.headers.get("user-agent"),
        ip_address=_client_ip(request),
    )

    enforce_session_limit(user["id"], MAX_SESSIONS_PER_USER)

    _set_auth_cookies(response, access_token, refresh_token)

    if user.get("login_alerts", True):
        # Off the request thread: SMTP can take seconds and must never delay
        # (or break) a sign-in.
        threading.Thread(
            target=_safe_login_alert,
            args=(
                user["email"],
                _describe_device(request.headers.get("user-agent")),
                _client_ip(request),
            ),
            daemon=True,
        ).start()

    return jti


def _safe_login_alert(email, device, ip):
    try:
        send_login_alert_email(email, device, ip)
    except Exception:
        logger.exception("Login alert email failed")


def _current_refresh_jti(request: Request) -> str | None:
    raw = request.cookies.get(REFRESH_COOKIE_NAME)

    if not raw:
        return None

    payload = decode_refresh_token(raw)

    return payload["jti"] if payload else None


# ==========================================
# REGISTER
# ==========================================

@router.post("/register")
@limiter.limit("5/minute")
def register(request: Request, payload: RegisterRequest):

    error = validate_password(
        payload.password,
        email=payload.email,
        username=payload.username,
    )

    if error:
        raise HTTPException(status_code=422, detail=error)

    if email_exists(payload.email):
        raise HTTPException(status_code=400, detail="Email already exists.")

    if username_exists(payload.username):
        raise HTTPException(status_code=400, detail="Username already exists.")

    try:
        user_id = create_user(
            payload.first_name,
            payload.last_name,
            payload.username,
            payload.email,
            hash_password(payload.password),
        )
    except DuplicateUserError as exc:
        # Lost a race with a simultaneous registration.
        raise HTTPException(
            status_code=400,
            detail=f"{exc.field.capitalize()} already exists.",
        )

    return {
        "success": True,
        "message": "Account created successfully.",
        "user": {
            "id": user_id,
            "first_name": payload.first_name,
            "last_name": payload.last_name,
            "username": payload.username,
            "email": payload.email,
        },
    }


# ==========================================
# LOGIN
# ==========================================

def _lock_message(seconds: int) -> str:
    minutes = max(1, (seconds + 59) // 60)

    return (
        "Too many failed sign-in attempts. "
        f"Try again in {minutes} minute{'s' if minutes != 1 else ''}."
    )


def _login_failed(email: str):
    """Count a failure; raises 429 once locked, otherwise the generic 401."""

    locked_for = record_failed_login(email, MAX_FAILED_LOGINS, LOCKOUT_MINUTES)

    if locked_for:
        raise HTTPException(
            status_code=429,
            detail=_lock_message(locked_for),
            headers={"Retry-After": str(locked_for)},
        )

    raise HTTPException(status_code=401, detail="Invalid email or password.")


@router.post("/login")
@limiter.limit("10/minute")
def login(request: Request, payload: LoginRequest, response: Response):

    email = payload.email

    remaining = get_lock_remaining_seconds(email)

    if remaining:
        raise HTTPException(
            status_code=429,
            detail=_lock_message(remaining),
            headers={"Retry-After": str(remaining)},
        )

    user = get_user_by_email(email)

    if user is None:
        # Spend the same time a real check would, so response time does not
        # reveal whether the address is registered.
        verify_dummy(payload.password)
        _login_failed(email)

    if not verify_password(payload.password, user["password_hash"]):
        _login_failed(email)

    # Only someone who knows the password learns the account is disabled.
    if not user["is_active"]:
        raise HTTPException(status_code=403, detail="Account has been disabled.")

    clear_failed_logins(email)

    if needs_rehash(user["password_hash"]):
        replace_password_hash_if_unchanged(
            user["id"],
            user["password_hash"],
            hash_password(payload.password),
        )

    if user.get("totp_enabled"):
        # Password was right, but no session yet: the second step finishes it.
        return {
            "success": True,
            "two_factor_required": True,
            "challenge": create_two_factor_challenge(user["id"]),
            "message": "Enter the 6-digit code from your authenticator app.",
        }

    update_last_login(user["id"])

    _issue_session(response, user, request)

    return {
        "success": True,
        "message": "Login successful.",
        "user": serialize_user(user),
    }


@router.post("/login/2fa")
@limiter.limit("10/minute")
def login_two_factor(
    request: Request, payload: TwoFactorLoginRequest, response: Response
):
    from api.account import verify_second_factor
    from database import account_repository

    claims = decode_two_factor_challenge(payload.challenge)

    if claims is None:
        raise HTTPException(
            status_code=401,
            detail="Your sign-in expired. Enter your password again.",
        )

    user = get_user_by_id(claims["sub"])

    if user is None or not user["is_active"] or not user.get("totp_enabled"):
        raise HTTPException(status_code=401, detail="Sign-in failed.")

    remaining = get_lock_remaining_seconds(user["email"])

    if remaining:
        raise HTTPException(
            status_code=429,
            detail=_lock_message(remaining),
            headers={"Retry-After": str(remaining)},
        )

    state = account_repository.get_two_factor_row(user["id"])

    if not state or not verify_second_factor(user["id"], state, payload.code):
        # Wrong codes count toward the same lockout as wrong passwords.
        locked_for = record_failed_login(
            user["email"], MAX_FAILED_LOGINS, LOCKOUT_MINUTES
        )

        if locked_for:
            raise HTTPException(
                status_code=429,
                detail=_lock_message(locked_for),
                headers={"Retry-After": str(locked_for)},
            )

        raise HTTPException(status_code=401, detail="That code didn't match.")

    clear_failed_logins(user["email"])
    update_last_login(user["id"])
    _issue_session(response, user, request)

    return {
        "success": True,
        "message": "Login successful.",
        "user": serialize_user(user),
    }


# ==========================================
# REFRESH
# ==========================================

@router.post("/refresh")
@limiter.limit("60/minute")
def refresh(request: Request, response: Response):
    """
    Exchange a valid refresh token (cookie) for a new access + refresh pair.

    Tokens rotate on every use. Presenting an already-rotated token is
    reuse: a legitimate client never does it, so outside a short grace window
    (two tabs racing) it is treated as theft and every session of the account
    is revoked.
    """

    raw_token = request.cookies.get(REFRESH_COOKIE_NAME)

    if not raw_token:
        raise HTTPException(status_code=401, detail="Not authenticated.")

    payload = decode_refresh_token(raw_token)

    if payload is None:
        return _session_expired("Invalid or expired session.")

    jti = payload["jti"]
    stored = get_refresh_token(jti)

    if stored is None or not token_matches(stored, raw_token):
        return _session_expired("Session no longer valid.")

    if is_expired(stored):
        return _session_expired("Session expired. Please sign in again.")

    if stored["revoked_at"] is not None:
        age = (datetime.now(timezone.utc) - stored["revoked_at"]).total_seconds()

        if stored["replaced_by_jti"] and age <= REFRESH_REUSE_GRACE_SECONDS:
            # Benign race: another request/tab just rotated this token and its
            # response is delivering the new cookies. Do not log the user out.
            return {"success": True, "concurrent": True}

        if stored["replaced_by_jti"]:
            logger.warning(
                "Refresh token reuse detected for user %s; revoking all sessions.",
                stored["user_id"],
            )
            revoke_all_refresh_tokens_for_user(stored["user_id"])

        return _session_expired("Session no longer valid.")

    claimed = claim_refresh_token(jti)

    if claimed is None:
        # Lost the rotation race to a simultaneous identical request.
        return {"success": True, "concurrent": True}

    user = get_user_by_id(claimed["user_id"])

    if user is None or not user["is_active"]:
        revoke_all_refresh_tokens_for_user(claimed["user_id"])
        return _session_expired("Account unavailable.")

    new_jti = _issue_session(response, user, request)
    set_replaced_by(jti, new_jti)

    return {"success": True}


# ==========================================
# LOGOUT
# ==========================================

@router.post("/logout")
def logout(request: Request, response: Response):
    jti = _current_refresh_jti(request)

    if jti:
        revoke_refresh_token(jti)

    _clear_auth_cookies(response)

    return {"success": True, "message": "Logged out."}


@router.post("/logout-all")
def logout_all(
    response: Response,
    current_user=Depends(get_current_user),
):
    """Sign out of every device, including this one."""

    revoke_all_refresh_tokens_for_user(current_user["id"])
    _clear_auth_cookies(response)

    return {"success": True, "message": "Signed out of all devices."}


# ==========================================
# ACTIVE SESSIONS
# ==========================================

def _describe_device(user_agent: str | None) -> str:
    """Best-effort, dependency-free human label for a User-Agent string."""

    if not user_agent:
        return "Unknown device"

    ua = user_agent.lower()

    # Order matters: iPhone/iPad user agents contain "like Mac OS X", and
    # Android user agents contain "Linux".
    if "iphone" in ua:
        os_label = "iPhone"
    elif "ipad" in ua:
        os_label = "iPad"
    elif "android" in ua:
        os_label = "Android"
    elif "windows" in ua:
        os_label = "Windows"
    elif "mac os" in ua or "macintosh" in ua:
        os_label = "Mac"
    elif "cros" in ua:
        os_label = "ChromeOS"
    elif "linux" in ua:
        os_label = "Linux"
    else:
        os_label = "Unknown OS"

    if "edg/" in ua or "edga/" in ua or "edgios/" in ua:
        browser_label = "Edge"
    elif "opr/" in ua or "opera" in ua:
        browser_label = "Opera"
    elif "samsungbrowser" in ua:
        browser_label = "Samsung Internet"
    elif "firefox/" in ua or "fxios" in ua:
        browser_label = "Firefox"
    elif "chrome/" in ua or "crios" in ua:
        browser_label = "Chrome"
    elif "safari/" in ua:
        browser_label = "Safari"
    else:
        browser_label = "Browser"

    return f"{os_label} \u00b7 {browser_label}"


@router.get("/sessions")
def list_sessions(
    request: Request,
    current_user=Depends(get_current_user),
):
    """Powers the Security page's Active Devices list."""

    current_jti = _current_refresh_jti(request)

    return {
        "success": True,
        "sessions": [
            {
                "id": str(row["jti"]),
                "device": _describe_device(row["user_agent"]),
                "ip_address": row["ip_address"],
                "created_at": row["created_at"],
                "expires_at": row["expires_at"],
                "is_current": str(row["jti"]) == current_jti,
            }
            for row in list_active_sessions(current_user["id"])
        ],
    }


@router.delete("/sessions/{jti}")
def revoke_session(
    jti: str,
    current_user=Depends(get_current_user),
):
    """Revoke a single device/session, e.g. a lost or unrecognised device."""

    if not revoke_session_owned_by_user(current_user["id"], jti):
        raise HTTPException(status_code=404, detail="Session not found.")

    return {"success": True, "message": "Session revoked."}


@router.post("/sessions/revoke-others")
def revoke_other_sessions(
    request: Request,
    current_user=Depends(get_current_user),
):
    """'Log out of all other devices' - keeps the current session active."""

    current_jti = _current_refresh_jti(request)

    if current_jti:
        revoke_all_refresh_tokens_for_user_except(current_user["id"], current_jti)
    else:
        # No refresh session to preserve (e.g. a Bearer-token client): the only
        # safe fallback is to revoke everything.
        revoke_all_refresh_tokens_for_user(current_user["id"])

    return {"success": True, "message": "Other sessions have been logged out."}


# ==========================================
# CURRENT AUTHENTICATED USER
# ==========================================

@router.get("/me")
def get_me(current_user=Depends(get_current_user)):
    return {"success": True, "user": current_user}


# ==========================================
# CHANGE PASSWORD
# ==========================================

@router.post("/change-password")
@limiter.limit("5/minute")
def change_password(
    request: Request,
    payload: ChangePasswordRequest,
    response: Response,
    current_user=Depends(get_current_user),
):
    """Change an authenticated user's password after verifying the old one."""

    user = get_user_by_email(current_user["email"])

    if user is None or not verify_password(
        payload.current_password,
        user["password_hash"],
    ):
        raise HTTPException(
            status_code=400,
            detail="Current password is incorrect.",
        )

    error = validate_password(
        payload.new_password,
        email=user["email"],
        username=user["username"],
    )

    if error:
        raise HTTPException(status_code=422, detail=error)

    if verify_password(payload.new_password, user["password_hash"]):
        raise HTTPException(
            status_code=400,
            detail="Choose a password different from the current one.",
        )

    update_password(user["id"], hash_password(payload.new_password))

    # Force re-login everywhere; outstanding access tokens are void as well
    # because they predate password_changed_at.
    revoke_all_refresh_tokens_for_user(user["id"])
    _clear_auth_cookies(response)

    return {
        "success": True,
        "message": "Password updated successfully. Please sign in again.",
    }


# ==========================================
# FORGOT / RESET PASSWORD
# ==========================================

@router.post("/forgot-password")
@limiter.limit("5/minute")
def forgot_password(
    request: Request,
    payload: ForgotPasswordRequest,
    background: BackgroundTasks,
):
    """
    Always answers with the same message, whether or not the email exists, so
    the endpoint cannot be used to enumerate registered accounts. The email is
    sent in the background so response time does not leak existence either.
    """

    user = get_user_by_email(payload.email)

    if (
        user is not None
        and user["is_active"]
        and not reset_requested_recently(user["id"], PASSWORD_RESET_COOLDOWN_SECONDS)
    ):
        raw_token = secrets.token_urlsafe(48)
        expires_at = datetime.now(timezone.utc) + timedelta(
            minutes=PASSWORD_RESET_EXPIRE_MINUTES
        )

        create_password_reset_token(user["id"], raw_token, expires_at)
        background.add_task(send_password_reset_email, user["email"], raw_token)

    return {
        "success": True,
        "message": (
            "If an account exists for that email, "
            "a password reset link has been sent."
        ),
    }


@router.post("/reset-password")
@limiter.limit("10/minute")
def reset_password(request: Request, payload: ResetPasswordRequest):
    invalid = HTTPException(
        status_code=400,
        detail="This reset link is invalid or has expired.",
    )

    row = get_valid_password_reset_token(payload.token)

    if row is None:
        raise invalid

    user = get_user_by_id(row["user_id"])

    if user is None or not user["is_active"]:
        raise invalid

    # Validate BEFORE consuming the token so a too-weak password lets the user
    # try again with the same link.
    error = validate_password(
        payload.new_password,
        email=user["email"],
        username=user["username"],
    )

    if error:
        raise HTTPException(status_code=422, detail=error)

    # Single-use is enforced atomically by the database.
    if consume_password_reset_token(payload.token) is None:
        raise invalid

    update_password(user["id"], hash_password(payload.new_password))
    revoke_all_refresh_tokens_for_user(user["id"])
    clear_failed_logins(user["email"].lower())

    return {
        "success": True,
        "message": "Password has been reset. You can now sign in.",
    }
