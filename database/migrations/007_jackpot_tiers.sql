-- Jackpot payout tiers. Entries could already be placed (005_betting.sql)
-- but nothing could ever settle them — there was no table saying what a
-- given correct-count pays. Idempotent, like every other migration here.

CREATE TABLE IF NOT EXISTS jackpot_tiers (
    id            SERIAL PRIMARY KEY,
    jackpot_id    INTEGER NOT NULL REFERENCES jackpots(id) ON DELETE CASCADE,
    min_correct   INTEGER NOT NULL,
    payout_multiplier NUMERIC(10, 2) NOT NULL CHECK (payout_multiplier >= 0),
    UNIQUE (jackpot_id, min_correct)
);

CREATE INDEX IF NOT EXISTS idx_jackpot_tiers_jackpot ON jackpot_tiers (jackpot_id, min_correct DESC);
