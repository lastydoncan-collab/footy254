-- Betting data model: wallets, odds, bet slips (single + multi) and
-- jackpots. Idempotent: safe to run more than once, like every other
-- migration in this project.

-- ==========================================================
-- WALLETS
-- ==========================================================

CREATE TABLE IF NOT EXISTS wallets (
    user_id    INTEGER PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
    balance    NUMERIC(14, 2) NOT NULL DEFAULT 0 CHECK (balance >= 0),
    currency   VARCHAR(3)     NOT NULL DEFAULT 'KES',
    updated_at TIMESTAMPTZ    NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- Backfill a zero-balance wallet for every user that already exists.
INSERT INTO wallets (user_id)
SELECT id FROM users
ON CONFLICT (user_id) DO NOTHING;

CREATE TABLE IF NOT EXISTS wallet_transactions (
    id            SERIAL PRIMARY KEY,
    user_id       INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    type          VARCHAR(20) NOT NULL CHECK (
        type IN (
            'DEPOSIT',
            'WITHDRAWAL',
            'BET_STAKE',
            'BET_PAYOUT',
            'BET_REFUND',
            'JACKPOT_STAKE',
            'JACKPOT_PAYOUT'
        )
    ),
    amount        NUMERIC(14, 2) NOT NULL,
    balance_after NUMERIC(14, 2) NOT NULL,
    reference     VARCHAR(100),
    description   TEXT,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_wallet_transactions_user
    ON wallet_transactions (user_id, created_at DESC);

-- ==========================================================
-- ODDS  (one row per fixture, 1X2 market)
-- ==========================================================

CREATE TABLE IF NOT EXISTS odds (
    id           SERIAL PRIMARY KEY,
    match_id     BIGINT NOT NULL UNIQUE REFERENCES fixtures(match_id) ON DELETE CASCADE,
    home_odds    NUMERIC(6, 2) NOT NULL,
    draw_odds    NUMERIC(6, 2) NOT NULL,
    away_odds    NUMERIC(6, 2) NOT NULL,
    margin       NUMERIC(5, 4) NOT NULL DEFAULT 0.07,
    source       VARCHAR(20)   NOT NULL DEFAULT 'MODEL',
    generated_at TIMESTAMPTZ   NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- ==========================================================
-- BET SLIPS  (single or multi/accumulator)
-- ==========================================================

CREATE TABLE IF NOT EXISTS bet_slips (
    id                SERIAL PRIMARY KEY,
    user_id           INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    bet_type          VARCHAR(10) NOT NULL CHECK (bet_type IN ('SINGLE', 'MULTI')),
    stake             NUMERIC(14, 2) NOT NULL CHECK (stake > 0),
    combined_odds     NUMERIC(10, 2) NOT NULL,
    potential_payout  NUMERIC(14, 2) NOT NULL,
    status            VARCHAR(10) NOT NULL DEFAULT 'PENDING' CHECK (
        status IN ('PENDING', 'WON', 'LOST', 'VOID')
    ),
    payout            NUMERIC(14, 2),
    placed_at         TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    settled_at        TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_bet_slips_user
    ON bet_slips (user_id, placed_at DESC);

CREATE INDEX IF NOT EXISTS idx_bet_slips_status
    ON bet_slips (status) WHERE status = 'PENDING';

CREATE TABLE IF NOT EXISTS bet_legs (
    id        SERIAL PRIMARY KEY,
    slip_id   INTEGER NOT NULL REFERENCES bet_slips(id) ON DELETE CASCADE,
    match_id  BIGINT  NOT NULL REFERENCES fixtures(match_id) ON DELETE CASCADE,
    pick      VARCHAR(5) NOT NULL CHECK (pick IN ('HOME', 'DRAW', 'AWAY')),
    odds      NUMERIC(6, 2) NOT NULL,
    status    VARCHAR(10) NOT NULL DEFAULT 'PENDING' CHECK (
        status IN ('PENDING', 'WON', 'LOST', 'VOID')
    )
);

CREATE INDEX IF NOT EXISTS idx_bet_legs_slip ON bet_legs (slip_id);
CREATE INDEX IF NOT EXISTS idx_bet_legs_match ON bet_legs (match_id) WHERE status = 'PENDING';

-- ==========================================================
-- JACKPOTS
-- ==========================================================

CREATE TABLE IF NOT EXISTS jackpots (
    id           SERIAL PRIMARY KEY,
    name         VARCHAR(100) NOT NULL,
    stake_amount NUMERIC(10, 2) NOT NULL,
    status       VARCHAR(10) NOT NULL DEFAULT 'OPEN' CHECK (
        status IN ('OPEN', 'CLOSED', 'SETTLED')
    ),
    opens_at     TIMESTAMPTZ,
    closes_at    TIMESTAMPTZ,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS jackpot_fixtures (
    jackpot_id  INTEGER NOT NULL REFERENCES jackpots(id) ON DELETE CASCADE,
    match_id    BIGINT  NOT NULL REFERENCES fixtures(match_id) ON DELETE CASCADE,
    sequence    INTEGER NOT NULL,
    PRIMARY KEY (jackpot_id, match_id)
);

CREATE TABLE IF NOT EXISTS jackpot_entries (
    id            SERIAL PRIMARY KEY,
    jackpot_id    INTEGER NOT NULL REFERENCES jackpots(id) ON DELETE CASCADE,
    user_id       INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    stake         NUMERIC(10, 2) NOT NULL,
    status        VARCHAR(10) NOT NULL DEFAULT 'PENDING' CHECK (
        status IN ('PENDING', 'SETTLED')
    ),
    correct_count INTEGER,
    payout        NUMERIC(14, 2),
    placed_at     TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    settled_at    TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_jackpot_entries_jackpot ON jackpot_entries (jackpot_id);
CREATE INDEX IF NOT EXISTS idx_jackpot_entries_user ON jackpot_entries (user_id);

CREATE TABLE IF NOT EXISTS jackpot_picks (
    entry_id  INTEGER NOT NULL REFERENCES jackpot_entries(id) ON DELETE CASCADE,
    match_id  BIGINT  NOT NULL REFERENCES fixtures(match_id) ON DELETE CASCADE,
    pick      VARCHAR(5) NOT NULL CHECK (pick IN ('HOME', 'DRAW', 'AWAY')),
    PRIMARY KEY (entry_id, match_id)
);
