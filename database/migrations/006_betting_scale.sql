-- Paper-money hardening + trading-desk-lite infrastructure for the betting
-- module: idempotent bet placement, odds price history, and the indexes
-- liability/exposure reporting needs. Idempotent: safe to run more than
-- once, like every other migration in this project.

-- ==========================================================
-- IDEMPOTENT BET PLACEMENT
-- ==========================================================
-- A client-generated key (e.g. a UUID minted once per "Place bet" tap)
-- lets a network retry or double-click return the original slip instead
-- of staking twice. NULL is allowed (unkeyed placement still works) but
-- a given user can only use the same key once.

ALTER TABLE bet_slips ADD COLUMN IF NOT EXISTS idempotency_key VARCHAR(100);

CREATE UNIQUE INDEX IF NOT EXISTS idx_bet_slips_idempotency
    ON bet_slips (user_id, idempotency_key)
    WHERE idempotency_key IS NOT NULL;

-- ==========================================================
-- ODDS HISTORY  (every price change, for the live-odds feed and movement charts)
-- ==========================================================

CREATE TABLE IF NOT EXISTS odds_history (
    id           SERIAL PRIMARY KEY,
    match_id     BIGINT NOT NULL REFERENCES fixtures(match_id) ON DELETE CASCADE,
    home_odds    NUMERIC(6, 2) NOT NULL,
    draw_odds    NUMERIC(6, 2) NOT NULL,
    away_odds    NUMERIC(6, 2) NOT NULL,
    reason       VARCHAR(30) NOT NULL DEFAULT 'MODEL' CHECK (
        reason IN ('MODEL', 'EXPOSURE_SHADE', 'MANUAL')
    ),
    recorded_at  TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_odds_history_match
    ON odds_history (match_id, recorded_at DESC);

-- ==========================================================
-- INDEXES FOR LIABILITY / EXPOSURE REPORTING
-- ==========================================================
-- Exposure reports group pending legs by (fixture, pick) and need the
-- parent slip's stake/odds, so the existing idx_bet_legs_match
-- (match_id WHERE status='PENDING') already covers the hot path; this
-- adds the slip-side lookup used when summing potential payout exposure.

CREATE INDEX IF NOT EXISTS idx_bet_slips_pending_lookup
    ON bet_slips (id) WHERE status = 'PENDING';
