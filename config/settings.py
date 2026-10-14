"""
FOOTY254 central runtime settings.

Everything environment-dependent that more than one module needs lives here, so
authentication, cookies, CORS, the database pool and static hosting can never
drift apart.

``main.py`` calls ``load_dotenv()`` before importing this module, so values in
``.env`` are visible here. Importing this module never touches the network or
the database.
"""

import os
from pathlib import Path
from urllib.parse import urlparse

PROJECT_ROOT = Path(__file__).resolve().parent.parent


# ----------------------------------------------------------
# Parsing helpers
# ----------------------------------------------------------

def env_str(name: str, default: str = "") -> str:
    value = os.getenv(name)

    if value is None:
        return default

    return value.strip()


def env_bool(name: str, default: bool = False) -> bool:
    value = os.getenv(name)

    if value is None or value.strip() == "":
        return default

    return value.strip().lower() in {"1", "true", "yes", "on"}


def env_int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, "").strip() or default)
    except ValueError:
        return default


def env_list(name: str) -> list[str]:
    return [
        item.strip().rstrip("/")
        for item in os.getenv(name, "").split(",")
        if item.strip()
    ]


def _origin_of(url: str) -> str | None:
    parsed = urlparse(url)

    if not parsed.scheme or not parsed.netloc:
        return None

    return f"{parsed.scheme}://{parsed.netloc}".lower()


# ----------------------------------------------------------
# Environment
# ----------------------------------------------------------

APP_ENV = env_str("APP_ENV", "development").lower()
IS_PRODUCTION = APP_ENV == "production"

# Every JSON route lives under this prefix so the single-page app can own all
# other paths (client-side routing) on the very same origin.
API_PREFIX = "/" + env_str("API_PREFIX", "/api").strip("/")

# ----------------------------------------------------------
# JWT
# ----------------------------------------------------------

JWT_SECRET_KEY = env_str("JWT_SECRET_KEY")
JWT_ALGORITHM = "HS256"
JWT_ISSUER = "footy254"

ACCESS_TOKEN_EXPIRE_MINUTES = env_int("ACCESS_TOKEN_EXPIRE_MINUTES", 15)
REFRESH_TOKEN_EXPIRE_DAYS = env_int("REFRESH_TOKEN_EXPIRE_DAYS", 30)

_PLACEHOLDER_SECRETS = ("replace-with", "changeme", "change-me", "secret")


def validate_jwt_secret() -> None:
    """Fail fast (at startup) on a missing or guessable signing secret."""

    if not JWT_SECRET_KEY:
        raise RuntimeError(
            "JWT_SECRET_KEY is not set. Set it in your .env file "
            "(see .env.example). Generate one with: "
            'python -c "import secrets; print(secrets.token_urlsafe(64))"'
        )

    if IS_PRODUCTION:
        weak = len(JWT_SECRET_KEY) < 32 or any(
            marker in JWT_SECRET_KEY.lower() for marker in _PLACEHOLDER_SECRETS
        )

        if weak:
            raise RuntimeError(
                "JWT_SECRET_KEY is too short or still a placeholder. In "
                "production it must be a random value of at least 32 characters."
            )


# ----------------------------------------------------------
# Cookies
# ----------------------------------------------------------

# Secure cookies are mandatory over https, so they default to ON in production.
COOKIE_SECURE = env_bool("COOKIE_SECURE", IS_PRODUCTION)
COOKIE_SAMESITE = env_str("COOKIE_SAMESITE", "lax").lower()
COOKIE_DOMAIN = env_str("COOKIE_DOMAIN") or None

if COOKIE_SAMESITE not in {"lax", "strict", "none"}:
    raise RuntimeError("COOKIE_SAMESITE must be lax, strict or none.")

# Browsers silently discard SameSite=None cookies that are not Secure, which
# would make every login look successful and then immediately log out.
if COOKIE_SAMESITE == "none" and not COOKIE_SECURE:
    raise RuntimeError("COOKIE_SAMESITE=none requires COOKIE_SECURE=true (https).")

