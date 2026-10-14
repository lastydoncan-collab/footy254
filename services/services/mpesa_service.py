import base64
import logging
import threading
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

import ssl
import time

import requests
from requests.adapters import HTTPAdapter

from config.mpesa import (
    MPESA_CALLBACK_URL,
    MPESA_CONSUMER_KEY,
    MPESA_CONSUMER_SECRET,
    MPESA_PARTY_B,
    MPESA_PASSKEY,
    MPESA_QUERY_URL,
    MPESA_REQUEST_TIMEOUT_SECONDS,
    MPESA_SHORTCODE,
    MPESA_STK_PUSH_URL,
    MPESA_TOKEN_URL,
    MPESA_TRANSACTION_TYPE,
    validate_mpesa_config,
)

logger = logging.getLogger(__name__)


class _TLS12Adapter(HTTPAdapter):
    """Caps TLS at 1.2. Some Safaricom hosts (notably the sandbox) drop the
    connection during a TLS 1.3 handshake, which surfaces on newer
    Python/OpenSSL builds as ``SSLEOFError: UNEXPECTED_EOF_WHILE_READING``."""

    def init_poolmanager(self, *args, **kwargs):
        context = ssl.create_default_context()
        context.maximum_version = ssl.TLSVersion.TLSv1_2
        kwargs["ssl_context"] = context
        return super().init_poolmanager(*args, **kwargs)


def _daraja_request(method: str, url: str, **kwargs):
    """
    One Daraja HTTP call with a few safe retries.

    * Attempt 1 uses normal TLS, attempt 2 onwards caps TLS at 1.2, each on a
      brand-new connection.
    * Only failures that happen BEFORE the request is sent are retried
      (TLS handshake errors and connect timeouts), so an STK push is never
      sent twice. A plain GET (the OAuth token) is also retried on any
      connection error because repeating it is harmless.
    """

    retry_on = (requests.exceptions.SSLError, requests.exceptions.ConnectTimeout)
    if method.upper() == "GET":
        retry_on = retry_on + (requests.exceptions.ConnectionError,)

    last_error = None

    for attempt in range(1, 4):
        session = requests.Session()
        if attempt > 1:
            session.mount("https://", _TLS12Adapter())

        try:
            return session.request(method, url, **kwargs)
        except retry_on as exc:
            last_error = exc
            logger.warning(
                "Daraja %s %s failed on attempt %s/3: %s", method, url, attempt, exc
            )
            time.sleep(0.8 * attempt)
        finally:
            session.close()

    raise last_error


