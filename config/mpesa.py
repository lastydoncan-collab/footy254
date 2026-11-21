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

# ==========================================================
# B2C (business-to-customer payout) — betting wallet withdrawals only.
# STK push (above) pulls money IN from a customer; B2C is the opposite
# Daraja product, used to push money OUT to a customer's phone, which is
# what a bet withdrawal needs and nothing above this point supports.
#
# "testapiuser" / "Safaricom999!*!" are Safaricom's own published sandbox
# B2C test credentials (same spirit as the sandbox STK shortcode/passkey
# already defaulted above — public test values, not secrets), used here
# only as the sandbox default so this works out of the box; production
# must set real values via env vars.
# ==========================================================

MPESA_B2C_INITIATOR_NAME = os.getenv("MPESA_B2C_INITIATOR_NAME", "").strip() or (
    "testapiuser" if MPESA_ENVIRONMENT == "sandbox" else ""
)
MPESA_B2C_INITIATOR_PASSWORD = os.getenv("MPESA_B2C_INITIATOR_PASSWORD", "").strip() or (
    "Safaricom999!*!" if MPESA_ENVIRONMENT == "sandbox" else ""
)
MPESA_B2C_SHORTCODE = os.getenv("MPESA_B2C_SHORTCODE", "").strip() or (
    "600000" if MPESA_ENVIRONMENT == "sandbox" else ""
)
MPESA_B2C_COMMAND_ID = os.getenv("MPESA_B2C_COMMAND_ID", "BusinessPayment").strip()

# Safaricom encrypts the initiator password with THEIR OWN public key
# certificate (a different file for sandbox vs. production), downloaded
# from your Daraja app's dashboard — there is no universal public sandbox
# certificate to default to the way there is for the shortcode/passkey
# above, so this one env var has no fallback and B2C simply refuses to run
# without it (see generate_security_credential() in services/mpesa_service.py).
MPESA_B2C_CERT_PATH = os.getenv("MPESA_B2C_CERT_PATH", "").strip()

MPESA_B2C_URL = f"{MPESA_BASE_URL}/mpesa/b2c/v1/paymentrequest"

_b2c_result_url = os.getenv(
    "MPESA_B2C_RESULT_URL", "http://localhost:8000/mpesa/callback/b2c/result/{secret}"
).strip()
MPESA_B2C_RESULT_URL = (
    _b2c_result_url.format(secret=MPESA_CALLBACK_SECRET)
    if "{secret}" in _b2c_result_url
    else _b2c_result_url.rstrip("/") + "/" + MPESA_CALLBACK_SECRET
)

_b2c_timeout_url = os.getenv(
    "MPESA_B2C_TIMEOUT_URL", "http://localhost:8000/mpesa/callback/b2c/timeout/{secret}"
).strip()
MPESA_B2C_TIMEOUT_URL = (
    _b2c_timeout_url.format(secret=MPESA_CALLBACK_SECRET)
    if "{secret}" in _b2c_timeout_url
    else _b2c_timeout_url.rstrip("/") + "/" + MPESA_CALLBACK_SECRET
)


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


def validate_mpesa_b2c_config() -> bool:
    """Validate B2C configuration immediately before a withdrawal payout.
    Separate from validate_mpesa_config() above because a deployment might
    only ever take deposits (STK) and never enable withdrawals (B2C) — it
    shouldn't need the certificate/initiator setup just to run the former."""

    required = {
        "MPESA_B2C_INITIATOR_NAME": MPESA_B2C_INITIATOR_NAME,
        "MPESA_B2C_INITIATOR_PASSWORD": MPESA_B2C_INITIATOR_PASSWORD,
        "MPESA_B2C_SHORTCODE": MPESA_B2C_SHORTCODE,
        "MPESA_B2C_CERT_PATH": MPESA_B2C_CERT_PATH,
    }
    missing = [name for name, value in required.items() if not value]
    if missing:
        raise RuntimeError(
            f"Missing M-Pesa B2C configuration: {', '.join(missing)}. "
            "MPESA_B2C_CERT_PATH must point to the Safaricom public key "
            "certificate downloaded from your Daraja app's dashboard "
            "(Sandbox or Production, matching MPESA_ENVIRONMENT)."
        )
    if not os.path.isfile(MPESA_B2C_CERT_PATH):
        raise RuntimeError(
            f"MPESA_B2C_CERT_PATH does not point to a file: {MPESA_B2C_CERT_PATH}"
        )
    callback = urlparse(MPESA_B2C_RESULT_URL)
    if not callback.scheme or not callback.netloc:
        raise RuntimeError("MPESA_B2C_RESULT_URL must be an absolute URL.")
    if MPESA_ENVIRONMENT == "production" and callback.scheme != "https":
        raise RuntimeError("Production MPESA_B2C_RESULT_URL must use HTTPS.")
    return True
