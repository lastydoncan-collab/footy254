-- Base schema for a brand-new FOOTY254 database.
--
-- The original project had no migration that created its core tables, so a
-- fresh machine could not run the app. Every statement here is idempotent:
-- on an existing database it changes nothing, and ADD COLUMN IF NOT EXISTS
-- only fills in columns an older install might lack.

-- ==========================================================
-- USERS
-- ==========================================================

CREATE TABLE IF NOT EXISTS users (
    id                   SERIAL PRIMARY KEY,
    first_name           VARCHAR(100) NOT NULL,
    last_name            VARCHAR(100) NOT NULL,
    username             VARCHAR(50)  NOT NULL,
    email                VARCHAR(254) NOT NULL,
    password_hash        TEXT         NOT NULL,
    role                 VARCHAR(30)  NOT NULL DEFAULT 'user',
    is_active            BOOLEAN      NOT NULL DEFAULT TRUE,
    is_admin             BOOLEAN      NOT NULL DEFAULT FALSE,
    subscription_status  VARCHAR(20)  NOT NULL DEFAULT 'FREE',
    subscription_expires TIMESTAMPTZ,
    payment_provider     VARCHAR(30),
    payment_reference    VARCHAR(100),
    created_at           TIMESTAMPTZ  NOT NULL DEFAULT CURRENT_TIMESTAMP,
    last_login           TIMESTAMPTZ
);

ALTER TABLE users ADD COLUMN IF NOT EXISTS role                 VARCHAR(30) NOT NULL DEFAULT 'user';
ALTER TABLE users ADD COLUMN IF NOT EXISTS is_active            BOOLEAN     NOT NULL DEFAULT TRUE;
ALTER TABLE users ADD COLUMN IF NOT EXISTS is_admin             BOOLEAN     NOT NULL DEFAULT FALSE;
ALTER TABLE users ADD COLUMN IF NOT EXISTS subscription_status  VARCHAR(20) NOT NULL DEFAULT 'FREE';
ALTER TABLE users ADD COLUMN IF NOT EXISTS subscription_expires TIMESTAMPTZ;
ALTER TABLE users ADD COLUMN IF NOT EXISTS payment_provider     VARCHAR(30);
ALTER TABLE users ADD COLUMN IF NOT EXISTS payment_reference    VARCHAR(100);
ALTER TABLE users ADD COLUMN IF NOT EXISTS created_at           TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP;
ALTER TABLE users ADD COLUMN IF NOT EXISTS last_login           TIMESTAMPTZ;

-- ==========================================================
-- FIXTURES
-- ==========================================================

CREATE TABLE IF NOT EXISTS fixtures (
    match_id         BIGINT PRIMARY KEY,
    competition_id   INTEGER,
    competition      TEXT,
    competition_code TEXT,
    season           INTEGER,
    matchday         INTEGER,
    stage            TEXT,
    home_team_id     INTEGER,
    away_team_id     INTEGER,
    home_team        TEXT,
    away_team        TEXT,
    utc_date         TIMESTAMPTZ,
    match_date       DATE,
    kickoff_time     TIME,
    kickoff          TIMESTAMPTZ,
    status           TEXT,
    score_home       INTEGER,
    score_away       INTEGER,
    winner           TEXT,
    last_updated     TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

-- ==========================================================
-- PREDICTIONS
-- ==========================================================

CREATE TABLE IF NOT EXISTS predictions (
    match_id     BIGINT PRIMARY KEY,
    prediction   TEXT,
    confidence   DOUBLE PRECISION,
    home_win     DOUBLE PRECISION,
    draw         DOUBLE PRECISION,
    away_win     DOUBLE PRECISION,
    xg_home      DOUBLE PRECISION,
    xg_away      DOUBLE PRECISION,
    generated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

-- ==========================================================
-- SUBSCRIPTIONS
-- ==========================================================

CREATE TABLE IF NOT EXISTS subscriptions (
    subscription_id       SERIAL PRIMARY KEY,
    user_id               INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    plan                  VARCHAR(20),
    status                VARCHAR(20) NOT NULL DEFAULT 'PENDING',
    payment_method        VARCHAR(20),
    transaction_reference VARCHAR(100),
    merchant_request_id   VARCHAR(100),
    checkout_request_id   VARCHAR(100),
    amount                NUMERIC(12, 2),
    currency              VARCHAR(3) DEFAULT 'KES',
    started_at            TIMESTAMPTZ,
    expires_at            TIMESTAMPTZ,
    created_at            TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at            TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- ==========================================================
-- AUTOMATION STATE (finished-match counter that triggers retraining)
-- ==========================================================

CREATE TABLE IF NOT EXISTS automation_state (
    key        TEXT PRIMARY KEY,
    value      INTEGER NOT NULL DEFAULT 0,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

INSERT INTO automation_state (key, value)
VALUES ('new_finished_matches', 0)
ON CONFLICT (key) DO NOTHING;
