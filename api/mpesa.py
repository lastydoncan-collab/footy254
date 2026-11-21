"""
FOOTY254 M-Pesa Router
"""

import hmac
import logging
from decimal import Decimal, InvalidOperation

from fastapi import APIRouter
from fastapi import Request
from fastapi.responses import JSONResponse
from fastapi import HTTPException

from config.mpesa import MPESA_CALLBACK_SECRET

from database.wallet_mpesa_repository import (
    get_deposit_request_by_checkout,
    get_withdrawal_request_by_conversation,
    mark_deposit_completed,
    mark_deposit_failed,
    mark_withdrawal_completed,
    mark_withdrawal_failed,
)

from services.mpesa_service import (
    mpesa_service,
)

from services.subscription_service import (
    subscription_service,
)

router = APIRouter(

    prefix="/mpesa",

    tags=["M-Pesa"],

)

logger = logging.getLogger(__name__)


# ==========================================================
# MPESA CALLBACK
# ==========================================================
#
# The path segment `secret` is the unguessable token configured as
# MPESA_CALLBACK_SECRET / baked into MPESA_CALLBACK_URL. Daraja callbacks
# aren't signed, and the CheckoutRequestID this depends on is already known
# to the browser that initiated checkout — so without this check, anyone
# could forge a "payment succeeded" callback for their own subscription.

def _handle_deposit_callback(deposit_request, callback):
    """
    The betting-wallet-deposit half of mpesa_callback()'s dispatch, mirroring
    the subscription handling in that function step for step (duplicate
    check, failure, amount-mismatch check, success) but crediting a wallet
    (mark_deposit_completed) instead of activating a subscription.
    """

    if deposit_request["status"] == "COMPLETED":
        logger.info("Duplicate deposit callback ignored.")
        return JSONResponse(
            status_code=200,
            content={"ResultCode": 0, "ResultDesc": "Accepted"},
        )

    if callback["result_code"] != 0:
        logger.warning("Deposit failed: %s", callback["result_desc"])
        mark_deposit_failed(deposit_request["id"], reason=callback["result_desc"])
        return JSONResponse(
            status_code=200,
            content={"ResultCode": 0, "ResultDesc": "Accepted"},
        )

    metadata = callback["metadata"]
    transaction_reference = metadata.get("MpesaReceiptNumber")

    if not transaction_reference:
        logger.warning("Successful deposit callback had no receipt number.")
        mark_deposit_failed(deposit_request["id"], reason="No M-Pesa receipt number in callback.")
        return JSONResponse(
            status_code=200,
            content={"ResultCode": 0, "ResultDesc": "Accepted"},
        )

    try:
        paid_amount = Decimal(str(metadata["Amount"]))
    except (KeyError, InvalidOperation):
        logger.warning("Successful deposit callback had an invalid amount.")
        mark_deposit_failed(deposit_request["id"], reason="Invalid amount in callback.")
        return JSONResponse(
            status_code=200,
            content={"ResultCode": 0, "ResultDesc": "Accepted"},
        )

    # Compared against gross_amount, not net_amount: STK push charges the
    # user the full amount they asked to deposit — tax is deducted on OUR
    # side before crediting the wallet (mark_deposit_completed), it was
    # never part of what M-Pesa itself charged them.
    if paid_amount != Decimal(str(deposit_request["gross_amount"])):
        logger.warning(
            "Deposit amount mismatch for request %s: received %s.",
            deposit_request["id"],
            paid_amount,
        )
        mark_deposit_failed(deposit_request["id"], reason="Paid amount did not match requested amount.")
        return JSONResponse(
            status_code=200,
            content={"ResultCode": 0, "ResultDesc": "Accepted"},
        )

    mark_deposit_completed(deposit_request["id"], mpesa_receipt=transaction_reference)

    logger.info(
        "Wallet deposit request %s completed (receipt %s).",
        deposit_request["id"],
        transaction_reference,
    )

    return JSONResponse(
        status_code=200,
        content={"ResultCode": 0, "ResultDesc": "Accepted"},
    )


