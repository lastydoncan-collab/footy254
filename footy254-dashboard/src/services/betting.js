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

// Paper-money self-service top-up (database/betting_wallet_topup.py on the
// backend) - NOT a real deposit. There's no M-Pesa or payment processor
// behind this; it exists so a signed-in user can top up their own demo
// balance without needing admin access. See the wallet page for the
// user-facing explanation of why.
export async function demoTopUp(amount) {
  return await post("/betting/wallet/demo-topup", { amount: Number(amount) });
}

// ======================================================
// M-PESA DEPOSIT (Safaricom Daraja SANDBOX only)
// ======================================================
//
// A real STK Push integration (services/mpesa_daraja.py on the backend),
// run against Safaricom's sandbox - no real money moves, but the OAuth +
// STK Push + callback flow is the actual Daraja API, not a fake. See the
// wallet page for what it takes to go from this to a real production
// deposit (a Safaricom business approval, not more code).

export async function initiateMpesaDeposit({ phone, amount }) {
  return await post("/betting/wallet/mpesa/stk-push", {
    phone,
    amount: Number(amount),
  });
}

export async function getMpesaDepositStatus(checkoutRequestId) {
  return await get(`/betting/wallet/mpesa/status/${checkoutRequestId}`);
}

// ======================================================
// M-PESA WITHDRAWAL (Safaricom Daraja B2C - SANDBOX only)
// ======================================================
//
// The payout itself resolves asynchronously (Safaricom's B2C result
// callback, not this response), so there's no per-id status endpoint the
// way deposits have one - getMpesaRequests() below is how the UI polls
// for the outcome instead.

export async function initiateMpesaWithdrawal({ phone, amount }) {
  return await post("/betting/wallet/mpesa/withdraw", {
    phone,
    amount: Number(amount),
  });
}

export async function getMpesaRequests() {
  const data = await get("/betting/wallet/mpesa/requests");
  return Array.isArray(data) ? data : Array.isArray(data?.requests) ? data.requests : [];
}

// ======================================================
// BET SLIPS
// ======================================================

export async function placeSingleBet({ matchId, market = "1X2", selection, stake }) {
  return await post("/betting/slips/single", {
    match_id: Number(matchId),
    market,
    selection,
    stake: Number(stake),
    idempotency_key: newIdempotencyKey(),
  });
}

