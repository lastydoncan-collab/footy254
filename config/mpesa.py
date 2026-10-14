"""Configuration and validation for Safaricom Daraja STK Push."""

import os
from urllib.parse import urlparse


MPESA_ENVIRONMENT = os.getenv("MPESA_ENVIRONMENT", "sandbox").strip().lower()
if MPESA_ENVIRONMENT not in {"sandbox", "production"}:
    raise RuntimeError("MPESA_ENVIRONMENT must be 'sandbox' or 'production'.")

MPESA_CONSUMER_KEY = os.getenv("MPESA_CONSUMER_KEY", "").strip()
MPESA_CONSUMER_SECRET = os.getenv("MPESA_CONSUMER_SECRET", "").strip()
MPESA_SHORTCODE = os.getenv("MPESA_SHORTCODE", "").strip()
MPESA_PASSKEY = os.getenv("MPESA_PASSKEY", "").strip()
# Who receives the money. Paybill: leave empty (same as MPESA_SHORTCODE).
# Till (Buy Goods): MPESA_SHORTCODE is the store/head-office number the passkey
# belongs to and MPESA_PARTY_B is the Till number customers pay.
MPESA_PARTY_B = os.getenv("MPESA_PARTY_B", "").strip() or MPESA_SHORTCODE
MPESA_CALLBACK_SECRET = os.getenv("MPESA_CALLBACK_SECRET", "").strip()
MPESA_TRANSACTION_TYPE = os.getenv(
    "MPESA_TRANSACTION_TYPE", "CustomerPayBillOnline"
).strip()
MPESA_REQUEST_TIMEOUT_SECONDS = int(os.getenv("MPESA_REQUEST_TIMEOUT_SECONDS", "30"))

if MPESA_TRANSACTION_TYPE not in {"CustomerPayBillOnline", "CustomerBuyGoodsOnline"}:
    raise RuntimeError(
        "MPESA_TRANSACTION_TYPE must be CustomerPayBillOnline or "
        "CustomerBuyGoodsOnline."
    )

_configured_callback_url = os.getenv(
    "MPESA_CALLBACK_URL", "http://localhost:8000/mpesa/callback/{secret}"
).strip()
MPESA_CALLBACK_URL = _configured_callback_url.format(secret=MPESA_CALLBACK_SECRET)
if "{secret}" not in _configured_callback_url:
    MPESA_CALLBACK_URL = _configured_callback_url.rstrip("/") + "/" + MPESA_CALLBACK_SECRET

SANDBOX_BASE_URL = "https://sandbox.safaricom.co.ke"
PRODUCTION_BASE_URL = "https://api.safaricom.co.ke"
MPESA_BASE_URL = PRODUCTION_BASE_URL if MPESA_ENVIRONMENT == "production" else SANDBOX_BASE_URL
MPESA_TOKEN_URL = f"{MPESA_BASE_URL}/oauth/v1/generate?grant_type=client_credentials"
MPESA_STK_PUSH_URL = f"{MPESA_BASE_URL}/mpesa/stkpush/v1/processrequest"
MPESA_QUERY_URL = f"{MPESA_BASE_URL}/mpesa/stkpushquery/v1/query"


def validate_mpesa_config() -> bool:
    """Validate configuration immediately before an outward payment request."""
    required = {
        "MPESA_CONSUMER_KEY": MPESA_CONSUMER_KEY,
        "MPESA_CONSUMER_SECRET": MPESA_CONSUMER_SECRET,
        "MPESA_SHORTCODE": MPESA_SHORTCODE,
        "MPESA_PASSKEY": MPESA_PASSKEY,
        "MPESA_CALLBACK_SECRET": MPESA_CALLBACK_SECRET,
    }
    missing = [name for name, value in required.items() if not value]
    if missing:
        raise RuntimeError(f"Missing M-Pesa configuration: {', '.join(missing)}")
    if len(MPESA_CALLBACK_SECRET) < 32:
        raise RuntimeError("MPESA_CALLBACK_SECRET must be at least 32 characters.")
    callback = urlparse(MPESA_CALLBACK_URL)
    if not callback.scheme or not callback.netloc:
        raise RuntimeError("MPESA_CALLBACK_URL must be an absolute URL.")
    if MPESA_ENVIRONMENT == "production" and callback.scheme != "https":
        raise RuntimeError("Production MPESA_CALLBACK_URL must use HTTPS.")
    if MPESA_ENVIRONMENT == "production":
        if MPESA_SHORTCODE == "174379":
            raise RuntimeError(
                "MPESA_SHORTCODE is still the sandbox test shortcode (174379); "
                "set your live Paybill/Store number."
            )
        host = (callback.hostname or "").lower()
        if host in {"localhost", "127.0.0.1"} or host.endswith(".local"):
            raise RuntimeError(
                "Production MPESA_CALLBACK_URL must be a public domain Safaricom can reach."
            )
    if MPESA_REQUEST_TIMEOUT_SECONDS <= 0:
        raise RuntimeError("MPESA_REQUEST_TIMEOUT_SECONDS must be positive.")
    return True
