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

    if subscription is None:

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
