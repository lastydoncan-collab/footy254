"""
Betting data access: wallets, odds, single/multi bet slips and jackpots.

Follows the same shape as the rest of database/*: plain functions, the
pooled `get_connection()` context manager, and RealDictCursor rows returned
straight to the caller.
"""

import logging

from decimal import Decimal, ROUND_HALF_UP

import psycopg2

from database.db_config import get_connection

logger = logging.getLogger(__name__)

# 7% overround, same figure used in the public odds explainer the product
# already cites — not pulled from any competitor's live feed.
DEFAULT_MARGIN = Decimal("0.07")
MIN_ODDS = Decimal("1.05")

TWO_PLACES = Decimal("0.01")

# Exposure-based odds shading: once a fixture's pending stake clears this
# threshold, an outcome carrying more than its fair (1/3) share of that
# stake gets its price nudged down — the same lever a trading desk pulls
# to manage liability on a popular selection, bounded so it never strays
# far from the model's own price.
EXPOSURE_THRESHOLD = Decimal("500")
MAX_SHADE = Decimal("0.15")
SHADE_SENSITIVITY = Decimal("0.6")
FAIR_SHARE = Decimal("1") / Decimal("3")


class InsufficientFundsError(Exception):
    """Raised when a wallet debit would take the balance below zero."""


class BettingError(Exception):
    """Raised for invalid bet requests (bad pick, closed market, ...)."""


# ==========================================================
# ODDS
# ==========================================================

def _price(probability) -> Decimal:
    """probability -> decimal odds, matching the product's published margin."""

    probability = Decimal(str(probability))

    if probability <= 0:
        return Decimal("999.00")

    raw = (Decimal(1) / probability) / (Decimal(1) - DEFAULT_MARGIN)

    return max(MIN_ODDS, raw.quantize(TWO_PLACES, rounding=ROUND_HALF_UP))


def generate_odds_for_fixture(match_id):
    """
    Derive 1X2 odds for one fixture from its stored model prediction and
    upsert them into `odds`. Returns the odds row, or None if the fixture
    has no prediction yet.
    """

    with get_connection() as conn:

        with conn.cursor() as cur:

            cur.execute(
                """
                SELECT home_win, draw, away_win
                FROM predictions
                WHERE match_id = %s;
                """,
                (match_id,),
            )

            prediction = cur.fetchone()

            if prediction is None:
                return None

            # predictions.home_win/draw/away_win are stored as 0-100
            # percentages (ml_pipeline/core/predict_engine.py's predict()
            # does `probabilities["home_win"] * 100` before it's saved by
            # database/predictions_repository.py) — _price() expects a
            # 0-1 probability. Feeding it the raw percentage (e.g. 55.23
            # instead of 0.5523) makes 1/probability collapse to a few
            # hundredths, which the MIN_ODDS floor then clamps to 1.05 for
            # every outcome of every fixture. Converting here is the fix.
            home_odds = _price(Decimal(str(prediction["home_win"])) / 100)
            draw_odds = _price(Decimal(str(prediction["draw"])) / 100)
            away_odds = _price(Decimal(str(prediction["away_win"])) / 100)

            cur.execute(
                """
                INSERT INTO odds (match_id, home_odds, draw_odds, away_odds, margin, source, generated_at)
                VALUES (%s, %s, %s, %s, %s, 'MODEL', NOW())
                ON CONFLICT (match_id) DO UPDATE SET
                    home_odds    = EXCLUDED.home_odds,
                    draw_odds    = EXCLUDED.draw_odds,
                    away_odds    = EXCLUDED.away_odds,
                    margin       = EXCLUDED.margin,
                    source       = 'MODEL',
                    generated_at = NOW()
                RETURNING *;
                """,
                (match_id, home_odds, draw_odds, away_odds, DEFAULT_MARGIN),
            )

            row = cur.fetchone()

            cur.execute(
                """
                INSERT INTO odds_history (match_id, home_odds, draw_odds, away_odds, reason)
                VALUES (%s, %s, %s, %s, 'MODEL');
                """,
                (match_id, row["home_odds"], row["draw_odds"], row["away_odds"]),
            )

        conn.commit()

    return row


