"""
M-Pesa-backed betting wallet deposits and withdrawals.

Sits next to database/betting_repository.py (which owns the wallet/ledger
itself — get_or_create_wallet, credit_wallet, debit_wallet) and only adds
the bookkeeping for the external M-Pesa request each deposit/withdrawal is
waiting on: wallet_mpesa_requests rows, created PENDING and resolved to
COMPLETED/FAILED by the callbacks in api/mpesa.py.

Same conventions as the rest of database/*: plain functions, the pooled
get_connection() context manager, RealDictCursor rows returned straight to
the caller.
"""

import logging

from decimal import Decimal

from database.betting_repository import (
    InsufficientFundsError,
    credit_wallet,
    debit_wallet,
)
from database.db_config import get_connection

logger = logging.getLogger(__name__)


# ==========================================================
# DEPOSITS (STK push — money IN)
# ==========================================================

def create_deposit_request(
    user_id,
    phone,
    gross_amount: Decimal,
    tax_amount: Decimal,
    net_amount: Decimal,
    checkout_request_id,
    merchant_request_id=None,
):
    """
    Record a deposit as PENDING the moment the STK push is sent — the
    wallet is NOT touched yet. Unlike a withdrawal, a deposit's money
    doesn't exist anywhere in FOOTY254 until M-Pesa actually confirms it
    (the callback), so there's nothing to credit or reverse here.
    """

    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO wallet_mpesa_requests
                    (user_id, direction, status, phone, gross_amount,
                     tax_amount, net_amount, checkout_request_id,
                     merchant_request_id)
                VALUES
                    (%s, 'DEPOSIT', 'PENDING', %s, %s, %s, %s, %s, %s)
                RETURNING *;
                """,
                (
                    user_id,
                    phone,
                    gross_amount,
                    tax_amount,
                    net_amount,
                    checkout_request_id,
                    merchant_request_id,
                ),
            )
            row = cur.fetchone()
        conn.commit()

    return row


def get_recent_pending_deposit(user_id):
    """Same guard subscriptions already use (SubscriptionService.get_recent_pending_checkout)
    against a page refresh re-submitting the deposit form and firing a
    second STK prompt on top of one the user hasn't answered yet."""

    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT * FROM wallet_mpesa_requests
                WHERE user_id = %s AND direction = 'DEPOSIT' AND status = 'PENDING'
                  AND created_at > NOW() - INTERVAL '5 minutes'
                ORDER BY created_at DESC
                LIMIT 1;
                """,
                (user_id,),
            )
            return cur.fetchone()


def get_deposit_request_by_checkout(checkout_request_id):

    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT * FROM wallet_mpesa_requests
                WHERE direction = 'DEPOSIT' AND checkout_request_id = %s;
                """,
                (checkout_request_id,),
            )
            return cur.fetchone()


def mark_deposit_completed(request_id, mpesa_receipt):
    """
    Credit the NET amount (gross minus tax — config/betting_finance.py) to
    the user's wallet and mark the request COMPLETED, in one transaction so
    a crash between the two can never happen. Idempotent: if this request
    was already COMPLETED (a duplicate M-Pesa callback), the wallet is not
    credited twice — mirrors how api/mpesa.py already de-dupes subscription
    activation callbacks.
    """

    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT * FROM wallet_mpesa_requests WHERE id = %s FOR UPDATE;
                """,
                (request_id,),
            )
            request = cur.fetchone()

            if request is None:
                raise ValueError(f"No wallet_mpesa_requests row with id={request_id}")

            if request["status"] == "COMPLETED":
                logger.info("Deposit request %s already completed; skipping.", request_id)
                conn.commit()
                return request

            cur.execute(
                """
                UPDATE wallet_mpesa_requests
                SET status = 'COMPLETED', mpesa_receipt = %s, updated_at = NOW()
                WHERE id = %s
                RETURNING *;
                """,
                (mpesa_receipt, request_id),
            )
            request = cur.fetchone()

        # credit_wallet opens its own connection/transaction — deliberately
        # done just outside the `with conn.cursor()` block above so the
        # request-status UPDATE above is already committed by the time we
        # touch the wallet (the reverse order risks crediting a wallet for
        # a request whose own status update then fails to commit).
        conn.commit()

    credit_wallet(
        request["user_id"],
        Decimal(str(request["net_amount"])),
        "DEPOSIT",
        reference=request["checkout_request_id"],
        description=(
            f"M-Pesa deposit (sandbox) — KES {request['gross_amount']} "
            f"less KES {request['tax_amount']} tax."
        ),
    )

    return request


def mark_deposit_failed(request_id, reason):

    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE wallet_mpesa_requests
                SET status = 'FAILED', failure_reason = %s, updated_at = NOW()
                WHERE id = %s AND status = 'PENDING'
                RETURNING *;
                """,
                (reason, request_id),
            )
            row = cur.fetchone()
        conn.commit()

    return row


