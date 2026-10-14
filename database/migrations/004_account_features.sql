-- Profile editing, notification preferences, two-factor authentication and
-- card payments. Idempotent: safe to run more than once.

ALTER TABLE users ADD COLUMN IF NOT EXISTS phone_number TEXT;
ALTER TABLE users ADD COLUMN IF NOT EXISTS favorite_league TEXT NOT NULL DEFAULT 'All Leagues';
ALTER TABLE users ADD COLUMN IF NOT EXISTS notifications_enabled BOOLEAN NOT NULL DEFAULT TRUE;
ALTER TABLE users ADD COLUMN IF NOT EXISTS match_alerts BOOLEAN NOT NULL DEFAULT TRUE;
ALTER TABLE users ADD COLUMN IF NOT EXISTS login_alerts BOOLEAN NOT NULL DEFAULT TRUE;
ALTER TABLE users ADD COLUMN IF NOT EXISTS refresh_rate_seconds INTEGER NOT NULL DEFAULT 30;

-- Two-factor (TOTP). The secret is only trusted once totp_enabled is true.
ALTER TABLE users ADD COLUMN IF NOT EXISTS totp_secret TEXT;
ALTER TABLE users ADD COLUMN IF NOT EXISTS totp_enabled BOOLEAN NOT NULL DEFAULT FALSE;
-- Last accepted 30-second step, so one code cannot be replayed.
ALTER TABLE users ADD COLUMN IF NOT EXISTS totp_last_step BIGINT NOT NULL DEFAULT 0;
-- SHA-256 hashes of single-use recovery codes.
ALTER TABLE users ADD COLUMN IF NOT EXISTS recovery_code_hashes TEXT[] NOT NULL DEFAULT '{}';

-- Card payments (Paystack): the gateway reference of the checkout.
ALTER TABLE subscriptions ADD COLUMN IF NOT EXISTS gateway_reference TEXT;
CREATE INDEX IF NOT EXISTS idx_subscriptions_gateway_reference
    ON subscriptions (gateway_reference);