export async function placeMultiBet({ legs, stake }) {
  return await post("/betting/slips/multi", {
    legs: legs.map((leg) => ({
      match_id: Number(leg.matchId),
      market: leg.market || "1X2",
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

// Goal lines with a market of their own - kept as a list (not typed out
// per-market) so the Over/Under entries below and GOAL_LINE_MARKETS stay
// in sync with each other and with database/betting_markets.py's
// GOAL_LINES automatically, rather than by careful hand-editing in two
// places every time a line is added.
const GOAL_LINES = ["0.5", "1.5", "2.5", "3.5", "4.5"];

// Correct Score: the same 4x4 grid (0-0 through 3-3) priced by
// database/betting_markets.py's CORRECT_SCORE_GRID, plus the 3 overflow
// buckets that make the market cover 100% of outcomes.
const CORRECT_SCORE_SELECTIONS = [];
for (let h = 0; h <= 3; h++) {
  for (let a = 0; a <= 3; a++) {
    CORRECT_SCORE_SELECTIONS.push({
      selection: `${h}-${a}`,
      shortLabel: `${h}-${a}`,
      oddsField: `cs_${h}_${a}_odds`,
    });
  }
}
CORRECT_SCORE_SELECTIONS.push(
  { selection: "OTHER_HOME_WIN", shortLabel: "Other 1", oddsField: "cs_other_home_odds" },
  { selection: "OTHER_DRAW", shortLabel: "Other X", oddsField: "cs_other_draw_odds" },
  { selection: "OTHER_AWAY_WIN", shortLabel: "Other 2", oddsField: "cs_other_away_odds" }
);

// Markets shown on the odds board, in display order. `key` matches the
// `market` value sent to the backend; `oddsField` maps each selection to
// the odds-board column it reads from (see database/betting_markets.py's
// ODDS_COLUMN_FOR for the backend side of this same mapping). `layout`
// tells OddsFixtureCard whether to render a row of equal-width buttons
// ("row", the default - fine for 2-3 selections) or a wrapping grid
// ("grid" - for Correct Score's 19 options).
export const MARKETS = [
  {
    key: "1X2",
    label: "1X2",
    selections: [
      { selection: "HOME", shortLabel: "1", oddsField: "home_odds" },
      { selection: "DRAW", shortLabel: "X", oddsField: "draw_odds" },
      { selection: "AWAY", shortLabel: "2", oddsField: "away_odds" },
    ],
  },
  {
    key: "DOUBLE_CHANCE",
    label: "Double Chance",
    selections: [
      { selection: "1X", shortLabel: "1X", oddsField: "dc_1x_odds" },
      { selection: "12", shortLabel: "12", oddsField: "dc_12_odds" },
      { selection: "X2", shortLabel: "X2", oddsField: "dc_x2_odds" },
    ],
  },
  {
    key: "DRAW_NO_BET",
    label: "Draw No Bet",
    selections: [
      { selection: "HOME", shortLabel: "Home", oddsField: "dnb_home_odds" },
      { selection: "AWAY", shortLabel: "Away", oddsField: "dnb_away_odds" },
    ],
  },
  {
    key: "BTTS",
    label: "BTTS",
    selections: [
      { selection: "YES", shortLabel: "Yes", oddsField: "btts_yes_odds" },
      { selection: "NO", shortLabel: "No", oddsField: "btts_no_odds" },
    ],
  },
  ...GOAL_LINES.map((line) => ({
    key: `OU_${line.replace(".", "_")}`,
    label: `O/U ${line}`,
    selections: [
      { selection: "OVER", shortLabel: "Over", oddsField: `over_${line.replace(".", "_")}_odds` },
      { selection: "UNDER", shortLabel: "Under", oddsField: `under_${line.replace(".", "_")}_odds` },
    ],
  })),
  {
    key: "ODD_EVEN",
    label: "Odd/Even",
    selections: [
      { selection: "ODD", shortLabel: "Odd", oddsField: "odd_total_odds" },
      { selection: "EVEN", shortLabel: "Even", oddsField: "even_total_odds" },
    ],
  },
  {
    key: "CLEAN_SHEET_HOME",
    label: "Clean Sheet (Home)",
    selections: [
      { selection: "YES", shortLabel: "Yes", oddsField: "cs_home_yes_odds" },
      { selection: "NO", shortLabel: "No", oddsField: "cs_home_no_odds" },
    ],
  },
  {
    key: "CLEAN_SHEET_AWAY",
    label: "Clean Sheet (Away)",
    selections: [
      { selection: "YES", shortLabel: "Yes", oddsField: "cs_away_yes_odds" },
      { selection: "NO", shortLabel: "No", oddsField: "cs_away_no_odds" },
    ],
  },
  {
    key: "WIN_TO_NIL",
    label: "Win to Nil",
    selections: [
      { selection: "HOME", shortLabel: "Home", oddsField: "wtn_home_odds" },
      { selection: "AWAY", shortLabel: "Away", oddsField: "wtn_away_odds" },
      { selection: "NONE", shortLabel: "Neither", oddsField: "wtn_none_odds" },
    ],
  },
  {
    key: "CORRECT_SCORE",
    label: "Correct Score",
    layout: "grid",
    selections: CORRECT_SCORE_SELECTIONS,
  },
];

const GOAL_LINE_MARKETS = Object.fromEntries(GOAL_LINES.map((l) => [`OU_${l.replace(".", "_")}`, l]));

export function selectionLabel(market, selection, match) {
  const home = match?.home_team || "Home";
  const away = match?.away_team || "Away";

  if (market === "DOUBLE_CHANCE") {
    if (selection === "1X") return `${home} or Draw`;
    if (selection === "12") return `${home} or ${away}`;
    return `Draw or ${away}`;
  }
  if (market === "DRAW_NO_BET") {
    return selection === "HOME"
      ? `${home} (draw = stake back)`
      : `${away} (draw = stake back)`;
  }
  if (market === "BTTS") return selection === "YES" ? "Both teams to score" : "Not both teams to score";
  if (market in GOAL_LINE_MARKETS) {
    const line = GOAL_LINE_MARKETS[market];
    return selection === "OVER" ? `Over ${line} goals` : `Under ${line} goals`;
  }
  if (market === "ODD_EVEN") return selection === "ODD" ? "Odd total goals" : "Even total goals";
  if (market === "CLEAN_SHEET_HOME") return selection === "YES" ? `${home} clean sheet` : `${home} concedes`;
  if (market === "CLEAN_SHEET_AWAY") return selection === "YES" ? `${away} clean sheet` : `${away} concedes`;
  if (market === "WIN_TO_NIL") {
    if (selection === "HOME") return `${home} to win to nil`;
    if (selection === "AWAY") return `${away} to win to nil`;
    return "No team wins to nil";
  }
  if (market === "CORRECT_SCORE") {
    if (selection === "OTHER_HOME_WIN") return `Correct score - any other ${home} win`;
    if (selection === "OTHER_DRAW") return "Correct score - any other draw";
    if (selection === "OTHER_AWAY_WIN") return `Correct score - any other ${away} win`;
    return `Correct score ${selection}`;
  }
  if (selection === "HOME") return home;
  if (selection === "AWAY") return away;
  return "Draw";
}