def shade_odds_for_exposure(match_id):
    """
    Re-price one fixture's odds against its current pending stake. Below
    EXPOSURE_THRESHOLD total stake, this is a no-op (the model price
    stands). Above it, any outcome holding more than its fair 1/3 share of
    that stake gets shaded down by up to MAX_SHADE (never below MIN_ODDS),
    proportional to how far over its fair share it is. Writes the result
    to `odds` and appends it to `odds_history`. Returns the odds row, or
    None if the fixture has no odds yet.
    """

    with get_connection() as conn:

        with conn.cursor() as cur:

            cur.execute("SELECT * FROM odds WHERE match_id = %s;", (match_id,))
            current = cur.fetchone()

            if current is None:
                return None

            cur.execute(
                """
                SELECT bl.pick, COALESCE(SUM(bs.stake), 0) AS stake
                FROM bet_legs bl
                JOIN bet_slips bs ON bs.id = bl.slip_id AND bs.status = 'PENDING'
                WHERE bl.match_id = %s AND bl.status = 'PENDING'
                GROUP BY bl.pick;
                """,
                (match_id,),
            )
            stake_by_pick = {row["pick"]: Decimal(row["stake"]) for row in cur.fetchall()}
            total_stake = sum(stake_by_pick.values(), Decimal("0"))

            model_prices = {
                "HOME": Decimal(current["home_odds"]),
                "DRAW": Decimal(current["draw_odds"]),
                "AWAY": Decimal(current["away_odds"]),
            }

            if total_stake < EXPOSURE_THRESHOLD:
                new_prices, reason = model_prices, "MODEL"
            else:
                new_prices, reason = {}, "EXPOSURE_SHADE"

                for pick, price in model_prices.items():
                    stake_share = stake_by_pick.get(pick, Decimal("0")) / total_stake
                    overexposure = max(Decimal("0"), stake_share - FAIR_SHARE)
                    shade = min(MAX_SHADE, overexposure * SHADE_SENSITIVITY)
                    shaded = (price * (Decimal("1") - shade)).quantize(TWO_PLACES, rounding=ROUND_HALF_UP)
                    new_prices[pick] = max(MIN_ODDS, shaded)

            unchanged = (
                reason == current["source"]
                and new_prices["HOME"] == Decimal(current["home_odds"])
                and new_prices["DRAW"] == Decimal(current["draw_odds"])
                and new_prices["AWAY"] == Decimal(current["away_odds"])
            )

            # Re-pricing ticks every 20s for every fixture with open odds
            # (see services/scheduler.py); writing a row and pushing a
            # websocket update when nothing actually moved would flood
            # odds_history and spam every connected client with no-op
            # "updates" for the entire duration a fixture stays open. Only
            # a genuine price change is worth persisting and broadcasting.
            if unchanged:
                return None

            cur.execute(
                """
                UPDATE odds
                SET home_odds = %s, draw_odds = %s, away_odds = %s,
                    source = %s, generated_at = NOW()
                WHERE match_id = %s
                RETURNING *;
                """,
                (new_prices["HOME"], new_prices["DRAW"], new_prices["AWAY"], reason, match_id),
            )
            row = cur.fetchone()

            cur.execute(
                """
                INSERT INTO odds_history (match_id, home_odds, draw_odds, away_odds, reason)
                VALUES (%s, %s, %s, %s, %s);
                """,
                (match_id, row["home_odds"], row["draw_odds"], row["away_odds"], reason),
            )

        conn.commit()

    return row


def get_odds(match_id):

    with get_connection() as conn:

        with conn.cursor() as cur:

            cur.execute("SELECT * FROM odds WHERE match_id = %s;", (match_id,))

            return cur.fetchone()


def get_odds_board():
    """Current odds for every fixture that still accepts bets."""

    with get_connection() as conn:

        with conn.cursor() as cur:

            cur.execute(
                """
                SELECT
                    o.*,
                    f.home_team,
                    f.away_team,
                    f.competition,
                    f.kickoff,
                    f.status AS fixture_status
                FROM odds o
                JOIN fixtures f ON f.match_id = o.match_id
                WHERE f.status IN ('SCHEDULED', 'TIMED')
                  AND f.kickoff >= NOW()
                ORDER BY f.kickoff ASC;
                """
            )

            return cur.fetchall()


def get_fixtures_needing_odds():
    """SCHEDULED/TIMED fixtures with a model prediction but no odds row yet
    — what the scheduler polls instead of an admin manually generating odds
    per fixture."""

    with get_connection() as conn:

        with conn.cursor() as cur:

            cur.execute(
                """
                SELECT p.match_id
                FROM predictions p
                JOIN fixtures f ON f.match_id = p.match_id
                LEFT JOIN odds o ON o.match_id = p.match_id
                WHERE o.match_id IS NULL
                  AND f.status IN ('SCHEDULED', 'TIMED')
                  AND f.kickoff >= NOW();
                """
            )

            return [row["match_id"] for row in cur.fetchall()]


def get_open_odds_match_ids():
    """Fixtures currently carrying live odds and still open for betting —
    the set the scheduler periodically re-shades against fresh exposure."""

    with get_connection() as conn:

        with conn.cursor() as cur:

            cur.execute(
                """
                SELECT o.match_id
                FROM odds o
                JOIN fixtures f ON f.match_id = o.match_id
                WHERE f.status IN ('SCHEDULED', 'TIMED') AND f.kickoff >= NOW();
                """
            )

            return [row["match_id"] for row in cur.fetchall()]


