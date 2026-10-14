"""Card payment (Paystack) configuration. Card details never touch this server:
the customer pays on Paystack's hosted page."""

import os

PAYSTACK_SECRET_KEY = os.getenv("PAYSTACK_SECRET_KEY", "").strip()
PAYSTACK_CURRENCY = os.getenv("PAYSTACK_CURRENCY", "KES").strip().upper()
# Where Paystack sends the customer after paying (your frontend page).
PAYSTACK_RETURN_URL = os.getenv(
    "PAYSTACK_RETURN_URL", "http://localhost:5173/subscription/card-return"
).strip()
PAYSTACK_BASE_URL = "https://api.paystack.co"
PAYSTACK_TIMEOUT_SECONDS = int(os.getenv("PAYSTACK_TIMEOUT_SECONDS", "30"))


def card_payments_enabled() -> bool:
    return bool(PAYSTACK_SECRET_KEY)