ACCESS_COOKIE_NAME = "footy254_access_token"
REFRESH_COOKIE_NAME = "footy254_refresh_token"

# The refresh cookie is only ever sent to the token-management endpoints.
REFRESH_COOKIE_PATH = f"{API_PREFIX}/auth"

# Cookie paths used by releases before the /api prefix existed; cleared on
# logout so an upgraded browser never keeps a dead, orphaned cookie around.
LEGACY_REFRESH_COOKIE_PATH = "/auth"

# ----------------------------------------------------------
# Origins / CORS
# ----------------------------------------------------------

FRONTEND_URL = env_str("FRONTEND_URL", "http://localhost:5173").rstrip("/")

# Same-origin deployments (the default and recommended setup) need no CORS at
# all. Extra origins are only for a separately hosted frontend.
EXTRA_ORIGINS = env_list("FRONTEND_ORIGINS")

DEV_ORIGINS = [] if IS_PRODUCTION else [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    "http://localhost:4173",
    "http://127.0.0.1:4173",
]

_frontend_origin = _origin_of(FRONTEND_URL)

ALLOWED_ORIGINS = sorted(
    {
        origin.lower()
        for origin in (
            *DEV_ORIGINS,
            *EXTRA_ORIGINS,
            *([_frontend_origin] if _frontend_origin else []),
        )
    }
)

# ----------------------------------------------------------
# Auth policy
# ----------------------------------------------------------

MAX_FAILED_LOGINS = env_int("MAX_FAILED_LOGINS", 5)
LOCKOUT_MINUTES = env_int("LOCKOUT_MINUTES", 15)
MAX_SESSIONS_PER_USER = env_int("MAX_SESSIONS_PER_USER", 10)
PASSWORD_RESET_EXPIRE_MINUTES = env_int("PASSWORD_RESET_EXPIRE_MINUTES", 60)
PASSWORD_RESET_COOLDOWN_SECONDS = env_int("PASSWORD_RESET_COOLDOWN_SECONDS", 60)

# A refresh token rotated moments ago may legitimately be presented again by a
# second tab whose request raced the first. Inside this window the duplicate is
# answered harmlessly; outside it, a re-presented token is treated as theft and
# every session of that user is revoked.
REFRESH_REUSE_GRACE_SECONDS = env_int("REFRESH_REUSE_GRACE_SECONDS", 15)

BCRYPT_ROUNDS = max(10, min(env_int("BCRYPT_ROUNDS", 12), 15))

# bcrypt only ever uses the first 72 bytes of a password.
PASSWORD_MIN_LENGTH = 8
PASSWORD_MAX_BYTES = 72

# ----------------------------------------------------------
# Database
# ----------------------------------------------------------

DB_POOL_ENABLED = env_bool("DB_POOL_ENABLED", True)
DB_POOL_MAX = max(2, env_int("DB_POOL_MAX", 15))
DB_POOL_WAIT_SECONDS = env_int("DB_POOL_WAIT_SECONDS", 15)
DB_CONNECT_TIMEOUT = env_int("DB_CONNECT_TIMEOUT", 10)

# ----------------------------------------------------------
# Runtime switches
# ----------------------------------------------------------

ENABLE_SCHEDULER = env_bool("ENABLE_SCHEDULER", True)
RUN_MIGRATIONS_ON_STARTUP = env_bool("RUN_MIGRATIONS_ON_STARTUP", True)
ENABLE_DOCS = env_bool("ENABLE_DOCS", not IS_PRODUCTION)

# Expose internal error text in /health only outside production.
EXPOSE_ERROR_DETAILS = not IS_PRODUCTION

FRONTEND_DIST = Path(
    os.getenv(
        "FRONTEND_DIST",
        str(PROJECT_ROOT / "footy254-dashboard" / "dist"),
    )
)

# ----------------------------------------------------------
# Email
# ----------------------------------------------------------

SMTP_HOST = env_str("SMTP_HOST")
SMTP_PORT = env_int("SMTP_PORT", 587)
SMTP_USER = env_str("SMTP_USER")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD", "")
FROM_EMAIL = env_str("FROM_EMAIL", "no-reply@footy254.com")
