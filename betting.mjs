// Wallet + bet-slip business logic, backed by the SQLite tables in db.mjs.
//
// Settlement only resolves the match-result (1X2) market automatically,
// because that's the only market this app can verify against a fixture's
// final score. A leg placed on any other market is settled VOID (stake
// refunded) rather than guessed at — see settleFixtureLegs below.

import { db, run } from "./db.mjs";

export class InsufficientFundsError extends Error {}
export class BettingError extends Error {}

const STARTING_BALANCE = 10000; // KES, paper money only.
const round2 = (value) => Math.round((Number(value) + Number.EPSILON) * 100) / 100;

// ==========================================================
// WALLET
// ==========================================================

export function getOrCreateWallet(sessionId) {
  return run(() => {
    db.prepare(
      `INSERT INTO wallets (session_id, balance) VALUES (?, ?)
       ON CONFLICT (session_id) DO NOTHING`
    ).run(sessionId, STARTING_BALANCE);

    return db.prepare(`SELECT * FROM wallets WHERE session_id = ?`).get(sessionId);
  });
}

export function getWalletTransactions(sessionId, limit = 50) {
  return db
    .prepare(
      `SELECT * FROM wallet_transactions WHERE session_id = ? ORDER BY created_at DESC LIMIT ?`
    )
    .all(sessionId, limit);
}

/** Must run inside an open transaction (call from within `run(...)`). */
function applyWalletDelta(sessionId, amount, type, { reference = null, description = null } = {}) {
  const wallet = db.prepare(`SELECT balance FROM wallets WHERE session_id = ?`).get(sessionId);
  const current = wallet ? Number(wallet.balance) : STARTING_BALANCE;

  if (!wallet) {
    db.prepare(`INSERT INTO wallets (session_id, balance) VALUES (?, ?)`).run(sessionId, STARTING_BALANCE);
  }

  const nextBalance = round2(current + amount);

  if (nextBalance < 0) throw new InsufficientFundsError("Paper wallet balance is too low for this stake.");

  db.prepare(`UPDATE wallets SET balance = ?, updated_at = strftime('%Y-%m-%dT%H:%M:%fZ','now') WHERE session_id = ?`)
    .run(nextBalance, sessionId);

  db.prepare(
    `INSERT INTO wallet_transactions (session_id, type, amount, balance_after, reference, description)
     VALUES (?, ?, ?, ?, ?, ?)`
  ).run(sessionId, type, amount, nextBalance, reference, description);

  return nextBalance;
}

export function topUpWallet(sessionId, amount) {
  if (!(amount > 0) || amount > 50000) throw new BettingError("Top-up must be between 1 and 50,000 paper KES.");
  return run(() => applyWalletDelta(sessionId, round2(amount), "TOPUP", { description: "Manual demo top-up" }));
}

// ==========================================================
// BET PLACEMENT
// ==========================================================

function insertSlip(sessionId, betType, stake, combinedOdds, potentialPayout) {
  return db
    .prepare(
      `INSERT INTO bet_slips (session_id, bet_type, stake, combined_odds, potential_payout)
       VALUES (?, ?, ?, ?, ?) RETURNING *`
    )
    .get(sessionId, betType, stake, combinedOdds, potentialPayout);
}

function insertLeg(slipId, pick) {
  db.prepare(
    `INSERT INTO bet_legs (slip_id, fixture_id, match_label, league, market, pick_label, pick_key, odds)
     VALUES (?, ?, ?, ?, ?, ?, ?, ?)`
  ).run(slipId, pick.fixtureId, pick.match, pick.league || null, pick.market || null, pick.label, pick.key, Number(pick.odds));
}

function validatePick(pick) {
  if (!pick || !pick.fixtureId || !pick.key || !pick.label) throw new BettingError("Each selection needs a fixture, pick and label.");
  const odds = Number(pick.odds);
  if (!Number.isFinite(odds) || odds <= 1) throw new BettingError(`Invalid odds for ${pick.label}.`);
}

