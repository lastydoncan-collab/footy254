"""
Repository for refresh tokens and password-reset tokens.

Tokens are stored hashed (SHA-256). The raw token is never persisted, so a
database dump cannot be replayed to forge sessions or reset passwords.
"""

import hashlib
import hmac
import uuid
from datetime import datetime, timezone

from database.db_config import get_connection


def _hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def is_valid_uuid(value) -> bool:
    try:
        uuid.UUID(str(value))
        return True
    except (ValueError, AttributeError, TypeError):
        return False


# ==========================================================
# REFRESH TOKENS
# ==========================================================

def store_refresh_token(
    user_id,
    jti,
    token,
    expires_at,
    user_agent=None,
    ip_address=None,
):
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO refresh_tokens
                    (user_id, jti, token_hash, expires_at, user_agent, ip_address)
                VALUES (%s, %s, %s, %s, %s, %s);
                """,
                (
                    user_id,
                    jti,
                    _hash(token),
                    expires_at,
                    (user_agent or "")[:500] or None,
                    ip_address,
                ),
            )


def get_refresh_token(jti):
    """The row for ``jti`` in ANY state (active, revoked or expired), or None."""

    if not is_valid_uuid(jti):
        return None

    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, user_id, jti, token_hash, expires_at,
                       revoked_at, replaced_by_jti
                FROM refresh_tokens
                WHERE jti = %s;
                """,
                (str(jti),),
            )
            return cur.fetchone()


def token_matches(row, token: str) -> bool:
    return row is not None and hmac.compare_digest(row["token_hash"], _hash(token))


def is_expired(row) -> bool:
    return row["expires_at"] <= datetime.now(timezone.utc)


def claim_refresh_token(jti):
    """
    Atomically revoke a refresh token that is still unrevoked and unexpired.

    Exactly one of several simultaneous refresh requests presenting the same
    token wins (gets the row back); the rest get ``None``. This is what makes
    rotation race-free.
    """

    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE refresh_tokens
                SET revoked_at = CURRENT_TIMESTAMP
                WHERE jti = %s
                  AND revoked_at IS NULL
                  AND expires_at > CURRENT_TIMESTAMP
                RETURNING user_id;
                """,
                (str(jti),),
            )
            return cur.fetchone()


def set_replaced_by(old_jti, new_jti):
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE refresh_tokens SET replaced_by_jti = %s WHERE jti = %s;",
                (str(new_jti), str(old_jti)),
            )


def revoke_refresh_token(jti):
    if not is_valid_uuid(jti):
        return

    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE refresh_tokens
                SET revoked_at = CURRENT_TIMESTAMP
                WHERE jti = %s AND revoked_at IS NULL;
                """,
                (str(jti),),
            )


def revoke_all_refresh_tokens_for_user(user_id):
    """Logout-everywhere, password change/reset, theft response, admin action."""

    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE refresh_tokens
                SET revoked_at = CURRENT_TIMESTAMP
                WHERE user_id = %s AND revoked_at IS NULL;
                """,
                (user_id,),
            )


def revoke_all_refresh_tokens_for_user_except(user_id, keep_jti):
    """'Log out of all other devices' - keeps the caller's own session."""

    if not is_valid_uuid(keep_jti):
        return revoke_all_refresh_tokens_for_user(user_id)

    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE refresh_tokens
                SET revoked_at = CURRENT_TIMESTAMP
                WHERE user_id = %s AND jti <> %s AND revoked_at IS NULL;
                """,
                (user_id, str(keep_jti)),
            )


def list_active_sessions(user_id):
    """Active (unrevoked, unexpired) sessions, newest first (Active Devices UI)."""

    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT jti, user_agent, ip_address, created_at, expires_at
                FROM refresh_tokens
                WHERE user_id = %s
                  AND revoked_at IS NULL
                  AND expires_at > CURRENT_TIMESTAMP
                ORDER BY created_at DESC;
                """,
                (user_id,),
            )
            return cur.fetchall()


