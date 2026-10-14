"""Card payments through Paystack (hosted checkout)."""

import hashlib
import hmac
import logging
import secrets
from decimal import Decimal

import requests

from config.card import (
    PAYSTACK_BASE_URL,
    PAYSTACK_CURRENCY,
    PAYSTACK_RETURN_URL,
    PAYSTACK_SECRET_KEY,
    PAYSTACK_TIMEOUT_SECONDS,
    card_payments_enabled,
)
from database.db_config import get_connection
from services.subscription_service import subscription_service

logger = logging.getLogger(__name__)


class CardNotConfigured(RuntimeError):
    pass


def _headers():
    if not card_payments_enabled():
        raise CardNotConfigured("Card payments are not configured.")
    return {
        "Authorization": f"Bearer {PAYSTACK_SECRET_KEY}",
        "Content-Type": "application/json",
    }


def _to_subunits(amount: Decimal) -> int:
    return int((Decimal(str(amount)) * 100).to_integral_value())


def new_reference(subscription_id: int) -> str:
    return f"FOOTY254-CARD-{subscription_id}-{secrets.token_hex(6)}"


def _store_reference(subscription_id: int, reference: str):
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE subscriptions SET gateway_reference=%s, updated_at=NOW() "
                "WHERE subscription_id=%s AND status='PENDING';",
                (reference, subscription_id),
            )


def _find_by_reference(reference: str):
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT subscription_id, user_id, plan, status, amount, currency
                  FROM subscriptions WHERE gateway_reference=%s;
                """,
                (reference,),
            )
            return cur.fetchone()


def start_checkout(*, subscription_id: int, email: str, amount: Decimal, plan: str):
    """Create a Paystack transaction and return its hosted payment URL."""

    reference = new_reference(subscription_id)

    response = requests.post(
        f"{PAYSTACK_BASE_URL}/transaction/initialize",
        json={
            "email": email,
            "amount": _to_subunits(amount),
            "currency": PAYSTACK_CURRENCY,
            "reference": reference,
            "callback_url": PAYSTACK_RETURN_URL,
            "channels": ["card"],
            "metadata": {"subscription_id": subscription_id, "plan": plan},
        },
        headers=_headers(),
        timeout=PAYSTACK_TIMEOUT_SECONDS,
    )
    response.raise_for_status()
    data = (response.json() or {}).get("data") or {}

    if not data.get("authorization_url"):
        raise RuntimeError("Paystack did not return a payment URL.")

    _store_reference(subscription_id, reference)

    return {"reference": reference, "authorization_url": data["authorization_url"]}


def _apply_success(reference: str, paid_subunits: int, currency: str) -> str:
    """Activate the subscription if the paid amount matches. Returns a status."""

    row = _find_by_reference(reference)

    if row is None:
        return "unknown"

    if row["status"] == "ACTIVE":
        return "active"

    expected = _to_subunits(row["amount"])

    if paid_subunits != expected or (currency or "").upper() != (row["currency"] or "").upper():
        logger.warning(
            "Card payment mismatch for %s: paid %s %s, expected %s %s",
            reference, paid_subunits, currency, expected, row["currency"],
        )
        return "mismatch"

    subscription_service.update_transaction_reference(row["subscription_id"], reference)
    ok = subscription_service.activate_subscription(
        subscription_id=row["subscription_id"],
        transaction_reference=reference,
        paid_amount=Decimal(paid_subunits) / 100,
    )
    return "active" if ok else "failed"


def verify_and_activate(reference: str, user_id: int | None = None) -> str:
    """Ask Paystack for the truth about a reference (never trust the browser)."""

    row = _find_by_reference(reference)
    if row is None or (user_id is not None and row["user_id"] != user_id):
        return "unknown"

    if row["status"] == "ACTIVE":
        return "active"

    response = requests.get(
        f"{PAYSTACK_BASE_URL}/transaction/verify/{reference}",
        headers=_headers(),
        timeout=PAYSTACK_TIMEOUT_SECONDS,
    )
    response.raise_for_status()
    data = (response.json() or {}).get("data") or {}

    status = data.get("status")

    if status == "success":
        return _apply_success(reference, int(data.get("amount", 0)), data.get("currency", ""))

    if status in {"failed", "abandoned", "reversed"}:
        return "failed"

    return "pending"


def valid_signature(raw_body: bytes, signature: str | None) -> bool:
    if not PAYSTACK_SECRET_KEY or not signature:
        return False
    expected = hmac.new(PAYSTACK_SECRET_KEY.encode(), raw_body, hashlib.sha512).hexdigest()
    return hmac.compare_digest(expected, signature)


def handle_webhook_event(event: dict) -> str:
    if event.get("event") != "charge.success":
        return "ignored"

    data = event.get("data") or {}
    reference = data.get("reference")

    if not reference:
        return "ignored"

    return _apply_success(reference, int(data.get("amount", 0)), data.get("currency", ""))