def get_fixtures_with_pending_settlement():
    """FINISHED fixtures that still have PENDING bet legs waiting on them."""

    with get_connection() as conn:

        with conn.cursor() as cur:

            cur.execute(
                """
                SELECT DISTINCT bl.match_id
                FROM bet_legs bl
                JOIN fixtures f ON f.match_id = bl.match_id
                WHERE bl.status = 'PENDING'
                  AND f.status = 'FINISHED'
                  AND f.winner IS NOT NULL;
                """
            )

            return [row["match_id"] for row in cur.fetchall()]


def get_odds_history(match_id, limit=100):

    with get_connection() as conn:

        with conn.cursor() as cur:

            cur.execute(
                """
                SELECT * FROM odds_history
                WHERE match_id = %s
                ORDER BY recorded_at DESC
                LIMIT %s;
                """,
                (match_id, limit),
            )

            return cur.fetchall()


def _require_open_odds(cur, match_id, pick):
    """Load odds for an open fixture, locking nothing (pricing is advisory,
    not a live order book), and return the price for `pick`."""

    cur.execute(
        """
        SELECT o.home_odds, o.draw_odds, o.away_odds, f.status AS fixture_status
        FROM odds o
        JOIN fixtures f ON f.match_id = o.match_id
        WHERE o.match_id = %s;
        """,
        (match_id,),
    )

    row = cur.fetchone()

    if row is None:
        raise BettingError(f"No odds available for fixture {match_id}.")

    if row["fixture_status"] not in ("SCHEDULED", "TIMED"):
        raise BettingError(f"Betting is closed for fixture {match_id}.")

    odds_by_pick = {
        "HOME": row["home_odds"],
        "DRAW": row["draw_odds"],
        "AWAY": row["away_odds"],
    }

    if pick not in odds_by_pick:
        raise BettingError("Pick must be one of HOME, DRAW, AWAY.")

    return odds_by_pick[pick]


# ==========================================================
# WALLET
# ==========================================================

def get_or_create_wallet(user_id):

    with get_connection() as conn:

        with conn.cursor() as cur:

            cur.execute(
                """
                INSERT INTO wallets (user_id)
                VALUES (%s)
                ON CONFLICT (user_id) DO NOTHING
                RETURNING *;
                """,
                (user_id,),
            )

            row = cur.fetchone()

            if row is None:
                cur.execute("SELECT * FROM wallets WHERE user_id = %s;", (user_id,))
                row = cur.fetchone()

        conn.commit()

    return row


def get_wallet_transactions(user_id, limit=50):

    with get_connection() as conn:

        with conn.cursor() as cur:

            cur.execute(
                """
                SELECT *
                FROM wallet_transactions
                WHERE user_id = %s
                ORDER BY created_at DESC
                LIMIT %s;
                """,
                (user_id, limit),
            )

            return cur.fetchall()


def _apply_wallet_delta(cur, user_id, amount: Decimal, tx_type, reference=None, description=None):
    """
    Move `amount` (positive = credit, negative = debit) on an already-open
    cursor, inside the caller's transaction. Raises InsufficientFundsError
    on a debit that would go negative; the caller's `with get_connection()`
    rolls back automatically.
    """

    cur.execute(
        "SELECT balance FROM wallets WHERE user_id = %s FOR UPDATE;",
        (user_id,),
    )

    wallet = cur.fetchone()

    if wallet is None:
        cur.execute(
            "INSERT INTO wallets (user_id) VALUES (%s) RETURNING balance;",
            (user_id,),
        )
        wallet = cur.fetchone()

    new_balance = Decimal(wallet["balance"]) + amount

    if new_balance < 0:
        raise InsufficientFundsError("Insufficient wallet balance.")

    cur.execute(
        "UPDATE wallets SET balance = %s, updated_at = NOW() WHERE user_id = %s;",
        (new_balance, user_id),
    )

    cur.execute(
        """
        INSERT INTO wallet_transactions
            (user_id, type, amount, balance_after, reference, description)
        VALUES (%s, %s, %s, %s, %s, %s);
        """,
        (user_id, tx_type, amount, new_balance, reference, description),
    )

    return new_balance


def credit_wallet(user_id, amount, tx_type, reference=None, description=None):
    """Standalone credit (e.g. a manual top-up). Commits on its own."""

    amount = Decimal(str(amount))

    with get_connection() as conn:

        with conn.cursor() as cur:

            new_balance = _apply_wallet_delta(cur, user_id, amount, tx_type, reference, description)

        conn.commit()

    return new_balance


# ==========================================================
# SINGLE / MULTI BET SLIPS
# ==========================================================

def _existing_slip_for_key(cur, user_id, idempotency_key):
    """If this (user, key) pair already placed a slip, return its id so the
    caller can short-circuit instead of staking twice on a retry."""

    if not idempotency_key:
        return None

    cur.execute(
        "SELECT id FROM bet_slips WHERE user_id = %s AND idempotency_key = %s;",
        (user_id, idempotency_key),
    )
    row = cur.fetchone()
    return row["id"] if row else None