class MpesaService:
    """
    Handles all communication with Safaricom Daraja API.
    """

    def __init__(self):
        self._access_token = None
        self._access_token_expires_at = None
        self._token_lock = threading.Lock()

    # ==========================================================
    # ACCESS TOKEN
    # ==========================================================

    def get_access_token(self):
        """Return a cached Daraja token, refreshing it shortly before expiry."""
        now = datetime.now(timezone.utc)
        if self._access_token and self._access_token_expires_at and now < self._access_token_expires_at:
            return self._access_token

        with self._token_lock:
            now = datetime.now(timezone.utc)
            if self._access_token and self._access_token_expires_at and now < self._access_token_expires_at:
                return self._access_token

            response = _daraja_request(
                "GET",
                MPESA_TOKEN_URL,
                auth=(MPESA_CONSUMER_KEY, MPESA_CONSUMER_SECRET),
                timeout=MPESA_REQUEST_TIMEOUT_SECONDS,
            )
            response.raise_for_status()
            data = response.json()
            token = data.get("access_token")
            if not token:
                raise RuntimeError("Daraja did not return an access token.")

            try:
                expires_in = max(60, int(data.get("expires_in", 3599)))
            except (TypeError, ValueError):
                expires_in = 3599
            self._access_token = token
            self._access_token_expires_at = now + timedelta(seconds=max(30, expires_in - 60))
            return token

    # ==========================================================
    # TIMESTAMP
    # ==========================================================

    @staticmethod
    def generate_timestamp():
        # Daraja expects East Africa Time, irrespective of the server's host timezone.
        return datetime.now(ZoneInfo("Africa/Nairobi")).strftime("%Y%m%d%H%M%S")

    # ==========================================================
    # PASSWORD
    # ==========================================================

    def generate_password(self):

        timestamp = self.generate_timestamp()

        password = base64.b64encode(

            (
                MPESA_SHORTCODE
                + MPESA_PASSKEY
                + timestamp
            ).encode()

        ).decode()

        return password, timestamp

    # ==========================================================
    # NORMALIZE PHONE NUMBER
    # ==========================================================

    @staticmethod
    def normalize_phone_number(phone_number: str) -> str:

        # Strip spaces, dashes, and parens so "0712 345 678" or
        # "(0712) 345-678" normalize the same as "0712345678".
        phone = "".join(
            ch for ch in phone_number.strip() if ch.isdigit() or ch == "+"
        )

        if phone.startswith("+254"):
            phone = phone[1:]
        elif phone.startswith("254"):
            pass
        elif phone.startswith("0"):
            # Covers both the 07xx and newer 01xx Safaricom ranges.
            phone = "254" + phone[1:]
        elif phone.startswith("7") or phone.startswith("1"):
            phone = "254" + phone

        return phone

    @staticmethod
    def is_valid_phone_number(phone_number: str) -> bool:
        """
        A normalized Kenyan mobile number is 254 followed by 9 digits
        (12 digits total), starting with 7 or 1 (Safaricom's ranges).
        """

        normalized = MpesaService.normalize_phone_number(phone_number)

        return (
            len(normalized) == 12
            and normalized.startswith("254")
            and normalized[3] in ("7", "1")
            and normalized.isdigit()
        )

    # ==========================================================
    # STK PUSH
    # ==========================================================

    def stk_push(
        self,
        phone_number: str,
        amount,
        account_reference: str,
        transaction_desc: str,
    ):
        validate_mpesa_config()

        phone_number = self.normalize_phone_number(phone_number)

        token = self.get_access_token()

        password, timestamp = self.generate_password()

        headers = {

            "Authorization": f"Bearer {token}",

            "Content-Type": "application/json",

        }

        payload = {

            "BusinessShortCode": MPESA_SHORTCODE,

            "Password": password,

            "Timestamp": timestamp,

            "TransactionType": MPESA_TRANSACTION_TYPE,

            "Amount": max(
                1,
                int(amount),
            ),

            "PartyA": phone_number,

            "PartyB": MPESA_PARTY_B,

            "PhoneNumber": phone_number,

            "CallBackURL": MPESA_CALLBACK_URL,

            "AccountReference": account_reference,

            "TransactionDesc": transaction_desc,

        }

        logger.info(

            "STK Push"

            " phone=%s"

            " amount=%s"

            " account=%s",

            phone_number,

            amount,

            account_reference,

        )

        response = _daraja_request(

            "POST",

            MPESA_STK_PUSH_URL,

            json=payload,

            headers=headers,

            timeout=MPESA_REQUEST_TIMEOUT_SECONDS,

        )

        response.raise_for_status()
        result = response.json()
        if str(result.get("ResponseCode")) != "0":
            raise RuntimeError(result.get("ResponseDescription") or "Daraja rejected the STK request.")
        return result

    # ==========================================================
    # QUERY TRANSACTION
    # ==========================================================

    def query_transaction(

        self,

        checkout_request_id: str,

    ):

        validate_mpesa_config()
        token = self.get_access_token()

        password, timestamp = self.generate_password()

        headers = {

            "Authorization": f"Bearer {token}",

            "Content-Type": "application/json",

        }

        payload = {

            "BusinessShortCode": MPESA_SHORTCODE,

            "Password": password,

            "Timestamp": timestamp,

            "CheckoutRequestID": checkout_request_id,

        }

        response = _daraja_request(

            "POST",

            MPESA_QUERY_URL,

            json=payload,

            headers=headers,

            timeout=MPESA_REQUEST_TIMEOUT_SECONDS,

        )

        response.raise_for_status()
        result = response.json()

        logger.info(

            "CheckoutRequestID=%s",

            result.get("CheckoutRequestID"),

        )

        return result


    # ==========================================================
    # CALLBACK PARSER
    # ==========================================================

    @staticmethod
    def parse_callback(payload: dict):

        body = payload.get("Body", {})

        callback = body.get("stkCallback", {})

        result_code = callback.get("ResultCode")

        result_desc = callback.get("ResultDesc")

        checkout_request_id = callback.get("CheckoutRequestID")

        merchant_request_id = callback.get("MerchantRequestID")

        metadata = {}

        callback_items = (

            callback
            .get("CallbackMetadata", {})
            .get("Item", [])

        )

        for item in callback_items:
            name = item.get("Name")
            if name:
                metadata[name] = item.get("Value")

        return {

            "result_code": result_code,

            "result_desc": result_desc,

            "checkout_request_id": checkout_request_id,

            "merchant_request_id": merchant_request_id,

            "metadata": metadata,

        }


mpesa_service = MpesaService()
