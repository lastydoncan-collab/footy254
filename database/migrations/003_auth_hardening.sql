-- Authentication / authorization hardening.
--
--  * password_changed_at lets the API reject access tokens issued before a
--    password change/reset immediately, instead of waiting for them to expire.
--  * login_attempts backs per-account lockout. It is keyed by the submitted
--    email (not by user id) so unknown addresses are throttled identically and
--    lockout can never be used to discover which accounts exist.
--  * Case-insensitive uniqueness for email/username stops "Bob@x.com" and
--    "bob@x.com" becoming two accounts. The unique indexes are skipped (with a
--    NOTICE) if legacy data already contains such duplicates, so this migration
--    can never block startup.

ALTER TABLE users ADD COLUMN IF NOT EXISTS password_changed_at TIMESTAMPTZ;

CREATE TABLE IF NOT EXISTS login_attempts (
    identifier   TEXT PRIMARY KEY,
    failures     INTEGER     NOT NULL DEFAULT 0,
    locked_until TIMESTAMPTZ,
    updated_at   TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_login_attempts_updated_at
    ON login_attempts (updated_at);

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_indexes WHERE indexname = 'uq_users_email_lower') THEN
        IF EXISTS (SELECT 1 FROM users GROUP BY lower(email) HAVING COUNT(*) > 1) THEN
            RAISE NOTICE 'Duplicate emails (case-insensitive) found; uq_users_email_lower skipped.';
        ELSE
            CREATE UNIQUE INDEX uq_users_email_lower ON users (lower(email));
        END IF;
    END IF;

    IF NOT EXISTS (SELECT 1 FROM pg_indexes WHERE indexname = 'uq_users_username_lower') THEN
        IF EXISTS (SELECT 1 FROM users GROUP BY lower(username) HAVING COUNT(*) > 1) THEN
            RAISE NOTICE 'Duplicate usernames (case-insensitive) found; uq_users_username_lower skipped.';
        ELSE
            CREATE UNIQUE INDEX uq_users_username_lower ON users (lower(username));
        END IF;
    END IF;
END
$$;

CREATE INDEX IF NOT EXISTS idx_refresh_tokens_user_active
    ON refresh_tokens (user_id, revoked_at, expires_at);

CREATE INDEX IF NOT EXISTS idx_refresh_tokens_expires_at
    ON refresh_tokens (expires_at);

CREATE INDEX IF NOT EXISTS idx_password_reset_tokens_hash
    ON password_reset_tokens (token_hash);

CREATE INDEX IF NOT EXISTS idx_password_reset_tokens_expires_at
    ON password_reset_tokens (expires_at);