def place_single_bet(user_id, match_id, pick, stake, idempotency_key=None):

    stake = Decimal(str(stake))

    if stake <= 0:
        raise BettingError("Stake must be greater than zero.")

    try:
        with get_connection() as conn:

            with conn.cursor() as cur:

                existing_id = _existing_slip_for_key(cur, user_id, idempotency_key)
                if existing_id:
                    return get_bet_slip(existing_id, user_id)

                price = _require_open_odds(cur, match_id, pick)
                price = Decimal(price)

                _apply_wallet_delta(
                    cur, user_id, -stake, "BET_STAKE",
                    description=f"Single bet on fixture {match_id} ({pick})",
                )

                potential_payout = (stake * price).quantize(TWO_PLACES, rounding=ROUND_HALF_UP)

                cur.execute(
                    """
                    INSERT INTO bet_slips (user_id, bet_type, stake, combined_odds, potential_payout, idempotency_key)
                    VALUES (%s, 'SINGLE', %s, %s, %s, %s)
                    RETURNING *;
                    """,
                    (user_id, stake, price, potential_payout, idempotency_key),
                )

                slip = cur.fetchone()

                cur.execute(
                    """
                    INSERT INTO bet_legs (slip_id, match_id, pick, odds)
                    VALUES (%s, %s, %s, %s);
                    """,
                    (slip["id"], match_id, pick, price),
                )

            conn.commit()
    except psycopg2.errors.UniqueViolation:
        # Lost a race against a concurrent retry carrying the same key —
        # the other request's slip is the real one; hand that back instead.
        with get_connection() as conn:
            with conn.cursor() as cur:
                existing_id = _existing_slip_for_key(cur, user_id, idempotency_key)
        if existing_id:
            return get_bet_slip(existing_id, user_id)
        raise

    return get_bet_slip(slip["id"], user_id)


def place_multi_bet(user_id, legs, stake, idempotency_key=None):
    """
    legs: list of {"match_id": int, "pick": "HOME"|"DRAW"|"AWAY"}.
    Combined odds = product of each leg's current price.
    """

    stake = Decimal(str(stake))

    if stake <= 0:
        raise BettingError("Stake must be greater than zero.")

    if len(legs) < 2:
        raise BettingError("A multi-bet needs at least 2 legs.")

    seen_fixtures = {leg["match_id"] for leg in legs}

    if len(seen_fixtures) != len(legs):
        raise BettingError("A multi-bet cannot include the same fixture twice.")

    try:
        with get_connection() as conn:

            with conn.cursor() as cur:

                existing_id = _existing_slip_for_key(cur, user_id, idempotency_key)
                if existing_id:
                    return get_bet_slip(existing_id, user_id)

                combined_odds = Decimal("1")
                priced_legs = []

                for leg in legs:
                    price = Decimal(_require_open_odds(cur, leg["match_id"], leg["pick"]))
                    combined_odds *= price
                    priced_legs.append((leg["match_id"], leg["pick"], price))

                combined_odds = combined_odds.quantize(TWO_PLACES, rounding=ROUND_HALF_UP)

                _apply_wallet_delta(
                    cur, user_id, -stake, "BET_STAKE",
                    description=f"Multi-bet ({len(legs)} legs)",
                )

                potential_payout = (stake * combined_odds).quantize(TWO_PLACES, rounding=ROUND_HALF_UP)

                cur.execute(
                    """
                    INSERT INTO bet_slips (user_id, bet_type, stake, combined_odds, potential_payout, idempotency_key)
                    VALUES (%s, 'MULTI', %s, %s, %s, %s)
                    RETURNING *;
                    """,
                    (user_id, stake, combined_odds, potential_payout, idempotency_key),
                )

                slip = cur.fetchone()

                for match_id, pick, price in priced_legs:
                    cur.execute(
                        """
                        INSERT INTO bet_legs (slip_id, match_id, pick, odds)
                        VALUES (%s, %s, %s, %s);
                        """,
                        (slip["id"], match_id, pick, price),
                    )

            conn.commit()
    except psycopg2.errors.UniqueViolation:
        with get_connection() as conn:
            with conn.cursor() as cur:
                existing_id = _existing_slip_for_key(cur, user_id, idempotency_key)
        if existing_id:
            return get_bet_slip(existing_id, user_id)
        raise

    return get_bet_slip(slip["id"], user_id)


def get_bet_slip(slip_id, user_id=None):

    with get_connection() as conn:

        with conn.cursor() as cur:

            if user_id is not None:
                cur.execute(
                    "SELECT * FROM bet_slips WHERE id = %s AND user_id = %s;",
                    (slip_id, user_id),
                )
            else:
                cur.execute("SELECT * FROM bet_slips WHERE id = %s;", (slip_id,))

            slip = cur.fetchone()

            if slip is None:
                return None

            cur.execute(
                """
                SELECT bl.*, f.home_team, f.away_team, f.kickoff, f.status AS fixture_status
                FROM bet_legs bl
                JOIN fixtures f ON f.match_id = bl.match_id
                WHERE bl.slip_id = %s
                ORDER BY bl.id ASC;
                """,
                (slip_id,),
            )

            slip["legs"] = cur.fetchall()

    return slip


