"""User persistence. All queries are parameterised."""

from datetime import datetime, timezone

from psycopg2 import errors as pg_errors

from database.db_config import get_connection


class DuplicateUserError(Exception):
    """Raised when an email or username is already registered."""

    def __init__(self, field: str):
        super().__init__(f"{field} already exists")
        self.field = field


_PUBLIC_COLUMNS = """
    id,
    first_name,
    last_name,
    username,
    email,
    role,
    is_active,
    is_admin,
    subscription_status,
    subscription_expires,
    payment_provider,
    payment_reference,
    password_changed_at,
    created_at,
    last_login,
    phone_number,
    favorite_league,
    notifications_enabled,
    match_alerts,
    login_alerts,
    refresh_rate_seconds,
    totp_enabled
"""


def _fetch_one(sql: str, params: tuple):
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, params)
            return cur.fetchone()


def _execute(sql: str, params: tuple) -> int:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, params)
            return cur.rowcount


# =========================
# CREATE USER
# =========================

def create_user(first_name, last_name, username, email, password_hash):
    """Insert a user and return its id. Raises DuplicateUserError on conflict."""

    try:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO users
                        (first_name, last_name, username, email, password_hash)
                    VALUES (%s, %s, %s, %s, %s)
                    RETURNING id;
                    """,
                    (first_name, last_name, username, email, password_hash),
                )
                return cur.fetchone()["id"]
    except pg_errors.UniqueViolation as exc:
        # Two simultaneous registrations can both pass the pre-check; the
        # database constraint is the real guarantee.
        constraint = (getattr(exc.diag, "constraint_name", "") or "").lower()

        raise DuplicateUserError(
            "username" if "username" in constraint else "email"
        ) from exc


# =========================
# LOOKUPS
# =========================

def get_user_by_email(email):
    """Full row including the password hash (login / password change)."""

    return _fetch_one(
        f"SELECT {_PUBLIC_COLUMNS}, password_hash FROM users "
        "WHERE lower(email) = lower(%s);",
        (email,),
    )


def get_user_by_username(username):
    return _fetch_one(
        f"SELECT {_PUBLIC_COLUMNS}, password_hash FROM users "
        "WHERE lower(username) = lower(%s);",
        (username,),
    )


def get_user_by_id(user_id):
    """Row without the password hash (per-request authentication)."""

    return _fetch_one(
        f"SELECT {_PUBLIC_COLUMNS} FROM users WHERE id = %s;",
        (user_id,),
    )


def email_exists(email) -> bool:
    return _fetch_one(
        "SELECT 1 AS hit FROM users WHERE lower(email) = lower(%s);",
        (email,),
    ) is not None


def username_exists(username) -> bool:
    return _fetch_one(
        "SELECT 1 AS hit FROM users WHERE lower(username) = lower(%s);",
        (username,),
    ) is not None


# =========================
# UPDATES
# =========================

def update_last_login(user_id):
    _execute(
        "UPDATE users SET last_login = CURRENT_TIMESTAMP WHERE id = %s;",
        (user_id,),
    )


def update_password(user_id, password_hash):
    """
    Store a new password hash and stamp ``password_changed_at``.

    The timestamp is taken from the application clock (the same clock that
    stamps token ``iat``) so access tokens issued before this moment can be
    rejected without any database/app clock-skew problems.
    """

    _execute(
        "UPDATE users SET password_hash = %s, password_changed_at = %s "
        "WHERE id = %s;",
        (password_hash, datetime.now(timezone.utc), user_id),
    )


def replace_password_hash_if_unchanged(user_id, old_hash, new_hash):
    """Silent re-hash at a higher bcrypt cost; no-op if the password changed."""

    return _execute(
        "UPDATE users SET password_hash = %s "
        "WHERE id = %s AND password_hash = %s;",
        (new_hash, user_id, old_hash),
    ) == 1


# =========================
# ADMINISTRATION
# =========================

def list_users(search: str | None = None, limit: int = 50, offset: int = 0):
    limit = max(1, min(int(limit), 200))
    offset = max(0, int(offset))

    where = ""
    params: list = []

    if search:
        like = f"%{search.strip().lower()}%"
        where = (
            "WHERE lower(email) LIKE %s OR lower(username) LIKE %s "
            "OR lower(first_name || ' ' || last_name) LIKE %s"
        )
        params.extend([like, like, like])

    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(f"SELECT COUNT(*) AS total FROM users {where};", params)
            total = cur.fetchone()["total"]

            cur.execute(
                f"SELECT {_PUBLIC_COLUMNS} FROM users {where} "
                "ORDER BY id DESC LIMIT %s OFFSET %s;",
                [*params, limit, offset],
            )
            rows = cur.fetchall()

    return total, rows


def count_active_admins() -> int:
    return _fetch_one(
        "SELECT COUNT(*) AS n FROM users WHERE is_admin = TRUE AND is_active = TRUE;",
        (),
    )["n"]


def set_user_active(user_id, active: bool) -> bool:
    return _execute(
        "UPDATE users SET is_active = %s WHERE id = %s;",
        (bool(active), user_id),
    ) == 1


def set_user_admin(user_id, admin: bool) -> bool:
    return _execute(
        "UPDATE users SET is_admin = %s, role = %s WHERE id = %s;",
        (bool(admin), "admin" if admin else "user", user_id),
    ) == 1
