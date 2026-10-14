"""
Per-account brute-force lockout.

Keyed by the submitted (lower-cased) email rather than a user id, so addresses
that do not exist are throttled exactly like real ones and the lockout response
can never be used to discover which accounts are registered. A per-IP limit
(slowapi) sits in front of this and covers one source hammering many accounts;
this covers many sources hammering one account.
"""

from datetime import datetime, timedelta, timezone

from database.db_config import get_connection


def get_lock_remaining_seconds(identifier: str) -> int:
    """Seconds left on an active lock, or 0 if the account is not locked."""

    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT locked_until FROM login_attempts WHERE identifier = %s;",
                (identifier,),
            )
            row = cur.fetchone()

    if not row or row["locked_until"] is None:
        return 0

    remaining = (row["locked_until"] - datetime.now(timezone.utc)).total_seconds()

    return max(0, int(remaining) + 1) if remaining > 0 else 0


def record_failed_login(identifier: str, max_failures: int, lockout_minutes: int) -> int:
    """
    Atomically count a failure; lock the identifier once the limit is reached.

    Returns the lock length in seconds if this failure triggered a lock, else 0.
    """

    locked_until = datetime.now(timezone.utc) + timedelta(minutes=lockout_minutes)

    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO login_attempts (identifier, failures, updated_at)
                VALUES (%s, 1, CURRENT_TIMESTAMP)
                ON CONFLICT (identifier) DO UPDATE SET
                    -- A previous lock that has already expired starts a fresh count.
                    failures = CASE
                        WHEN login_attempts.locked_until IS NOT NULL
                             AND login_attempts.locked_until <= CURRENT_TIMESTAMP
                        THEN 1
                        ELSE login_attempts.failures + 1
                    END,
                    locked_until = CASE
                        WHEN login_attempts.locked_until IS NOT NULL
                             AND login_attempts.locked_until <= CURRENT_TIMESTAMP
                        THEN NULL
                        ELSE login_attempts.locked_until
                    END,
                    updated_at = CURRENT_TIMESTAMP
                RETURNING failures;
                """,
                (identifier,),
            )
            failures = cur.fetchone()["failures"]

            if failures >= max_failures:
                cur.execute(
                    "UPDATE login_attempts SET locked_until = %s WHERE identifier = %s;",
                    (locked_until, identifier),
                )
                return lockout_minutes * 60

    return 0


def clear_failed_logins(identifier: str) -> None:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "DELETE FROM login_attempts WHERE identifier = %s;",
                (identifier,),
            )


def purge_stale_attempts(older_than_days: int = 2) -> int:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                DELETE FROM login_attempts
                WHERE updated_at < CURRENT_TIMESTAMP - (%s * INTERVAL '1 day')
                  AND (locked_until IS NULL OR locked_until < CURRENT_TIMESTAMP);
                """,
                (older_than_days,),
            )
            return cur.rowcount