def get_user_bet_slips(user_id, status=None, limit=50):

    with get_connection() as conn:

        with conn.cursor() as cur:

            if status:
                cur.execute(
                    """
                    SELECT * FROM bet_slips
                    WHERE user_id = %s AND status = %s
                    ORDER BY placed_at DESC
                    LIMIT %s;
                    """,
                    (user_id, status, limit),
                )
            else:
                cur.execute(
                    """
                    SELECT * FROM bet_slips
                    WHERE user_id = %s
                    ORDER BY placed_at DESC
                    LIMIT %s;
                    """,
                    (user_id, limit),
                )

            slips = cur.fetchall()

            for slip in slips:
                cur.execute(
                    """
                    SELECT bl.*, f.home_team, f.away_team, f.kickoff
                    FROM bet_legs bl
                    JOIN fixtures f ON f.match_id = bl.match_id
                    WHERE bl.slip_id = %s
                    ORDER BY bl.id ASC;
                    """,
                    (slip["id"],),
                )
                slip["legs"] = cur.fetchall()

    return slips


# ==========================================================
# SETTLEMENT  (called once a fixture's winner is known)
# ==========================================================

def settle_fixture_bets(match_id):
    """
    Resolve every pending bet_leg on this fixture against fixtures.winner
    ('HOME' | 'AWAY' | 'DRAW'), then resolve any bet_slip whose legs are
    now all settled: a single or multi wins only if every leg won, and
    loses as soon as any leg is lost. Winning slips are paid out to the
    bettor's wallet. Returns a summary dict.
    """

    settled_legs = 0
    won_slips = 0
    lost_slips = 0
    paid_out = Decimal("0")

    with get_connection() as conn:

        with conn.cursor() as cur:

            cur.execute("SELECT winner, status FROM fixtures WHERE match_id = %s;", (match_id,))
            fixture = cur.fetchone()

            if fixture is None:
                raise BettingError(f"Unknown fixture {match_id}.")

            if fixture["status"] != "FINISHED" or not fixture["winner"]:
                raise BettingError(f"Fixture {match_id} has not finished yet.")

            winner = fixture["winner"]

            cur.execute(
                "SELECT id, slip_id, pick FROM bet_legs WHERE match_id = %s AND status = 'PENDING';",
                (match_id,),
            )
            pending_legs = cur.fetchall()

            affected_slip_ids = set()

            for leg in pending_legs:
                leg_status = "WON" if leg["pick"] == winner else "LOST"

                cur.execute(
                    "UPDATE bet_legs SET status = %s WHERE id = %s;",
                    (leg_status, leg["id"]),
                )

                settled_legs += 1
                affected_slip_ids.add(leg["slip_id"])

            for slip_id in affected_slip_ids:

                cur.execute(
                    "SELECT status FROM bet_legs WHERE slip_id = %s;",
                    (slip_id,),
                )
                leg_statuses = {row["status"] for row in cur.fetchall()}

                if "LOST" in leg_statuses:
                    final_status = "LOST"
                elif "PENDING" in leg_statuses:
                    continue  # other legs still unresolved — settle later
                else:
                    final_status = "WON"

                cur.execute(
                    "SELECT user_id, stake, potential_payout FROM bet_slips WHERE id = %s FOR UPDATE;",
                    (slip_id,),
                )
                slip = cur.fetchone()

                payout = slip["potential_payout"] if final_status == "WON" else None

                cur.execute(
                    """
                    UPDATE bet_slips
                    SET status = %s, payout = %s, settled_at = NOW()
                    WHERE id = %s;
                    """,
                    (final_status, payout, slip_id),
                )

                if final_status == "WON":
                    _apply_wallet_delta(
                        cur, slip["user_id"], Decimal(slip["potential_payout"]), "BET_PAYOUT",
                        reference=f"slip:{slip_id}",
                        description=f"Payout for bet slip #{slip_id}",
                    )
                    won_slips += 1
                    paid_out += Decimal(slip["potential_payout"])
                else:
                    lost_slips += 1

        conn.commit()

    logger.info(
        "Settled fixture %s: %d legs, %d slips won, %d slips lost, %.2f paid out.",
        match_id, settled_legs, won_slips, lost_slips, paid_out,
    )

    return {
        "match_id": match_id,
        "winner": winner,
        "legs_settled": settled_legs,
        "slips_won": won_slips,
        "slips_lost": lost_slips,
        "paid_out": paid_out,
    }


# ==========================================================
# RISK / EXPOSURE REPORTING  (trading-desk-lite — paper money, admin only)
# ==========================================================

