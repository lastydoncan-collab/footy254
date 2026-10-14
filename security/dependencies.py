"""FastAPI authentication / authorisation dependencies."""

from fastapi import Depends, HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from config.settings import ACCESS_COOKIE_NAME
from database.user_repository import get_user_by_id
from security.jwt_handler import decode_access_token

# auto_error=False: browser clients authenticate via the httpOnly cookie and
# never send this header, so HTTPBearer must not reject a request just for
# lacking one. Non-browser clients (mobile apps, scripts) can still authenticate
# with "Authorization: Bearer <access token>".
security = HTTPBearer(auto_error=False)

__all__ = [
    "ACCESS_COOKIE_NAME",
    "get_current_user",
    "get_optional_user",
    "require_admin",
    "serialize_user",
]


def _extract_token(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None,
) -> str | None:
    cookie_token = request.cookies.get(ACCESS_COOKIE_NAME)

    if cookie_token:
        return cookie_token

    if credentials and credentials.credentials:
        return credentials.credentials

    return None


def serialize_user(user) -> dict:
    """The one user shape the API returns (login, /auth/me, dependencies)."""

    return {
        "id": user["id"],
        "first_name": user["first_name"],
        "last_name": user["last_name"],
        "username": user["username"],
        "email": user["email"],
        "role": user["role"],
        "is_active": user["is_active"],
        "is_admin": bool(user.get("is_admin", False)),
        "subscription_status": user.get("subscription_status") or "FREE",
        "subscription_expires": user.get("subscription_expires"),
        "payment_provider": user.get("payment_provider"),
        "payment_reference": user.get("payment_reference"),
        "created_at": user["created_at"],
        "last_login": user["last_login"],
        "phone_number": user.get("phone_number"),
        "favorite_league": user.get("favorite_league") or "All Leagues",
        "notifications_enabled": user.get("notifications_enabled", True),
        "match_alerts": user.get("match_alerts", True),
        "login_alerts": user.get("login_alerts", True),
        "refresh_rate_seconds": user.get("refresh_rate_seconds") or 30,
        "two_factor_enabled": bool(user.get("totp_enabled", False)),
    }


def _authenticate(token: str) -> dict:
    payload = decode_access_token(token)

    if payload is None:
        raise HTTPException(status_code=401, detail="Invalid or expired token.")

    user = get_user_by_id(payload["sub"])

    if user is None:
        raise HTTPException(status_code=401, detail="User not found.")

    # A disabled account loses access on its very next request, not when its
    # (up to 15 minute) access token happens to expire.
    if not user["is_active"]:
        raise HTTPException(status_code=403, detail="Account has been disabled.")

    # Access tokens minted before a password change/reset are void immediately.
    changed_at = user.get("password_changed_at")
    issued_at = payload.get("iat")

    if changed_at is not None and issued_at is not None:
        if int(issued_at) < int(changed_at.timestamp()):
            raise HTTPException(
                status_code=401,
                detail="Session expired. Please sign in again.",
            )

    return serialize_user(user)


def get_current_user(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(security),
):
    token = _extract_token(request, credentials)

    if token is None:
        raise HTTPException(status_code=401, detail="Not authenticated.")

    return _authenticate(token)


def get_optional_user(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(security),
):
    """Like get_current_user, but returns None instead of failing."""

    token = _extract_token(request, credentials)

    if token is None:
        return None

    try:
        return _authenticate(token)
    except HTTPException:
        return None


def require_admin(current_user=Depends(get_current_user)):
    """Restrict operational endpoints to authenticated administrators."""

    if not current_user.get("is_admin"):
        raise HTTPException(
            status_code=403,
            detail="Administrator access required.",
        )

    return current_user