def _handle_withdrawal_result(withdrawal_request, result):
    """
    The async B2C "Result" callback's dispatch — mirrors
    _handle_deposit_callback() above (duplicate check, failure, success) but
    for the opposite money direction: a withdrawal whose payout either
    landed (mark_withdrawal_completed) or didn't (mark_withdrawal_failed,
    which refunds the gross amount debited up front at request time).

    Unlike a deposit callback, there's no "amount mismatch" check here —
    Daraja's ResultParameters for a successful B2C payment report the
    TransactionAmount, but that will always equal what we ourselves sent as
    the B2C "Amount" (net_amount); there's no customer-typed amount it could
    disagree with the way a deposit's callback amount can disagree with what
    the user asked to deposit.
    """

    if withdrawal_request["status"] in ("COMPLETED", "FAILED"):
        logger.info(
            "Duplicate B2C result callback ignored (request already %s).",
            withdrawal_request["status"],
        )
        return JSONResponse(
            status_code=200,
            content={"ResultCode": 0, "ResultDesc": "Accepted"},
        )

    if result["result_code"] != 0:
        logger.warning(
            "B2C withdrawal failed for request %s: %s",
            withdrawal_request["id"],
            result["result_desc"],
        )
        mark_withdrawal_failed(
            withdrawal_request["id"],
            reason=result["result_desc"] or "B2C payment failed.",
        )
        return JSONResponse(
            status_code=200,
            content={"ResultCode": 0, "ResultDesc": "Accepted"},
        )

    transaction_id = result["transaction_id"]

    if not transaction_id:
        logger.warning("Successful B2C result callback had no TransactionID.")
        mark_withdrawal_failed(
            withdrawal_request["id"],
            reason="No M-Pesa transaction ID in B2C result.",
        )
        return JSONResponse(
            status_code=200,
            content={"ResultCode": 0, "ResultDesc": "Accepted"},
        )

    mark_withdrawal_completed(withdrawal_request["id"], mpesa_receipt=transaction_id)

    logger.info(
        "Wallet withdrawal request %s completed (receipt %s).",
        withdrawal_request["id"],
        transaction_id,
    )

    return JSONResponse(
        status_code=200,
        content={"ResultCode": 0, "ResultDesc": "Accepted"},
    )


@router.post("/callback/b2c/result/{secret}")
async def mpesa_b2c_result(
    request: Request,
    secret: str,
):
    """
    Daraja's async B2C "ResultURL" — the actual outcome of a withdrawal
    payout (mpesa_service.b2c_payment() in api/betting.py only gets Daraja's
    synchronous "accepted/queued" acknowledgement, not whether the money
    actually landed). Same unguessable-secret path-based auth as
    mpesa_callback() above, and for the same reason: B2C result callbacks
    aren't signed either, and ConversationID is already known to whatever
    could try to forge one.
    """

    if not MPESA_CALLBACK_SECRET or not hmac.compare_digest(
        secret, MPESA_CALLBACK_SECRET
    ):
        logger.warning("Rejected M-Pesa B2C result callback with an invalid callback secret.")
        raise HTTPException(status_code=404)

    try:
        payload = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid callback payload.")

    logger.info("Received M-Pesa B2C result callback.")

    result = mpesa_service.parse_b2c_result(payload)

    conversation_id = result["conversation_id"]

    if not conversation_id:
        logger.warning("M-Pesa B2C result callback did not contain a ConversationID.")
        return JSONResponse(
            status_code=200,
            content={"ResultCode": 0, "ResultDesc": "Accepted"},
        )

    withdrawal_request = get_withdrawal_request_by_conversation(conversation_id)

    if withdrawal_request is None:
        logger.warning("ConversationID %s not found.", conversation_id)
        return JSONResponse(
            status_code=200,
            content={"ResultCode": 0, "ResultDesc": "Accepted"},
        )

    return _handle_withdrawal_result(withdrawal_request, result)


@router.post("/callback/b2c/timeout/{secret}")
async def mpesa_b2c_timeout(
    request: Request,
    secret: str,
):
    """
    Daraja's "QueueTimeOutURL" — fires instead of the ResultURL above if
    Safaricom gives up waiting on its own B2C processing. Treated exactly
    like a failed result (refund the withdrawal via mark_withdrawal_failed),
    since from this app's point of view a payout that will never resolve is
    operationally no different from one that explicitly failed — the user's
    money needs to go back into their wallet either way.
    """

    if not MPESA_CALLBACK_SECRET or not hmac.compare_digest(
        secret, MPESA_CALLBACK_SECRET
    ):
        logger.warning("Rejected M-Pesa B2C timeout callback with an invalid callback secret.")
        raise HTTPException(status_code=404)

    try:
        payload = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid callback payload.")

    logger.info("Received M-Pesa B2C timeout callback.")

    result = mpesa_service.parse_b2c_timeout(payload)

    conversation_id = result["conversation_id"]

    if not conversation_id:
        logger.warning("M-Pesa B2C timeout callback did not contain a ConversationID.")
        return JSONResponse(
            status_code=200,
            content={"ResultCode": 0, "ResultDesc": "Accepted"},
        )

    withdrawal_request = get_withdrawal_request_by_conversation(conversation_id)

    if withdrawal_request is None:
        logger.warning("ConversationID %s not found (timeout).", conversation_id)
        return JSONResponse(
            status_code=200,
            content={"ResultCode": 0, "ResultDesc": "Accepted"},
        )

    if withdrawal_request["status"] in ("COMPLETED", "FAILED"):
        logger.info(
            "Duplicate B2C timeout callback ignored (request already %s).",
            withdrawal_request["status"],
        )
        return JSONResponse(
            status_code=200,
            content={"ResultCode": 0, "ResultDesc": "Accepted"},
        )

    mark_withdrawal_failed(
        withdrawal_request["id"],
        reason=result["result_desc"] or "M-Pesa B2C request timed out.",
    )

    return JSONResponse(
        status_code=200,
        content={"ResultCode": 0, "ResultDesc": "Accepted"},
    )


