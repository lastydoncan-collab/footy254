"""
Betting API: odds, wallet, single/multi bet slips and jackpots.

Placing bets only requires a signed-in account (betting is the core free
product, unlike /predictions which is gated behind an active subscription).
Generating odds and settling fixtures are administrator-only operations —
in production these are triggered by the fixture-sync scheduler, not a
person, but an explicit endpoint makes both easy to trigger by hand and to
test.
"""

from fastapi import APIRouter, Depends, HTTPException, WebSocket, WebSocketDisconnect

from database.betting_repository import (
    BettingError,
    InsufficientFundsError,
    create_jackpot,
    credit_wallet,
    generate_odds_for_fixture,
    get_active_jackpots,
    get_bet_slip,
    get_fixture_exposure,
    get_odds_board,
    get_odds_history,
    get_or_create_wallet,
    get_user_bet_slips,
    get_user_jackpot_entries,
    get_volume_report,
    get_wallet_transactions,
    place_jackpot_entry,
    place_multi_bet,
    place_single_bet,
    settle_fixture_bets,
    settle_jackpot_entries,
    shade_odds_for_exposure,
)
from schemas.betting import (
    BetSlipListResponse,
    BetSlipResponse,
    JackpotCreateRequest,
    JackpotEntryRequest,
    JackpotEntryResponse,
    JackpotResponse,
    OddsBoardEntry,
    OddsResponse,
    PlaceMultiBetRequest,
    PlaceSingleBetRequest,
    WalletResponse,
    WalletTransactionListResponse,
)
from security.dependencies import get_current_user, require_admin
from services.cache import ttl_cache
from services.odds_hub import odds_hub

router = APIRouter(
    prefix="/betting",
    tags=["Betting"],
)

# Odds board is the single hottest read in this module — every visitor's
# home screen hits it, and it changes far less often than it's read, so a
# short cache takes real load off the pool without visibly staling prices
# (the reshade_odds scheduler job runs every 20s; this cache is shorter).
_cached_odds_board = ttl_cache(2.0)(get_odds_board)


def _handle(fn, *args, **kwargs):
    """Translate repository-level domain errors into HTTP responses."""

    try:
        return fn(*args, **kwargs)
    except InsufficientFundsError as exc:
        raise HTTPException(status_code=402, detail=str(exc)) from exc
    except BettingError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


# ==========================================================
# ODDS
# ==========================================================

@router.get("/odds", response_model=list[OddsBoardEntry])
def odds_board(
    current_user=Depends(get_current_user),
):
    return _cached_odds_board()


@router.post("/odds/{match_id}/generate", response_model=OddsResponse)
def generate_odds(
    match_id: int,
    current_user=Depends(require_admin),
):
    odds = generate_odds_for_fixture(match_id)

    if odds is None:
        raise HTTPException(
            status_code=404,
            detail="No prediction exists yet for this fixture.",
        )

    _cached_odds_board.cache_clear()
    odds_hub.publish({"type": "odds_update", "reason": "MANUAL_GENERATE", **odds})

    return odds


@router.post("/odds/{match_id}/shade", response_model=OddsResponse)
def shade_odds(
    match_id: int,
    current_user=Depends(require_admin),
):
    """Re-price against current pending stake. See shade_odds_for_exposure's
    docstring for the (bounded, transparent) formula. The scheduler calls
    this automatically every 20s (services/scheduler.py:reshade_odds_job);
    this endpoint exists for an admin to force an immediate re-price."""

    odds = shade_odds_for_exposure(match_id)

    if odds is None:
        raise HTTPException(status_code=404, detail="No odds exist yet for this fixture.")

    _cached_odds_board.cache_clear()
    odds_hub.publish({"type": "odds_update", "reason": odds["source"], **odds})

    return odds


@router.get("/odds/{match_id}/history")
def odds_history(
    match_id: int,
    current_user=Depends(get_current_user),
):
    return {"match_id": match_id, "history": get_odds_history(match_id)}


@router.websocket("/ws/odds")
async def odds_stream(websocket: WebSocket):
    """
    Live odds feed: every price change (new fixture priced, exposure
    shading, manual admin adjustment) is pushed here the moment it happens,
    instead of clients polling GET /betting/odds. Payload shape matches
    OddsResponse plus a "type" and "reason" field, e.g.:
        {"type": "odds_update", "reason": "EXPOSURE_SHADE", "match_id": 123, ...}
    No auth dependency here deliberately — odds are public read data (same
    as GET /betting/odds, which only requires login because every other
    route in this router does, not because prices are sensitive).
    """

    await odds_hub.connect(websocket)

    try:
        while True:
            # This socket is push-only; we still need to await something so
            # a client disconnect raises promptly instead of leaking a dead
            # connection until the next failed send.
            await websocket.receive_text()
    except WebSocketDisconnect:
        pass
    finally:
        odds_hub.disconnect(websocket)


# ==========================================================
# WALLET
# ==========================================================

@router.get("/wallet", response_model=WalletResponse)
def my_wallet(
    current_user=Depends(get_current_user),
):
    return get_or_create_wallet(current_user["id"])