def get_fixture_exposure(match_id=None):
    """
    Outstanding liability, grouped by (fixture, pick), across every PENDING
    bet slip that has a leg on that pick.

    For a SINGLE slip this is exact. For a MULTI/JACKPOT slip it's the
    slip's FULL potential_payout counted against this one leg — i.e. the
    worst case where every other leg in that slip also wins. That's a
    deliberate upper bound, not a joint-probability estimate (computing a
    true probability-weighted liability across correlated multi-leg slips
    is a materially harder problem); it's exactly the "what's the most we
    could owe" number a risk desk checks before deciding whether to shade
    an outcome's price.
    """

    with get_connection() as conn:

        with conn.cursor() as cur:

            cur.execute(
                """
                SELECT
                    bl.match_id,
                    bl.pick,
                    COUNT(DISTINCT bl.slip_id)                       AS slip_count,
                    COALESCE(SUM(DISTINCT_SLIP.stake), 0)            AS stake_collected,
                    COALESCE(SUM(DISTINCT_SLIP.potential_payout), 0) AS payout_if_all_win
                FROM bet_legs bl
                JOIN LATERAL (
                    SELECT bs.id, bs.stake, bs.potential_payout
                    FROM bet_slips bs
                    WHERE bs.id = bl.slip_id AND bs.status = 'PENDING'
                ) AS DISTINCT_SLIP ON TRUE
                WHERE bl.status = 'PENDING'
                  AND (%(match_id)s::bigint IS NULL OR bl.match_id = %(match_id)s)
                GROUP BY bl.match_id, bl.pick
                ORDER BY bl.match_id, bl.pick;
                """,
                {"match_id": match_id},
            )

            rows = cur.fetchall()

    for row in rows:
        row["net_position"] = Decimal(row["stake_collected"]) - Decimal(row["payout_if_all_win"])

    return rows


def get_volume_report(hours=24):
    """Bet volume and stake totals over the trailing window, by bet type."""

    with get_connection() as conn:

        with conn.cursor() as cur:

            cur.execute(
                """
                SELECT
                    bet_type,
                    COUNT(*)                                             AS slip_count,
                    COALESCE(SUM(stake), 0)                              AS total_staked,
                    COALESCE(SUM(stake) FILTER (WHERE status = 'WON'), 0) AS stake_on_won,
                    COALESCE(SUM(payout) FILTER (WHERE status = 'WON'), 0) AS total_paid_out,
                    COUNT(*) FILTER (WHERE status = 'PENDING')           AS pending_count,
                    COUNT(*) FILTER (WHERE status = 'WON')               AS won_count,
                    COUNT(*) FILTER (WHERE status = 'LOST')              AS lost_count,
                    COUNT(*) FILTER (WHERE status = 'VOID')              AS void_count
                FROM bet_slips
                WHERE placed_at >= NOW() - (%s || ' hours')::interval
                GROUP BY bet_type
                ORDER BY bet_type;
                """,
                (hours,),
            )

            by_type = cur.fetchall()

            cur.execute(
                """
                SELECT
                    COUNT(*)                 AS slip_count,
                    COALESCE(SUM(stake), 0)  AS total_staked,
                    COALESCE(SUM(payout) FILTER (WHERE status = 'WON'), 0) AS total_paid_out
                FROM bet_slips
                WHERE placed_at >= NOW() - (%s || ' hours')::interval;
                """,
                (hours,),
            )

            totals = cur.fetchone()

    return {"window_hours": hours, "by_type": by_type, "totals": totals}


# ==========================================================
# JACKPOTS
# ==========================================================

def create_jackpot(name, stake_amount, match_ids, tiers, opens_at=None, closes_at=None):
    """
    match_ids: ordered list of fixture match_ids (sequence = list order).
    tiers: list of {"min_correct": int, "payout_multiplier": number}, e.g.
        [{"min_correct": 17, "payout_multiplier": 400}, {"min_correct": 13, "payout_multiplier": 20}]
    Every fixture must still be SCHEDULED/TIMED; a jackpot can't be built on
    a match that's already kicked off or finished.
    """

    if len(match_ids) < 2:
        raise BettingError("A jackpot needs at least 2 fixtures.")

    if len(set(match_ids)) != len(match_ids):
        raise BettingError("A jackpot cannot list the same fixture twice.")

    if not tiers:
        raise BettingError("A jackpot needs at least one payout tier.")

    with get_connection() as conn:

        with conn.cursor() as cur:

            cur.execute(
                """
                SELECT match_id FROM fixtures
                WHERE match_id = ANY(%s) AND status IN ('SCHEDULED', 'TIMED');
                """,
                (match_ids,),
            )
            open_ids = {row["match_id"] for row in cur.fetchall()}

            missing = set(match_ids) - open_ids
            if missing:
                raise BettingError(f"Fixture(s) {sorted(missing)} are not open for a jackpot (already live/finished, or unknown).")

            cur.execute(
                """
                INSERT INTO jackpots (name, stake_amount, opens_at, closes_at)
                VALUES (%s, %s, %s, %s)
                RETURNING *;
                """,
                (name, Decimal(str(stake_amount)), opens_at, closes_at),
            )
            jackpot = cur.fetchone()

            for sequence, match_id in enumerate(match_ids, start=1):
                cur.execute(
                    """
                    INSERT INTO jackpot_fixtures (jackpot_id, match_id, sequence)
                    VALUES (%s, %s, %s);
                    """,
                    (jackpot["id"], match_id, sequence),
                )

            for tier in tiers:
                cur.execute(
                    """
                    INSERT INTO jackpot_tiers (jackpot_id, min_correct, payout_multiplier)
                    VALUES (%s, %s, %s);
                    """,
                    (jackpot["id"], int(tier["min_correct"]), Decimal(str(tier["payout_multiplier"]))),
                )

        conn.commit()

    return jackpot


