// Real persistent storage for PitchIQ's paper wallet and bet slips.
//
// Uses Node's built-in `node:sqlite` (stable in recent Node 22/24 releases,
// still flagged experimental — hence the startup warning, which is expected
// and harmless) so the project keeps its zero-npm-install promise while no
// longer losing state to browser localStorage. One file, `data/pitchiq.db`,
// survives server restarts and is shared across every browser tab that
// carries the session cookie.
//
// This schema deliberately mirrors the shape of the footy254 repo's own
// Postgres betting tables (wallets / wallet_transactions / bet_slips /
// bet_legs) so this prototype can be ported over later with the same
// concepts, not rebuilt from scratch.

import { DatabaseSync } from "node:sqlite";
import { mkdirSync } from "node:fs";
import { dirname } from "node:path";
import { fileURLToPath } from "node:url";

const dbPath = fileURLToPath(new URL("./data/pitchiq.db", import.meta.url));
mkdirSync(dirname(dbPath), { recursive: true });

export const db = new DatabaseSync(dbPath);

db.exec("PRAGMA journal_mode = WAL;");
db.exec("PRAGMA foreign_keys = ON;");

db.exec(`
CREATE TABLE IF NOT EXISTS wallets (
  session_id  TEXT PRIMARY KEY,
  balance     REAL NOT NULL DEFAULT 10000,
  currency    TEXT NOT NULL DEFAULT 'KES',
  created_at  TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
  updated_at  TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))
);

CREATE TABLE IF NOT EXISTS wallet_transactions (
  id             INTEGER PRIMARY KEY AUTOINCREMENT,
  session_id     TEXT NOT NULL REFERENCES wallets(session_id) ON DELETE CASCADE,
  type           TEXT NOT NULL CHECK (type IN ('TOPUP','BET_STAKE','BET_PAYOUT','BET_REFUND')),
  amount         REAL NOT NULL,
  balance_after  REAL NOT NULL,
  reference      TEXT,
  description    TEXT,
  created_at     TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))
);
CREATE INDEX IF NOT EXISTS idx_wallet_tx_session ON wallet_transactions (session_id, created_at DESC);

CREATE TABLE IF NOT EXISTS bet_slips (
  id                INTEGER PRIMARY KEY AUTOINCREMENT,
  session_id        TEXT NOT NULL REFERENCES wallets(session_id) ON DELETE CASCADE,
  bet_type          TEXT NOT NULL CHECK (bet_type IN ('single','multiple','jackpot')),
  stake             REAL NOT NULL CHECK (stake > 0),
  combined_odds     REAL NOT NULL,
  potential_payout  REAL NOT NULL,
  status            TEXT NOT NULL DEFAULT 'PENDING' CHECK (status IN ('PENDING','WON','LOST','VOID')),
  payout            REAL,
  placed_at         TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
  settled_at        TEXT
);
CREATE INDEX IF NOT EXISTS idx_bet_slips_session ON bet_slips (session_id, placed_at DESC);

CREATE TABLE IF NOT EXISTS bet_legs (
  id          INTEGER PRIMARY KEY AUTOINCREMENT,
  slip_id     INTEGER NOT NULL REFERENCES bet_slips(id) ON DELETE CASCADE,
  fixture_id  TEXT NOT NULL,
  match_label TEXT NOT NULL,
  league      TEXT,
  market      TEXT,
  pick_label  TEXT NOT NULL,
  pick_key    TEXT NOT NULL,
  odds        REAL NOT NULL,
  status      TEXT NOT NULL DEFAULT 'PENDING' CHECK (status IN ('PENDING','WON','LOST','VOID'))
);
CREATE INDEX IF NOT EXISTS idx_bet_legs_slip ON bet_legs (slip_id);
CREATE INDEX IF NOT EXISTS idx_bet_legs_fixture ON bet_legs (fixture_id) WHERE status = 'PENDING';
`);

export function run(fn) {
  db.exec("BEGIN");
  try {
    const result = fn();
    db.exec("COMMIT");
    return result;
  } catch (error) {
    db.exec("ROLLBACK");
    throw error;
  }
}
