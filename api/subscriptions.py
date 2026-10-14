"""
FOOTY254 Subscription Router
"""

import logging

from fastapi import APIRouter, Depends, HTTPException, Request

from security.dependencies import get_current_user
from security.rate_limiter import limiter

from config.subscription_plans import (
    list_plans,
    get_plan,
)

from schemas.subscription import (
    SubscriptionCreate,
    SubscriptionResponse,
    SubscriptionStatus,
)

from services.subscription_service import (
    subscription_service,
)

from fastapi import HTTPException

from services.mpesa_service import (
    mpesa_service,
)

from config.subscription_plans import (
    get_plan,
)

router = APIRouter(
    prefix="/subscriptions",
    tags=["Subscriptions"],
)

logger = logging.getLogger(__name__)

# ==========================================================
# AVAILABLE PLANS
# ==========================================================

@router.get("/plans")
async def get_available_plans():

    return {
        "plans": list_plans()
    }


# ==========================================================
# MY SUBSCRIPTION
# ==========================================================

@router.get(
    "/me",
    response_model=SubscriptionStatus,
)
async def my_subscription(

    current_user=Depends(get_current_user),

):

    subscription = subscription_service.get_user_subscription(
        current_user["id"]
    )

    if subscription is None:

        return SubscriptionStatus(

            is_active=False,

            plan="FREE",

            status="FREE",

            expires_at=None,

        )

    return SubscriptionStatus(

        is_active=subscription_service.has_active_subscription(
            current_user["id"]
        ),

        plan=subscription["plan"],

        status=subscription["status"],

        expires_at=subscription["expires_at"],

    )


# ==========================================================
# CREATE CHECKOUT
# ==========================================================

@router.post(
    "/checkout",
)
@limiter.limit("5/minute")
async def create_subscription_checkout(

    request: Request,

    body: SubscriptionCreate,

    current_user=Depends(get_current_user),

):

    plan_id = body.plan.upper().strip()
    plan = get_plan(plan_id)

    if plan is None:

        raise HTTPException(

            status_code=400,

            detail="Invalid subscription plan.",

        )

    payment_method = body.payment_method.upper().strip()

    if payment_method != "MPESA":
        raise HTTPException(
            status_code=400,
            detail="M-Pesa is the only payment method currently available.",
        )

    pending = subscription_service.get_recent_pending_checkout(current_user["id"])
    if pending:
        # Returning the existing identifier lets the UI resume polling after
        # a refresh without charging the customer twice.
        return {
            "success": True,
            "subscription_id": pending["subscription_id"],
            "checkout_request_id": pending["checkout_request_id"],
            "plan": pending["plan"],
            "amount": plan["price"],
            "currency": plan["currency"],
            "customer_message": "An M-Pesa prompt is already awaiting confirmation.",
        }

    subscription_id = subscription_service.create_subscription(

        user_id=current_user["id"],

        plan=plan_id,

        payment_method=payment_method,

        # Prices and currency must come from the server-side plan catalogue,
        # never from a browser or mobile client.
        amount=plan["price"],

        currency=plan["currency"],

    )

    account_reference = (
        f"FOOTY254-{subscription_id}"
    )

    try:

        stk_response = mpesa_service.stk_push(

            phone_number=body.phone_number,

            # Must match the server-side plan price used to create the
            # subscription record above. Using the client-supplied amount
            # here would charge the wrong amount and cause the M-Pesa
            # callback's amount-verification check to reject the
            # (legitimate) payment.
            amount=plan["price"],

            account_reference=account_reference,

            transaction_desc=f"{plan_id} Subscription",

        )

    except Exception:

        # Without this, a Safaricom outage / network error / bad
        # credentials leaves the subscription stuck PENDING forever —
        # nothing else in the app ever revisits a PENDING row that never
        # got a CheckoutRequestID (the stale-subscription job only expires
        # ACTIVE ones), and the user sees a bare 500 with no way to retry.

        logger.exception(
            "STK push failed for subscription %s", subscription_id
        )

        subscription_service.mark_payment_failed(subscription_id)

        raise HTTPException(
            status_code=502,
            detail=(
                "We couldn't reach M-Pesa to start this payment. "
                "Please try again in a moment."
            ),
        )

    merchant_request_id = stk_response.get(
        "MerchantRequestID"
    )

    checkout_request_id = stk_response.get(
        "CheckoutRequestID"
    )

    if not checkout_request_id:

        # Daraja returned 200 but without the ID we need to ever match a
        # callback back to this subscription — treat it as a failure now
        # rather than leaving the row PENDING indefinitely.

        logger.error(
            "STK push for subscription %s returned no CheckoutRequestID: %s",
            subscription_id,
            stk_response,
        )

        subscription_service.mark_payment_failed(subscription_id)

        raise HTTPException(
            status_code=502,
            detail="M-Pesa did not confirm the payment request. Please try again.",
        )

    subscription_service.update_checkout_request(

        subscription_id=subscription_id,

        merchant_request_id=merchant_request_id,

        checkout_request_id=checkout_request_id,

    )

    return {
        "success": True,
        "subscription_id": subscription_id,
        "merchant_request_id": merchant_request_id,
        "checkout_request_id": checkout_request_id,
        "plan": plan_id,
        "amount": plan["price"],
        "currency": plan["currency"],
        "customer_message": stk_response.get("CustomerMessage"),
        "response_description": stk_response.get("ResponseDescription"),
    }


# ==========================================================
# SUBSCRIPTION STATUS
# ==========================================================

@router.get(
    "/status/{transaction_reference}",
    response_model=SubscriptionResponse,
)
async def subscription_status(

    transaction_reference: str,

    current_user=Depends(get_current_user),

):

    subscription = (
        subscription_service.get_subscription_by_reference(
            transaction_reference
        )
    )

    if subscription is None:

        raise HTTPException(

            status_code=404,

            detail="Subscription not found.",

        )

    if subscription["user_id"] != current_user["id"]:

        raise HTTPException(

            status_code=403,

            detail="Not allowed.",

        )

    return SubscriptionResponse(**subscription)


# ==========================================================
# CHECKOUT STATUS (USED DURING STK PUSH)
# ==========================================================

@router.get(
    "/checkout-status/{checkout_request_id}",
)
async def checkout_status(

    checkout_request_id: str,

    current_user=Depends(get_current_user),

):

    subscription = (
        subscription_service
        .get_subscription_by_checkout_request(
            checkout_request_id
        )
    )

    if subscription is None:

        raise HTTPException(

            status_code=404,

            detail="Subscription not found.",

        )

    if subscription["user_id"] != current_user["id"]:

        raise HTTPException(

            status_code=403,

            detail="Not allowed.",

        )

    return {

        "subscription_id":
            subscription["subscription_id"],

        "status":
            subscription["status"],

        "plan":
            subscription["plan"],

        "expires_at":
            subscription["expires_at"],

        "transaction_reference":
            subscription["transaction_reference"],

    }

# ==========================================================
# CANCEL SUBSCRIPTION
# ==========================================================

@router.post("/cancel")
async def cancel_subscription(

    current_user=Depends(get_current_user),

):

    subscription_service.deactivate_subscription(
        current_user["id"]
    )

    return {

        "success": True,

        "message": "Subscription cancelled successfully.",

    }
