// ======================================================
// FOOTY254 BETTING SERVICE
// Talks to the /api/betting/* routes added by the PitchIQ betting module
// (database/betting_repository.py, api/betting.py, schemas/betting.py).
//
// NOTE ON FIELD NAMES: the odds-board shape below (match_id, home_odds,
// draw_odds, away_odds, margin, generated_at, home_team, away_team,
// competition, kickoff, fixture_status) is confirmed against a live
// Swagger response. The request bodies for placing bets and entering
// jackpots follow the PlaceSingleBetRequest / PlaceMultiBetRequest /
// JackpotEntryRequest shapes as designed, but weren't re-verified against
// a live response in this session. If the backend rejects a request with
// a 422, open /docs on the backend, compare the real schema for that
// endpoint, and tell me what's different - it's a one-line fix here.
// ======================================================

import { get, post } from "./api";

// ======================================================
// IDEMPOTENCY
// ======================================================
//
// Every bet placement call carries a client-generated idempotency key, so
// a retried request (flaky network, double-tap) can never create two bet
// slips for the same intended bet.

export function newIdempotencyKey() {
  if (typeof crypto !== "undefined" && crypto.randomUUID) {
    return crypto.randomUUID();
  }
  return `idem-${Date.now()}-${Math.random().toString(16).slice(2)}`;
}

// ======================================================
// ODDS BOARD
// ======================================================

export async function getOddsBoard() {
  const data = await get("/betting/odds");
  return Array.isArray(data) ? data : [];
}

export async function getOddsHistory(matchId) {
  const data = await get(`/betting/odds/${matchId}/history`);
  return Array.isArray(data) ? data : [];
}

// ======================================================
// WALLET (paper money - see services/wallet admin dev-topup, admin only)
// ======================================================

export async function getWallet() {
  return await get("/betting/wallet");
}

export async function getWalletTransactions() {
  const data = await get("/betting/wallet/transactions");
  return Array.isArray(data?.transactions)
    ? data.transactions
    : Array.isArray(data)
      ? data
      : [];
}

// ======================================================
// BET SLIPS
// ======================================================

export async function placeSingleBet({ matchId, selection, stake }) {
  return await post("/betting/slips/single", {
    match_id: Number(matchId),
    selection,
    stake: Number(stake),
    idempotency_key: newIdempotencyKey(),
  });
}

export async function placeMultiBet({ legs, stake }) {
  return await post("/betting/slips/multi", {
    legs: legs.map((leg) => ({
      match_id: Number(leg.matchId),
      selection: leg.selection,
    })),
    stake: Number(stake),
    idempotency_key: newIdempotencyKey(),
  });
}

export async function getMySlips() {
  const data = await get("/betting/slips");
  return Array.isArray(data?.slips) ? data.slips : Array.isArray(data) ? data : [];
}

export async function getSlip(slipId) {
  return await get(`/betting/slips/${slipId}`);
}

// ======================================================
// JACKPOTS
// ======================================================

export async function getActiveJackpots() {
  const data = await get("/betting/jackpots");
  return Array.isArray(data) ? data : [];
}

export async function enterJackpot(jackpotId, { picks, stake }) {
  return await post(`/betting/jackpots/${jackpotId}/enter`, {
    picks,
    stake: Number(stake),
    idempotency_key: newIdempotencyKey(),
  });
}

export async function getMyJackpotEntries() {
  const data = await get("/betting/jackpots/entries/mine");
  return Array.isArray(data) ? data : [];
}

// ======================================================
// SELECTION LABELS
// ======================================================

export const SELECTIONS = {
  HOME: "HOME",
  DRAW: "DRAW",
  AWAY: "AWAY",
};

export function selectionLabel(selection, match) {
  if (selection === "HOME") return match?.home_team || "Home";
  if (selection === "AWAY") return match?.away_team || "Away";
  return "Draw";
}

export function oddsFor(match, selection) {
  if (!match) return null;
  if (selection === "HOME") return Number(match.home_odds);
  if (selection === "AWAY") return Number(match.away_odds);
  return Number(match.draw_odds);
}
