-- Operational indexes for authentication, subscriptions, payments, fixtures,
-- and prediction reads.  All statements are idempotent and preserve records.

CREATE INDEX IF NOT EXISTS idx_users_active_email
    ON users (email)
    WHERE is_active = TRUE;

CREATE INDEX IF NOT EXISTS idx_subscriptions_user_status_expiry
    ON subscriptions (user_id, status, expires_at DESC);

CREATE UNIQUE INDEX IF NOT EXISTS uq_subscriptions_checkout_request_id
    ON subscriptions (checkout_request_id)
    WHERE checkout_request_id IS NOT NULL;

CREATE UNIQUE INDEX IF NOT EXISTS uq_subscriptions_transaction_reference
    ON subscriptions (transaction_reference)
    WHERE transaction_reference IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_fixtures_status_kickoff
    ON fixtures (status, kickoff);

CREATE INDEX IF NOT EXISTS idx_predictions_generated_at
    ON predictions (generated_at DESC);