def settle_jackpot_entries(jackpot_id):
    """
    Settle every PENDING entry on a jackpot, once every one of its fixtures
    has finished. correct_count = picks matching fixtures.winner; payout =
    stake * the highest tier's multiplier whose min_correct the entry meets
    (0 if none). Winning entries are paid into the wallet. Returns a summary.
    """

    with get_connection() as conn:

        with conn.cursor() as cur:

            cur.execute("SELECT * FROM jackpots WHERE id = %s FOR UPDATE;", (jackpot_id,))
            jackpot = cur.fetchone()

            if jackpot is None:
                raise BettingError("Jackpot not found.")

            if jackpot["status"] == "SETTLED":
                raise BettingError("This jackpot has already been settled.")

            cur.execute(
                """
                SELECT jf.match_id, f.status, f.winner
                FROM jackpot_fixtures jf
                JOIN fixtures f ON f.match_id = jf.match_id
                WHERE jf.jackpot_id = %s;
                """,
                (jackpot_id,),
            )
            fixtures = cur.fetchall()

            unfinished = [row["match_id"] for row in fixtures if row["status"] != "FINISHED" or not row["winner"]]
            if unfinished:
                raise BettingError(f"Fixture(s) {unfinished} haven't finished yet.")

            winners = {row["match_id"]: row["winner"] for row in fixtures}

            cur.execute(
                """
                SELECT * FROM jackpot_tiers
                WHERE jackpot_id = %s
                ORDER BY min_correct DESC;
                """,
                (jackpot_id,),
            )
            tiers = cur.fetchall()

            cur.execute(
                "SELECT * FROM jackpot_entries WHERE jackpot_id = %s AND status = 'PENDING';",
                (jackpot_id,),
            )
            entries = cur.fetchall()

            settled = 0
            paid_out = Decimal("0")

            for entry in entries:

                cur.execute(
                    "SELECT match_id, pick FROM jackpot_picks WHERE entry_id = %s;",
                    (entry["id"],),
                )
                picks = cur.fetchall()

                correct_count = sum(1 for pick in picks if winners.get(pick["match_id"]) == pick["pick"])

                multiplier = next(
                    (Decimal(tier["payout_multiplier"]) for tier in tiers if correct_count >= tier["min_correct"]),
                    Decimal("0"),
                )
                payout = (Decimal(entry["stake"]) * multiplier).quantize(TWO_PLACES, rounding=ROUND_HALF_UP)

                if payout > 0:
                    _apply_wallet_delta(
                        cur, entry["user_id"], payout, "JACKPOT_PAYOUT",
                        reference=f"jackpot_entry:{entry['id']}",
                        description=f"Jackpot payout — {correct_count} correct, '{jackpot['name']}'",
                    )
                    paid_out += payout

                cur.execute(
                    """
                    UPDATE jackpot_entries
                    SET status = 'SETTLED', correct_count = %s, payout = %s, settled_at = NOW()
                    WHERE id = %s;
                    """,
                    (correct_count, payout, entry["id"]),
                )

                settled += 1

            cur.execute("UPDATE jackpots SET status = 'SETTLED' WHERE id = %s;", (jackpot_id,))

        conn.commit()

    logger.info(
        "Settled jackpot %s: %d entries, %.2f paid out.",
        jackpot_id, settled, paid_out,
    )

    return {"jackpot_id": jackpot_id, "entries_settled": settled, "paid_out": paid_out}


def close_expired_jackpots():
    """
    Flip OPEN -> CLOSED for any jackpot past its closes_at, or whose
    earliest fixture has already kicked off. place_jackpot_entry() already
    refuses these on its own (the authoritative check — this function is
    not what keeps a late entry from being accepted), but without this a
    jackpot stays listed as OPEN in GET /betting/jackpots right up until
    someone actually tries to enter it and gets rejected. Returns the list
    of jackpot ids closed.
    """

    with get_connection() as conn:

        with conn.cursor() as cur:

            cur.execute(
                """
                UPDATE jackpots j
                SET status = 'CLOSED'
                WHERE j.status = 'OPEN'
                  AND (
                      (j.closes_at IS NOT NULL AND j.closes_at <= NOW())
                      OR EXISTS (
                          SELECT 1
                          FROM jackpot_fixtures jf
                          JOIN fixtures f ON f.match_id = jf.match_id
                          WHERE jf.jackpot_id = j.id
                            AND f.status NOT IN ('SCHEDULED', 'TIMED')
                      )
                  )
                RETURNING j.id;
                """
            )

            closed = [row["id"] for row in cur.fetchall()]

        conn.commit()

    return closed


