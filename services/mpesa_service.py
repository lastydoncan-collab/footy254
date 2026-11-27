import base64
import logging
import threading
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

import ssl
import time

import requests
from cryptography.hazmat.primitives.asymmetric import padding
from cryptography.x509 import load_pem_x509_certificate, load_der_x509_certificate
from requests.adapters import HTTPAdapter

from config.mpesa import (
    MPESA_B2C_CERT_PATH,
    MPESA_B2C_COMMAND_ID,
    MPESA_B2C_INITIATOR_NAME,
    MPESA_B2C_INITIATOR_PASSWORD,
    MPESA_B2C_RESULT_URL,
    MPESA_B2C_SHORTCODE,
    MPESA_B2C_TIMEOUT_URL,
    MPESA_B2C_URL,
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
    validate_mpesa_b2c_config,
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


def _raise_for_status_with_body(response):
    """
    requests' own response.raise_for_status() only reports the HTTP status
    line ("400 Client Error: Bad Request for url: ...") and silently
    discards the response body - which for Daraja is exactly where the
    useful part lives, e.g. {"errorCode": "400.002.02",
    "errorMessage": "Bad Request - Invalid PartyB"}. Call this instead
    everywhere a Daraja response is checked so that body ends up in the
    logs and in the exception message instead of being thrown away.
    """

    try:
        response.raise_for_status()
    except requests.exceptions.HTTPError as exc:
        body = (response.text or "").strip()
        if body:
            logger.error("Daraja error response body: %s", body)
        raise requests.exceptions.HTTPError(
            f"{exc} | Daraja response body: {body or '(empty)'}",
            response=response,
        ) from exc


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
            _raise_for_status_with_body(response)
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

        _raise_for_status_with_body(response)
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

        _raise_for_status_with_body(response)
        result = response.json()

        logger.info(

            "CheckoutRequestID=%s",

            result.get("CheckoutRequestID"),

        )

        return result


    # ==========================================================
    # B2C SECURITY CREDENTIAL
    # ==========================================================

    @staticmethod
    def generate_security_credential() -> str:
        """
        Daraja's B2C "SecurityCredential" is the initiator password,
        RSA-encrypted (PKCS#1 v1.5 padding) with Safaricom's own public key
        certificate and base64-encoded — NOT the plaintext password, and
        NOT the same thing as the STK push password above (which is just a
        base64 of shortcode+passkey+timestamp, no encryption involved).

        The certificate file (MPESA_B2C_CERT_PATH) is downloaded from your
        Daraja app's dashboard — Safaricom publishes a different one for
        Sandbox vs. Production, so there is no built-in default to fall
        back to the way the STK shortcode/passkey have one.
        """

        with open(MPESA_B2C_CERT_PATH, "rb") as cert_file:
            cert_bytes = cert_file.read()

        try:
            certificate = load_pem_x509_certificate(cert_bytes)
        except ValueError:
            # Safaricom's download is sometimes DER (binary), not PEM.
            certificate = load_der_x509_certificate(cert_bytes)

        public_key = certificate.public_key()

        encrypted = public_key.encrypt(
            MPESA_B2C_INITIATOR_PASSWORD.encode("utf-8"),
            padding.PKCS1v15(),
        )

        return base64.b64encode(encrypted).decode("utf-8")

    # ==========================================================
    # B2C PAYMENT (withdrawal payout)
    # ==========================================================

    def b2c_payment(
        self,
        phone_number: str,
        amount,
        remarks: str,
        occasion: str = "",
    ):
        """
        Send money OUT to a customer's phone — the opposite direction from
        stk_push() above. Used only for betting wallet withdrawals; nothing
        else in FOOTY254 pays a customer directly.

        Returns Daraja's synchronous acknowledgement (accepted/queued for
        processing, with a ConversationID to correlate against the async
        result callback) — NOT the final outcome. The real outcome (did
        the money actually land) only arrives later at MPESA_B2C_RESULT_URL
        / MPESA_B2C_TIMEOUT_URL (see api/mpesa.py), exactly like how
        stk_push()'s real outcome only arrives at MPESA_CALLBACK_URL rather
        than in its own return value.
        """

        validate_mpesa_b2c_config()

        phone_number = self.normalize_phone_number(phone_number)

        token = self.get_access_token()

        security_credential = self.generate_security_credential()

        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        }

        payload = {
            "InitiatorName": MPESA_B2C_INITIATOR_NAME,
            "SecurityCredential": security_credential,
            "CommandID": MPESA_B2C_COMMAND_ID,
            "Amount": max(1, int(amount)),
            "PartyA": MPESA_B2C_SHORTCODE,
            "PartyB": phone_number,
            "Remarks": remarks[:100],
            "QueueTimeOutURL": MPESA_B2C_TIMEOUT_URL,
            "ResultURL": MPESA_B2C_RESULT_URL,
            "Occasion": occasion[:100],
        }

        logger.info(
            "B2C payment phone=%s amount=%s remarks=%s",
            phone_number,
            amount,
            remarks,
        )

        response = _daraja_request(
            "POST",
            MPESA_B2C_URL,
            json=payload,
            headers=headers,
            timeout=MPESA_REQUEST_TIMEOUT_SECONDS,
        )

        _raise_for_status_with_body(response)
        result = response.json()

        if str(result.get("ResponseCode")) != "0":
            raise RuntimeError(
                result.get("ResponseDescription") or "Daraja rejected the B2C request."
            )

        return result

    # ==========================================================
    # B2C RESULT / TIMEOUT PARSERS
    # ==========================================================

    @staticmethod
    def parse_b2c_result(payload: dict):
        """
        Parse the async B2C "Result" callback. Shape is deliberately similar
        to parse_callback() below (same kind of flattened metadata dict)
        but the raw Daraja envelope is completely different from the STK
        callback's — B2C nests under "Result", not "Body.stkCallback", and
        its metadata list is "ResultParameters.ResultParameter" instead of
        "CallbackMetadata.Item".
        """

        result = payload.get("Result", {})

        metadata = {}

        for item in result.get("ResultParameters", {}).get("ResultParameter", []):
            key = item.get("Key")
            if key:
                metadata[key] = item.get("Value")

        return {
            "result_code": result.get("ResultCode"),
            "result_desc": result.get("ResultDesc"),
            "conversation_id": result.get("ConversationID"),
            "originator_conversation_id": result.get("OriginatorConversationID"),
            "transaction_id": result.get("TransactionID"),
            "metadata": metadata,
        }

    @staticmethod
    def parse_b2c_timeout(payload: dict):
        """
        Parse the "QueueTimeOutURL" callback — fires if the ResultURL never
        gets called in time (Daraja gives up waiting on itself). Shares the
        same top-level "Result" shape as parse_b2c_result() but Daraja does
        not promise ResultParameters will be present on a timeout, so this
        stays minimal rather than reusing parse_b2c_result() and risking a
        confusing partial metadata dict.
        """

        result = payload.get("Result", {})

        return {
            "result_code": result.get("ResultCode"),
            "result_desc": result.get("ResultDesc"),
            "conversation_id": result.get("ConversationID"),
            "originator_conversation_id": result.get("OriginatorConversationID"),
        }

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