@router.post("/callback/{secret}")
async def mpesa_callback(
    request: Request,
    secret: str,
):

    if not MPESA_CALLBACK_SECRET or not hmac.compare_digest(
        secret, MPESA_CALLBACK_SECRET
    ):
        logger.warning(
            "Rejected M-Pesa callback with an invalid callback secret."
        )
        # 404, not 401/403: don't confirm to a prober that this path exists
        # and merely has the wrong secret.
        raise HTTPException(status_code=404)

    try:
        payload = await request.json()

    except Exception:

        raise HTTPException(

            status_code=400,

            detail="Invalid callback payload.",

        )

    logger.info(

        "Received M-Pesa callback."

    )

    callback = mpesa_service.parse_callback(
        payload
    )

    checkout_request_id = callback[
        "checkout_request_id"
    ]

    if not checkout_request_id:
        logger.warning("M-Pesa callback did not contain a CheckoutRequestID.")
        return JSONResponse(
            status_code=200,
            content={"ResultCode": 0, "ResultDesc": "Accepted"},
        )

    subscription = (
        subscription_service
        .get_subscription_by_checkout_request(
            checkout_request_id
        )
    )

    # One callback URL, one OAuth/STK push implementation (services.mpesa_service)
    # shared by subscriptions AND betting wallet deposits — Daraja only ever
    # gives back the CheckoutRequestID it was sent, so that's what decides
    # which table this callback belongs to.
    if subscription is None:

        deposit_request = get_deposit_request_by_checkout(checkout_request_id)

        if deposit_request is not None:
            return _handle_deposit_callback(deposit_request, callback)

        logger.warning(

            "CheckoutRequestID %s not found.",

            checkout_request_id,

        )

        return JSONResponse(

            status_code=200,

            content={

                "ResultCode": 0,

                "ResultDesc": "Accepted",

            },

        )

    if subscription["status"] == "ACTIVE":

        logger.info(

            "Duplicate callback ignored."

        )

        return JSONResponse(

            status_code=200,

            content={

                "ResultCode": 0,

                "ResultDesc": "Accepted",

            },

        )

    # ---------------------------------------------
    # PAYMENT FAILED
    # ---------------------------------------------

    if callback["result_code"] != 0:

        subscription_service.mark_payment_failed(
            subscription["subscription_id"]
        )

        logger.warning(

            "Payment failed: %s",

            callback["result_desc"],

        )

        return JSONResponse(

            status_code=200,

            content={

                "ResultCode": 0,

                "ResultDesc": "Accepted",

            },

        )

    metadata = callback["metadata"]

    transaction_reference = metadata.get("MpesaReceiptNumber")

    if not transaction_reference:
        logger.warning("Successful M-Pesa callback had no receipt number.")
        subscription_service.mark_payment_failed(subscription["subscription_id"])
        return JSONResponse(
            status_code=200,
            content={"ResultCode": 0, "ResultDesc": "Accepted"},
        )

    try:
        paid_amount = Decimal(str(metadata["Amount"]))
    except (KeyError, InvalidOperation):
        logger.warning("Successful M-Pesa callback had an invalid amount.")
        subscription_service.mark_payment_failed(subscription["subscription_id"])
        return JSONResponse(
            status_code=200,
            content={"ResultCode": 0, "ResultDesc": "Accepted"},
        )

    if paid_amount != Decimal(str(subscription["amount"])):
        logger.warning(
            "Payment amount mismatch for subscription %s: received %s.",
            subscription["subscription_id"],
            paid_amount,
        )
        subscription_service.mark_payment_failed(subscription["subscription_id"])
        return JSONResponse(
            status_code=200,
            content={"ResultCode": 0, "ResultDesc": "Accepted"},
        )

    logger.info(

        "Receipt Number: %s",

        transaction_reference,

    )

    logger.info(

        "Amount: %s",

        metadata.get("Amount"),

    )

    logger.info(

        "Phone: %s",

        metadata.get("PhoneNumber"),

    )

    subscription_service.update_transaction_reference(

        subscription["subscription_id"],

        transaction_reference,

    )

    subscription_service.activate_subscription(

        subscription_id=subscription[
            "subscription_id"
        ],

        transaction_reference=transaction_reference,

        paid_amount=paid_amount,

    )

    logger.info(

        "Subscription %s activated.",

        subscription["subscription_id"],

    )

    return JSONResponse(

        status_code=200,

        content={

            "ResultCode": 0,

            "ResultDesc": "Accepted",

        },

    )