def get_jackpots_ready_to_settle():
    """Jackpots whose fixtures have all finished but haven't been settled yet
    — what the scheduler polls instead of guessing a fixed delay."""

    with get_connection() as conn:

        with conn.cursor() as cur:

            cur.execute(
                """
                SELECT j.id
                FROM jackpots j
                WHERE j.status != 'SETTLED'
                  AND NOT EXISTS (
                      SELECT 1
                      FROM jackpot_fixtures jf
                      JOIN fixtures f ON f.match_id = jf.match_id
                      WHERE jf.jackpot_id = j.id
                        AND (f.status != 'FINISHED' OR f.winner IS NULL)
                  )
                  AND EXISTS (
                      SELECT 1 FROM jackpot_fixtures jf WHERE jf.jackpot_id = j.id
                  );
                """
            )

            return [row["id"] for row in cur.fetchall()]


def get_active_jackpots():

    with get_connection() as conn:

        with conn.cursor() as cur:

            cur.execute(
                """
                SELECT * FROM jackpots
                WHERE status = 'OPEN'
                ORDER BY closes_at ASC NULLS LAST;
                """
            )

            jackpots = cur.fetchall()

            for jackpot in jackpots:
                cur.execute(
                    """
                    SELECT jf.match_id, jf.sequence, f.home_team, f.away_team, f.kickoff
                    FROM jackpot_fixtures jf
                    JOIN fixtures f ON f.match_id = jf.match_id
                    WHERE jf.jackpot_id = %s
                    ORDER BY jf.sequence ASC;
                    """,
                    (jackpot["id"],),
                )
                jackpot["fixtures"] = cur.fetchall()

    return jackpots


def place_jackpot_entry(user_id, jackpot_id, picks):
    """picks: dict of {match_id: "HOME"|"DRAW"|"AWAY"} covering every fixture."""

    with get_connection() as conn:

        with conn.cursor() as cur:

            cur.execute("SELECT * FROM jackpots WHERE id = %s FOR UPDATE;", (jackpot_id,))
            jackpot = cur.fetchone()

            if jackpot is None:
                raise BettingError("Jackpot not found.")

            if jackpot["status"] != "OPEN":
                raise BettingError("This jackpot is no longer accepting entries.")

            if jackpot["closes_at"] is not None:
                cur.execute("SELECT NOW() > %s AS past_close;", (jackpot["closes_at"],))
                if cur.fetchone()["past_close"]:
                    raise BettingError("Entries for this jackpot have closed.")

            cur.execute(
                """
                SELECT jf.match_id, f.status
                FROM jackpot_fixtures jf
                JOIN fixtures f ON f.match_id = jf.match_id
                WHERE jf.jackpot_id = %s;
                """,
                (jackpot_id,),
            )
            fixture_rows = cur.fetchall()
            required = {row["match_id"] for row in fixture_rows}

            # Belt-and-braces on top of closes_at: even an open-ended
            # jackpot (no closes_at set) must never accept a pick on a
            # fixture that has already kicked off or finished.
            started = [row["match_id"] for row in fixture_rows if row["status"] not in ("SCHEDULED", "TIMED")]
            if started:
                raise BettingError(f"Fixture(s) {sorted(started)} have already started — this jackpot can no longer be entered.")

            if set(picks.keys()) != required:
                raise BettingError("A pick is required for every jackpot fixture, no more and no fewer.")

            for pick in picks.values():
                if pick not in ("HOME", "DRAW", "AWAY"):
                    raise BettingError("Picks must be HOME, DRAW or AWAY.")

            stake = Decimal(jackpot["stake_amount"])

            _apply_wallet_delta(
                cur, user_id, -stake, "JACKPOT_STAKE",
                reference=f"jackpot:{jackpot_id}",
                description=f"Entry for jackpot '{jackpot['name']}'",
            )

            cur.execute(
                """
                INSERT INTO jackpot_entries (jackpot_id, user_id, stake)
                VALUES (%s, %s, %s)
                RETURNING *;
                """,
                (jackpot_id, user_id, stake),
            )
            entry = cur.fetchone()

            for match_id, pick in picks.items():
                cur.execute(
                    """
                    INSERT INTO jackpot_picks (entry_id, match_id, pick)
                    VALUES (%s, %s, %s);
                    """,
                    (entry["id"], match_id, pick),
                )

        conn.commit()

    return entry


def get_user_jackpot_entries(user_id):

    with get_connection() as conn:

        with conn.cursor() as cur:

            cur.execute(
                """
                SELECT je.*, j.name AS jackpot_name
                FROM jackpot_entries je
                JOIN jackpots j ON j.id = je.jackpot_id
                WHERE je.user_id = %s
                ORDER BY je.placed_at DESC;
                """,
                (user_id,),
            )

            return cur.fetchall()