def revoke_session_owned_by_user(user_id, jti) -> bool:
    """
    Revoke one session, scoped to ``user_id`` so a user can never revoke
    someone else's session by guessing a jti. Returns True if a row changed.
    """

    if not is_valid_uuid(jti):
        return False

    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE refresh_tokens
                SET revoked_at = CURRENT_TIMESTAMP
                WHERE jti = %s AND user_id = %s AND revoked_at IS NULL
                RETURNING id;
                """,
                (str(jti), user_id),
            )
            return cur.fetchone() is not None


def enforce_session_limit(user_id, limit: int):
    """Keep only the ``limit`` most recent active sessions; revoke the rest."""

    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE refresh_tokens
                SET revoked_at = CURRENT_TIMESTAMP
                WHERE user_id = %s
                  AND revoked_at IS NULL
                  AND id NOT IN (
                      SELECT id FROM refresh_tokens
                      WHERE user_id = %s
                        AND revoked_at IS NULL
                        AND expires_at > CURRENT_TIMESTAMP
                      ORDER BY created_at DESC
                      LIMIT %s
                  );
                """,
                (user_id, user_id, limit),
            )


# ==========================================================
# PASSWORD RESET TOKENS
# ==========================================================

def create_password_reset_token(user_id, token, expires_at):
    """Issue a reset token; any earlier unused tokens for the user are voided."""

    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE password_reset_tokens
                SET used_at = CURRENT_TIMESTAMP
                WHERE user_id = %s AND used_at IS NULL;
                """,
                (user_id,),
            )
            cur.execute(
                """
                INSERT INTO password_reset_tokens (user_id, token_hash, expires_at)
                VALUES (%s, %s, %s);
                """,
                (user_id, _hash(token), expires_at),
            )


def reset_requested_recently(user_id, within_seconds: int) -> bool:
    """True if a reset email was already issued in the last ``within_seconds``."""

    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT 1 AS hit
                FROM password_reset_tokens
                WHERE user_id = %s
                  AND created_at > CURRENT_TIMESTAMP - (%s * INTERVAL '1 second')
                LIMIT 1;
                """,
                (user_id, within_seconds),
            )
            return cur.fetchone() is not None


def get_valid_password_reset_token(token: str):
    """Peek at an unused, unexpired reset token (does not consume it)."""

    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, user_id, expires_at
                FROM password_reset_tokens
                WHERE token_hash = %s
                  AND used_at IS NULL
                  AND expires_at > CURRENT_TIMESTAMP;
                """,
                (_hash(token),),
            )
            return cur.fetchone()


def consume_password_reset_token(token: str):
    """
    Atomically mark a reset token used and return its row (or None).

    Single-use is enforced by the database: two simultaneous submissions of
    the same link cannot both succeed.
    """

    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE password_reset_tokens
                SET used_at = CURRENT_TIMESTAMP
                WHERE token_hash = %s
                  AND used_at IS NULL
                  AND expires_at > CURRENT_TIMESTAMP
                RETURNING id, user_id;
                """,
                (_hash(token),),
            )
            return cur.fetchone()


# ==========================================================
# HOUSEKEEPING
# ==========================================================

def purge_expired_tokens() -> dict:
    """Delete long-dead token rows so the tables do not grow forever."""

    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                DELETE FROM refresh_tokens
                WHERE expires_at < CURRENT_TIMESTAMP - INTERVAL '7 days'
                   OR (revoked_at IS NOT NULL
                       AND revoked_at < CURRENT_TIMESTAMP - INTERVAL '7 days');
                """
            )
            refresh = cur.rowcount

            cur.execute(
                """
                DELETE FROM password_reset_tokens
                WHERE expires_at < CURRENT_TIMESTAMP - INTERVAL '1 day';
                """
            )
            resets = cur.rowcount

    return {"refresh_tokens": refresh, "password_reset_tokens": resets}