export function placeSingleBet(sessionId, picks, stakePerPick) {
  const stake = round2(Number(stakePerPick));
  if (!(stake > 0) || stake > 5000) throw new BettingError("Stake must be between 1 and 5,000 paper KES.");
  if (!picks.length) throw new BettingError("Add at least one selection.");
  picks.forEach(validatePick);

  return run(() => {
    const totalStake = round2(stake * picks.length);
    const potentialPayout = round2(picks.reduce((sum, pick) => sum + stake * Number(pick.odds), 0));

    applyWalletDelta(sessionId, -totalStake, "BET_STAKE", { description: `Single bet, ${picks.length} selection(s)` });

    const avgOdds = round2(potentialPayout / totalStake);
    const slip = insertSlip(sessionId, "single", totalStake, avgOdds, potentialPayout);
    picks.forEach((pick) => insertLeg(slip.id, pick));

    return getBetSlip(sessionId, slip.id);
  });
}

export function placeMultiBet(sessionId, picks, stake, kind = "multiple") {
  stake = round2(Number(stake));
  if (!(stake > 0) || stake > 5000) throw new BettingError("Stake must be between 1 and 5,000 paper KES.");
  const minLegs = kind === "jackpot" ? 5 : 2;
  if (picks.length < minLegs) throw new BettingError(`A ${kind} bet needs at least ${minLegs} selections.`);
  picks.forEach(validatePick);

  const fixtureIds = new Set(picks.map((pick) => pick.fixtureId));
  if (fixtureIds.size !== picks.length) throw new BettingError("Each fixture can only appear once in a multi/jackpot slip.");

  return run(() => {
    const combinedOdds = round2(picks.reduce((product, pick) => product * Number(pick.odds), 1));
    const potentialPayout = round2(stake * combinedOdds);

    applyWalletDelta(sessionId, -stake, "BET_STAKE", { description: `${kind} bet, ${picks.length} selections` });

    const slip = insertSlip(sessionId, kind, stake, combinedOdds, potentialPayout);
    picks.forEach((pick) => insertLeg(slip.id, pick));

    return getBetSlip(sessionId, slip.id);
  });
}

// ==========================================================
// READING
// ==========================================================

export function getBetSlip(sessionId, slipId) {
  const slip = db.prepare(`SELECT * FROM bet_slips WHERE id = ? AND session_id = ?`).get(slipId, sessionId);
  if (!slip) return null;
  slip.legs = db.prepare(`SELECT * FROM bet_legs WHERE slip_id = ? ORDER BY id ASC`).all(slipId);
  return slip;
}

export function listBetSlips(sessionId, limit = 30) {
  const slips = db
    .prepare(`SELECT * FROM bet_slips WHERE session_id = ? ORDER BY placed_at DESC LIMIT ?`)
    .all(sessionId, limit);

  const legsStatement = db.prepare(`SELECT * FROM bet_legs WHERE slip_id = ? ORDER BY id ASC`);
  for (const slip of slips) slip.legs = legsStatement.all(slip.id);
  return slips;
}

// ==========================================================
// SETTLEMENT
// ==========================================================

/**
 * Resolve every pending leg for `fixtureId`:
 *  - a leg picked on the 1X2 market (pick_key === "<fixtureId>:home|draw|away")
 *    is WON if it matches `winner`, else LOST;
 *  - any other leg (an exotic market this app can't verify) is VOIDed and
 *    its stake contribution refunded rather than guessed at.
 * Then resolves any bet_slip whose legs are now all settled: a slip wins
 * only if every non-void leg won; a VOID-only slip is voided and refunded
 * in full. Winning slips are paid into the wallet. Returns a summary.
 */
