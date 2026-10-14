"""Profile, preference and two-factor persistence."""

from datetime import datetime, timezone

from psycopg2 import errors as pg_errors

from database.db_config import get_connection
from database.user_repository import DuplicateUserError


def _run(sql: str, params: tuple, fetch: bool = False):
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, params)
            return cur.fetchone() if fetch else cur.rowcount


def update_profile(user_id, first_name, last_name, username, phone_number):
    try:
        _run(
            """
            UPDATE users
               SET first_name = %s, last_name = %s, username = %s, phone_number = %s
             WHERE id = %s;
            """,
            (first_name, last_name, username, phone_number, user_id),
        )
    except pg_errors.UniqueViolation as exc:
        raise DuplicateUserError("username") from exc


def update_preferences(
    user_id,
    notifications_enabled,
    match_alerts,
    login_alerts,
    favorite_league,
    refresh_rate_seconds,
):
    _run(
        """
        UPDATE users
           SET notifications_enabled = %s, match_alerts = %s, login_alerts = %s,
               favorite_league = %s, refresh_rate_seconds = %s
         WHERE id = %s;
        """,
        (
            notifications_enabled,
            match_alerts,
            login_alerts,
            favorite_league,
            refresh_rate_seconds,
            user_id,
        ),
    )


def get_two_factor_row(user_id):
    return _run(
        """
        SELECT totp_secret, totp_enabled, totp_last_step, recovery_code_hashes
          FROM users WHERE id = %s;
        """,
        (user_id,),
        fetch=True,
    )


def store_pending_totp_secret(user_id, sealed_secret):
    # Never overwrite the secret of an account that already has 2FA on.
    return _run(
        """
        UPDATE users SET totp_secret = %s, totp_last_step = 0
         WHERE id = %s AND totp_enabled = FALSE;
        """,
        (sealed_secret, user_id),
    )


def enable_totp(user_id, last_step, recovery_hashes):
    _run(
        """
        UPDATE users
           SET totp_enabled = TRUE, totp_last_step = %s, recovery_code_hashes = %s
         WHERE id = %s;
        """,
        (last_step, recovery_hashes, user_id),
    )


def disable_totp(user_id):
    _run(
        """
        UPDATE users
           SET totp_enabled = FALSE, totp_secret = NULL, totp_last_step = 0,
               recovery_code_hashes = '{}'
         WHERE id = %s;
        """,
        (user_id,),
    )


def advance_totp_step(user_id, step) -> bool:
    """Atomically accept a step once; False if it was already used."""

    return (
        _run(
            "UPDATE users SET totp_last_step = %s WHERE id = %s AND totp_last_step < %s;",
            (step, user_id, step),
        )
        == 1
    )


def consume_recovery_code(user_id, code_hash) -> bool:
    """Remove one recovery code; True only if it existed (single use)."""

    return (
        _run(
            """
            UPDATE users
               SET recovery_code_hashes = array_remove(recovery_code_hashes, %s)
             WHERE id = %s AND %s = ANY(recovery_code_hashes);
            """,
            (code_hash, user_id, code_hash),
        )
        == 1
    )