# ==========================================================
# WITHDRAWALS (B2C — money OUT)
# ==========================================================

def create_withdrawal_request(
    user_id,
    phone,
    gross_amount: Decimal,
    tax_amount: Decimal,
    net_amount: Decimal,
):
    """
    Debit the wallet for the GROSS amount immediately (before the B2C call
    is even sent), then record the request PENDING. Debiting up front —
    rather than waiting for B2C to confirm, the way a deposit waits for STK
    to confirm before crediting anything — is deliberate: it is what stops
    a user from staking the same money on a bet while a withdrawal of it is
    in flight. If the B2C payout then fails or times out, the gross amount
    is refunded (mark_withdrawal_failed, below) as a WITHDRAWAL_REVERSAL.

    Raises InsufficientFundsError (from debit_wallet) if the wallet can't
    cover the gross amount — the caller (api/betting.py) turns that into a
    402 before ever calling mpesa_service.b2c_payment(), so a withdrawal
    that can't be afforded never reaches Safaricom at all.
    """

    debit_wallet(
        user_id,
        gross_amount,
        "WITHDRAWAL",
        description=(
            f"M-Pesa withdrawal (sandbox) — KES {net_amount} to be sent, "
            f"KES {tax_amount} tax."
        ),
    )

    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO wallet_mpesa_requests
                    (user_id, direction, status, phone, gross_amount,
                     tax_amount, net_amount)
                VALUES
                    (%s, 'WITHDRAWAL', 'PENDING', %s, %s, %s, %s)
                RETURNING *;
                """,
                (user_id, phone, gross_amount, tax_amount, net_amount),
            )
            row = cur.fetchone()
        conn.commit()

    return row


def attach_withdrawal_conversation_id(request_id, conversation_id, originator_conversation_id):
    """Called right after mpesa_service.b2c_payment() returns its
    synchronous acknowledgement, so the later async result/timeout
    callback (which only carries these IDs, not our own request_id) can
    find its way back to this row."""

    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE wallet_mpesa_requests
                SET conversation_id = %s, originator_conversation_id = %s, updated_at = NOW()
                WHERE id = %s
                RETURNING *;
                """,
                (conversation_id, originator_conversation_id, request_id),
            )
            return cur.fetchone()


def get_withdrawal_request_by_conversation(conversation_id):

    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT * FROM wallet_mpesa_requests
                WHERE direction = 'WITHDRAWAL' AND conversation_id = %s;
                """,
                (conversation_id,),
            )
            return cur.fetchone()


def mark_withdrawal_completed(request_id, mpesa_receipt):
    """The gross amount was already debited at request time — completion
    just records the receipt. Idempotent against duplicate callbacks, same
    as mark_deposit_completed()."""

    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT * FROM wallet_mpesa_requests WHERE id = %s FOR UPDATE;",
                (request_id,),
            )
            request = cur.fetchone()

            if request is None:
                raise ValueError(f"No wallet_mpesa_requests row with id={request_id}")

            if request["status"] == "COMPLETED":
                logger.info("Withdrawal request %s already completed; skipping.", request_id)
                conn.commit()
                return request

            cur.execute(
                """
                UPDATE wallet_mpesa_requests
                SET status = 'COMPLETED', mpesa_receipt = %s, updated_at = NOW()
                WHERE id = %s
                RETURNING *;
                """,
                (mpesa_receipt, request_id),
            )
            row = cur.fetchone()
        conn.commit()

    return row


def mark_withdrawal_failed(request_id, reason):
    """Refund the gross amount that was debited up front (create_withdrawal_request),
    since the payout never actually reached the user. Idempotent: a
    second failure callback for an already-FAILED request does not refund
    twice."""

    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT * FROM wallet_mpesa_requests WHERE id = %s FOR UPDATE;",
                (request_id,),
            )
            request = cur.fetchone()

            if request is None:
                raise ValueError(f"No wallet_mpesa_requests row with id={request_id}")

            if request["status"] in ("FAILED", "COMPLETED"):
                logger.info(
                    "Withdrawal request %s already %s; not refunding again.",
                    request_id,
                    request["status"],
                )
                conn.commit()
                return request

            cur.execute(
                """
                UPDATE wallet_mpesa_requests
                SET status = 'FAILED', failure_reason = %s, updated_at = NOW()
                WHERE id = %s
                RETURNING *;
                """,
                (reason, request_id),
            )
            row = cur.fetchone()
        conn.commit()

    credit_wallet(
        request["user_id"],
        Decimal(str(request["gross_amount"])),
        "WITHDRAWAL_REVERSAL",
        description=f"Withdrawal failed ({reason}) — KES {request['gross_amount']} refunded.",
    )

    return row


def get_user_mpesa_requests(user_id, limit=50):

    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT * FROM wallet_mpesa_requests
                WHERE user_id = %s
                ORDER BY created_at DESC
                LIMIT %s;
                """,
                (user_id, limit),
            )
            return cur.fetchall()