export function settleFixtureLegs(fixtureId, winner) {
  if (!["home", "draw", "away"].includes(winner)) throw new BettingError("winner must be home, draw or away.");

  return run(() => {
    const pendingLegs = db
      .prepare(`SELECT * FROM bet_legs WHERE fixture_id = ? AND status = 'PENDING'`)
      .all(fixtureId);

    const touchedSlips = new Set();
    let legsSettled = 0;

    for (const leg of pendingLegs) {
      const isMatchResultPick = leg.pick_key === `${fixtureId}:home` || leg.pick_key === `${fixtureId}:draw` || leg.pick_key === `${fixtureId}:away`;
      let status;

      if (!isMatchResultPick) {
        status = "VOID"; // can't verify this market's outcome from a final score alone
      } else {
        status = leg.pick_key === `${fixtureId}:${winner}` ? "WON" : "LOST";
      }

      db.prepare(`UPDATE bet_legs SET status = ? WHERE id = ?`).run(status, leg.id);
      legsSettled += 1;
      touchedSlips.add(leg.slip_id);
    }

    let slipsWon = 0;
    let slipsLost = 0;
    let slipsVoided = 0;
    let paidOut = 0;

    for (const slipId of touchedSlips) {
      const legs = db.prepare(`SELECT status, odds FROM bet_legs WHERE slip_id = ?`).all(slipId);

      if (legs.some((leg) => leg.status === "PENDING")) continue; // other fixtures in this slip still open

      const slip = db.prepare(`SELECT * FROM bet_slips WHERE id = ?`).get(slipId);
      const settledAt = `, settled_at=strftime('%Y-%m-%dT%H:%M:%fZ','now')`;

      if (slip.bet_type === "single") {
        // A grouped "single" slip is really N independent bets sharing one
        // stake-per-pick: each leg wins or loses on its own, and a voided
        // leg just gets its own stake refunded.
        const perLegStake = round2(slip.stake / legs.length);
        const payout = round2(
          legs.reduce((sum, leg) => {
            if (leg.status === "WON") return sum + perLegStake * leg.odds;
            if (leg.status === "VOID") return sum + perLegStake;
            return sum;
          }, 0)
        );

        const status = payout <= 0 ? "LOST" : legs.every((leg) => leg.status === "VOID") ? "VOID" : "WON";

        if (payout > 0) {
          applyWalletDelta(slip.session_id, payout, status === "VOID" ? "BET_REFUND" : "BET_PAYOUT", {
            reference: `slip:${slipId}`,
            description: `${status === "VOID" ? "Refund" : "Payout"} for bet slip #${slipId}`,
          });
        }

        db.prepare(`UPDATE bet_slips SET status=?, payout=?${settledAt} WHERE id=?`).run(status, payout, slipId);

        if (status === "WON") slipsWon += 1;
        else if (status === "VOID") slipsVoided += 1;
        else slipsLost += 1;
        paidOut = round2(paidOut + payout);
        continue;
      }

      // multiple / jackpot: a voided leg is dropped from the accumulator
      // (its odds don't count), but every remaining leg must still win.
      const decided = legs.filter((leg) => leg.status !== "VOID");

      if (decided.some((leg) => leg.status === "LOST")) {
        db.prepare(`UPDATE bet_slips SET status='LOST', payout=0${settledAt} WHERE id=?`).run(slipId);
        slipsLost += 1;
        continue;
      }

      if (decided.length === 0) {
        // every leg voided — full stake refund, nothing won or lost
        applyWalletDelta(slip.session_id, slip.stake, "BET_REFUND", {
          reference: `slip:${slipId}`,
          description: `Refund — all selections voided on slip #${slipId}`,
        });
        db.prepare(`UPDATE bet_slips SET status='VOID', payout=?${settledAt} WHERE id=?`).run(slip.stake, slipId);
        slipsVoided += 1;
        paidOut = round2(paidOut + slip.stake);
        continue;
      }

      // all remaining (non-void) legs won — recompute from their own odds
      // so a dropped leg doesn't still count toward the payout.
      const payout = round2(slip.stake * decided.reduce((product, leg) => product * leg.odds, 1));

      applyWalletDelta(slip.session_id, payout, "BET_PAYOUT", {
        reference: `slip:${slipId}`,
        description: `Payout for bet slip #${slipId}`,
      });

      db.prepare(`UPDATE bet_slips SET status='WON', payout=?${settledAt} WHERE id=?`).run(payout, slipId);
      slipsWon += 1;
      paidOut = round2(paidOut + payout);
    }

    return { fixtureId, winner, legsSettled, slipsWon, slipsLost, slipsVoided, paidOut };
  });
}
