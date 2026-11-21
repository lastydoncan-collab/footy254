"""
Betting API: odds, wallet, single/multi bet slips and jackpots.

Placing bets only requires a signed-in account (betting is the core free
product, unlike /predictions which is gated behind an active subscription).
Generating odds and settling fixtures are administrator-only operations —
in production these are triggered by the fixture-sync scheduler, not a
person, but an explicit endpoint makes both easy to trigger by hand and to
test.
"""

import logging

from fastapi import APIRouter, Depends, HTTPException, WebSocket, WebSocketDisconnect

from config.betting_finance import (
    MIN_DEPOSIT_KES,
    MIN_WITHDRAWAL_KES,
    apply_tax,
)
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
from database.wallet_mpesa_repository import (
    attach_withdrawal_conversation_id,
    create_deposit_request,
    create_withdrawal_request,
    get_deposit_request_by_checkout,
    get_recent_pending_deposit,
    get_user_mpesa_requests,
    mark_withdrawal_failed,
)
from schemas.betting import (
    BetSlipListResponse,
    BetSlipResponse,
    JackpotCreateRequest,
    JackpotEntryRequest,
    JackpotEntryResponse,
    JackpotResponse,
    MpesaDepositRequest,
    MpesaRequestResponse,
    MpesaWithdrawRequest,
    OddsBoardEntry,
    OddsResponse,
    PlaceMultiBetRequest,
    PlaceSingleBetRequest,
    WalletResponse,
    WalletTransactionListResponse,
)
from security.dependencies import get_current_user, require_admin
from services.cache import ttl_cache
from services.mpesa_service import mpesa_service
from services.odds_hub import odds_hub

logger = logging.getLogger(__name__)

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


@router.post("/wallet/mpesa/stk-push", response_model=MpesaRequestResponse)
def deposit_via_mpesa(
    body: MpesaDepositRequest,
    current_user=Depends(get_current_user),
):
    """
    Real deposit path: a genuine Safaricom Daraja STK push (sandbox), not
    the admin-only dev_topup() above. Shares the exact same M-Pesa service
    (services/mpesa_service.py) and callback endpoint (api/mpesa.py's
    mpesa_callback) that FOOTY254's premium subscriptions already use —
    there's one M-Pesa integration in this app, not two.
    """

    if body.amount < MIN_DEPOSIT_KES:
        raise HTTPException(
            status_code=400,
            detail=f"Minimum deposit is KES {MIN_DEPOSIT_KES}.",
        )

    if not mpesa_service.is_valid_phone_number(body.phone):
        raise HTTPException(status_code=400, detail="Invalid phone number.")

    existing = get_recent_pending_deposit(current_user["id"])
    if existing is not None:
        return existing

    tax_amount, net_amount = apply_tax(body.amount)

    try:
        stk_result = mpesa_service.stk_push(
            phone_number=body.phone,
            amount=body.amount,
            account_reference=f"FOOTY254-DEP-{current_user['id']}",
            transaction_desc="FOOTY254 wallet deposit",
        )
    except RuntimeError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    request = create_deposit_request(
        user_id=current_user["id"],
        phone=body.phone,
        gross_amount=body.amount,
        tax_amount=tax_amount,
        net_amount=net_amount,
        checkout_request_id=stk_result.get("CheckoutRequestID"),
        merchant_request_id=stk_result.get("MerchantRequestID"),
    )

    return request


@router.get("/wallet/mpesa/status/{checkout_request_id}", response_model=MpesaRequestResponse)
def deposit_status(
    checkout_request_id: str,
    current_user=Depends(get_current_user),
):
    """Polled by the frontend while an STK push is pending — the real
    outcome arrives asynchronously at api/mpesa.py's callback, so this
    just reflects whatever that callback has (or hasn't yet) resolved."""

    request = get_deposit_request_by_checkout(checkout_request_id)

    if request is None or request["user_id"] != current_user["id"]:
        raise HTTPException(status_code=404, detail="Deposit request not found.")

    return request


@router.post("/wallet/mpesa/withdraw", response_model=MpesaRequestResponse)
def withdraw_via_mpesa(
    body: MpesaWithdrawRequest,
    current_user=Depends(get_current_user),
):
    """
    Withdraw winnings (or any wallet balance) out to M-Pesa via a Daraja B2C
    payout. The gross amount is debited from the wallet immediately — see
    database.wallet_mpesa_repository.create_withdrawal_request's docstring
    for why — and refunded automatically if the B2C payout then fails.
    """

    if body.amount < MIN_WITHDRAWAL_KES:
        raise HTTPException(
            status_code=400,
            detail=f"Minimum withdrawal is KES {MIN_WITHDRAWAL_KES}.",
        )

    if not mpesa_service.is_valid_phone_number(body.phone):
        raise HTTPException(status_code=400, detail="Invalid phone number.")

    tax_amount, net_amount = apply_tax(body.amount)

    try:
        request = create_withdrawal_request(
            user_id=current_user["id"],
            phone=body.phone,
            gross_amount=body.amount,
            tax_amount=tax_amount,
            net_amount=net_amount,
        )
    except InsufficientFundsError as exc:
        raise HTTPException(status_code=402, detail=str(exc)) from exc

    try:
        b2c_result = mpesa_service.b2c_payment(
            phone_number=body.phone,
            amount=net_amount,
            remarks="FOOTY254 wallet withdrawal",
            occasion=f"withdrawal-{request['id']}",
        )
    except Exception as exc:
        # Deliberately broad: whatever went wrong (Daraja rejected it,
        # a network error, a config/certificate problem), the wallet was
        # already debited (create_withdrawal_request, above)
        # — if Daraja never even accepted the request, that debit has to
        # come back now, not sit there waiting for a result callback that
        # is never going to arrive.
        logger.warning("B2C payment failed to send for request %s: %s", request["id"], exc)
        mark_withdrawal_failed(request["id"], reason=str(exc))
        raise HTTPException(
            status_code=502,
            detail="Could not reach M-Pesa for this withdrawal; your balance has been restored.",
        ) from exc

    request = attach_withdrawal_conversation_id(
        request["id"],
        conversation_id=b2c_result.get("ConversationID"),
        originator_conversation_id=b2c_result.get("OriginatorConversationID"),
    )

    return request


@router.get("/wallet/mpesa/requests", response_model=list[MpesaRequestResponse])
def my_mpesa_requests(
    current_user=Depends(get_current_user),
):
    """Deposit + withdrawal history, separate from /wallet/transactions
    (which only shows completed ledger movements) — this also shows
    PENDING and FAILED attempts, useful for a user wondering "where did my
    STK prompt go" or "why didn't my withdrawal show up"."""

    return get_user_mpesa_requests(current_user["id"])


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