@router.get("/wallet/transactions", response_model=WalletTransactionListResponse)
def my_wallet_transactions(
    current_user=Depends(get_current_user),
):
    transactions = get_wallet_transactions(current_user["id"])

    return {
        "count": len(transactions),
        "transactions": transactions,
    }


@router.post("/wallet/dev-topup", response_model=WalletResponse)
def dev_topup(
    amount: float,
    current_user=Depends(require_admin),
):
    """
    Manual balance credit for development/testing only. Real deposits run
    through M-Pesa (api/mpesa.py) / card payments (api/card_payments.py);
    this route deliberately stays admin-gated so it can never become a
    free-money endpoint in production.
    """

    new_balance = credit_wallet(
        current_user["id"],
        amount,
        "DEPOSIT",
        description="Manual development top-up.",
    )

    wallet = get_or_create_wallet(current_user["id"])
    wallet["balance"] = new_balance

    return wallet


# ==========================================================
# BET SLIPS
# ==========================================================

@router.post("/slips/single", response_model=BetSlipResponse)
def bet_single(
    payload: PlaceSingleBetRequest,
    current_user=Depends(get_current_user),
):
    return _handle(
        place_single_bet,
        current_user["id"],
        payload.match_id,
        payload.pick,
        payload.stake,
        payload.idempotency_key,
    )


@router.post("/slips/multi", response_model=BetSlipResponse)
def bet_multi(
    payload: PlaceMultiBetRequest,
    current_user=Depends(get_current_user),
):
    return _handle(
        place_multi_bet,
        current_user["id"],
        [leg.model_dump() for leg in payload.legs],
        payload.stake,
        payload.idempotency_key,
    )


@router.get("/slips", response_model=BetSlipListResponse)
def my_bet_slips(
    status: str | None = None,
    current_user=Depends(get_current_user),
):
    slips = get_user_bet_slips(current_user["id"], status=status)

    return {
        "count": len(slips),
        "bet_slips": slips,
    }


@router.get("/slips/{slip_id}", response_model=BetSlipResponse)
def bet_slip_detail(
    slip_id: int,
    current_user=Depends(get_current_user),
):
    slip = get_bet_slip(slip_id, current_user["id"])

    if slip is None:
        raise HTTPException(status_code=404, detail="Bet slip not found.")

    return slip


@router.post("/fixtures/{match_id}/settle")
def settle_fixture(
    match_id: int,
    current_user=Depends(require_admin),
):
    """The scheduler settles finished fixtures automatically within a
    minute (services/scheduler.py:settle_finished_fixtures_job); this is
    for forcing it by hand."""

    result = _handle(settle_fixture_bets, match_id)
    _cached_odds_board.cache_clear()
    return result


# ==========================================================
# RISK DESK  (admin only — paper-money exposure/volume, not a live trading desk)
# ==========================================================

@router.get("/admin/exposure")
def exposure_report(
    match_id: int | None = None,
    current_user=Depends(require_admin),
):
    """
    Outstanding liability per (fixture, pick) across pending bet slips.
    See get_fixture_exposure's docstring for what "payout_if_all_win" means
    for multi/jackpot legs — it's a worst-case upper bound, not a
    probability-weighted estimate.
    """

    return {"exposure": get_fixture_exposure(match_id)}


@router.get("/admin/volume")
def volume_report(
    hours: int = 24,
    current_user=Depends(require_admin),
):
    if hours < 1 or hours > 24 * 90:
        raise HTTPException(status_code=400, detail="hours must be between 1 and 2160 (90 days).")

    return get_volume_report(hours)


# ==========================================================
# JACKPOTS
# ==========================================================

@router.get("/jackpots", response_model=list[JackpotResponse])
def active_jackpots(
    current_user=Depends(get_current_user),
):
    return get_active_jackpots()


@router.post("/jackpots", response_model=JackpotResponse)
def create_jackpot_route(
    payload: JackpotCreateRequest,
    current_user=Depends(require_admin),
):
    return _handle(
        create_jackpot,
        payload.name,
        payload.stake_amount,
        payload.match_ids,
        [tier.model_dump() for tier in payload.tiers],
        payload.opens_at,
        payload.closes_at,
    )


@router.post("/jackpots/{jackpot_id}/settle")
def settle_jackpot_route(
    jackpot_id: int,
    current_user=Depends(require_admin),
):
    """The scheduler settles jackpots automatically once every listed
    fixture finishes (services/scheduler.py:settle_jackpots_job); this is
    for forcing it by hand."""

    return _handle(settle_jackpot_entries, jackpot_id)


@router.post("/jackpots/{jackpot_id}/enter", response_model=JackpotEntryResponse)
def enter_jackpot(
    jackpot_id: int,
    payload: JackpotEntryRequest,
    current_user=Depends(get_current_user),
):
    return _handle(
        place_jackpot_entry,
        current_user["id"],
        jackpot_id,
        payload.picks,
    )


@router.get("/jackpots/entries/mine", response_model=list[JackpotEntryResponse])
def my_jackpot_entries(
    current_user=Depends(get_current_user),
):
    return get_user_jackpot_entries(current_user["id"])
