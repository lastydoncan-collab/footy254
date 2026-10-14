"""Card payment endpoints (Paystack hosted checkout)."""

import json
import logging

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from config.card import card_payments_enabled
from config.subscription_plans import get_plan
from security.dependencies import get_current_user
from security.rate_limiter import limiter
from services import card_service
from services.subscription_service import subscription_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/card", tags=["Card payments"])


class CardCheckoutRequest(BaseModel):
    plan: str = Field(min_length=1, max_length=20)


@router.get("/status")
def card_status():
    return {"enabled": card_payments_enabled()}


@router.post("/checkout")
@limiter.limit("5/minute")
def card_checkout(
    request: Request,
    body: CardCheckoutRequest,
    current_user=Depends(get_current_user),
):
    if not card_payments_enabled():
        raise HTTPException(
            status_code=503,
            detail="Card payments are not available yet. Please use M-Pesa.",
        )

    plan_id = body.plan.upper().strip()
    plan = get_plan(plan_id)

    if plan is None:
        raise HTTPException(status_code=400, detail="Invalid subscription plan.")

    # The price always comes from the server-side catalogue.
    subscription_id = subscription_service.create_subscription(
        user_id=current_user["id"],
        plan=plan_id,
        payment_method="CARD",
        amount=plan["price"],
        currency=plan["currency"],
    )

    try:
        result = card_service.start_checkout(
            subscription_id=subscription_id,
            email=current_user["email"],
            amount=plan["price"],
            plan=plan_id,
        )
    except Exception:
        logger.exception("Card checkout failed for subscription %s", subscription_id)
        subscription_service.mark_payment_failed(subscription_id)
        raise HTTPException(
            status_code=502,
            detail="We couldn't start the card payment. Please try again in a moment.",
        )

    return {
        "success": True,
        "subscription_id": subscription_id,
        "reference": result["reference"],
        "authorization_url": result["authorization_url"],
    }


@router.get("/verify/{reference}")
@limiter.limit("30/minute")
def card_verify(
    request: Request,
    reference: str,
    current_user=Depends(get_current_user),
):
    """Called when the customer returns from the card page."""

    try:
        status = card_service.verify_and_activate(reference, user_id=current_user["id"])
    except Exception:
        logger.exception("Card verification failed for %s", reference)
        raise HTTPException(
            status_code=502, detail="Could not confirm the payment yet. Try again shortly."
        )

    if status == "unknown":
        raise HTTPException(status_code=404, detail="Payment not found.")

    return {"success": True, "status": status}


@router.post("/webhook", include_in_schema=False)
async def card_webhook(request: Request):
    """Paystack server-to-server notification; trusted only if correctly signed."""

    raw = await request.body()

    if not card_service.valid_signature(raw, request.headers.get("x-paystack-signature")):
        raise HTTPException(status_code=404)

    try:
        event = json.loads(raw)
    except ValueError:
        return JSONResponse({"received": False}, status_code=400)

    try:
        outcome = card_service.handle_webhook_event(event)
    except Exception:
        # A 5xx makes Paystack retry later, which is what we want.
        logger.exception("Card webhook processing failed")
        raise HTTPException(status_code=500)

    return {"received": True, "outcome": outcome}
