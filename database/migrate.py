"""Apply project SQL migrations in filename order, once each.

Run from the project root with:  ``python -m database.migrate``

Every migration is written with idempotent SQL. Applied migrations are recorded
in ``schema_migrations`` so they are not re-run on later starts. A PostgreSQL
advisory lock makes concurrent starts (several workers / containers booting at
the same time) safe: one applies, the others wait and then find nothing to do.
"""

import logging
from pathlib import Path

from database.db_config import get_raw_connection

logger = logging.getLogger(__name__)

MIGRATIONS_DIR = Path(__file__).with_name("migrations")

# Arbitrary constant: all FOOTY254 processes agree on this lock key.
_MIGRATION_LOCK_KEY = 254_254_001


def apply_migrations() -> list[str]:
    """Apply pending migrations and return the filenames applied."""

    applied: list[str] = []

    conn = get_raw_connection()

    try:
        conn.autocommit = True

        with conn.cursor() as cur:
            cur.execute("SELECT pg_advisory_lock(%s)", (_MIGRATION_LOCK_KEY,))

            try:
                cur.execute(
                    """
                    CREATE TABLE IF NOT EXISTS schema_migrations (
                        filename   TEXT PRIMARY KEY,
                        applied_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
                    )
                    """
                )

                cur.execute("SELECT filename FROM schema_migrations")
                done = {row["filename"] for row in cur.fetchall()}

                for migration in sorted(MIGRATIONS_DIR.glob("*.sql")):
                    if migration.name in done:
                        continue

                    sql = migration.read_text(encoding="utf-8")

                    # One transaction per migration: it either fully applies
                    # or leaves the database untouched.
                    cur.execute("BEGIN")
                    try:
                        cur.execute(sql)
                        cur.execute(
                            "INSERT INTO schema_migrations (filename) VALUES (%s)",
                            (migration.name,),
                        )
                        cur.execute("COMMIT")
                    except Exception:
                        cur.execute("ROLLBACK")
                        logger.exception("Migration %s failed.", migration.name)
                        raise

                    applied.append(migration.name)
                    logger.info("Applied migration %s", migration.name)
            finally:
                cur.execute("SELECT pg_advisory_unlock(%s)", (_MIGRATION_LOCK_KEY,))
    finally:
        conn.close()

    return applied


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(message)s")

    from dotenv import load_dotenv

    load_dotenv()

    result = apply_migrations()

    if not result:
        print("Database schema is up to date.")

    for filename in result:
        print(f"Applied {filename}")
