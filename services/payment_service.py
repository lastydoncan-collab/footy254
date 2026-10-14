import logging

from datetime import datetime, timedelta
from decimal import Decimal

from database.db_config import get_connection

from services.subscription_service import (
    subscription_service,
)

logger = logging.getLogger(__name__)


class PaymentService:
    """
    Handles subscription payments.

    This service currently records successful payments.

    Later this service will integrate:

    - Stripe
    - Paystack
    - M-Pesa
    - Flutterwave

    without changing any frontend code.
    """

    # ==========================================================
    # CREATE PAYMENT RECORD
    # ==========================================================

    def record_payment(
        self,
        user_id: int,
        plan: str,
        amount: Decimal,
        payment_method: str,
        transaction_reference: str,
        duration_days: int,
        currency: str = "KES",
    ):

        started = datetime.utcnow()

        expires = started + timedelta(days=duration_days)

        conn = get_connection()

        cur = conn.cursor()

        cur.execute(
            """
            INSERT INTO subscriptions
            (
                user_id,
                plan,
                status,
                payment_method,
                transaction_reference,
                amount,
                currency,
                started_at,
                expires_at
            )
            VALUES
            (
                %s,
                %s,
                'ACTIVE',
                %s,
                %s,
                %s,
                %s,
                %s,
                %s
            )
            RETURNING subscription_id
            """,
            (
                user_id,
                plan,
                payment_method,
                transaction_reference,
                amount,
                currency,
                started,
                expires,
            ),
        )

        subscription_id = cur.fetchone()[0]

        conn.commit()

        cur.close()

        conn.close()

        subscription_service.activate_subscription(
            user_id=user_id,
            provider=payment_method,
            reference=transaction_reference,
            expiry=expires,
        )

        logger.info(
            "Subscription payment recorded "
            "(user=%s, plan=%s, subscription=%s)",
            user_id,
            plan,
            subscription_id,
        )

        return subscription_id

    # ==========================================================
    # PAYMENT HISTORY
    # ==========================================================

    def get_payment_history(
        self,
        user_id: int,
    ):

        conn = get_connection()

        cur = conn.cursor()

        cur.execute(
            """
            SELECT
                subscription_id,
                plan,
                status,
                payment_method,
                transaction_reference,
                amount,
                currency,
                started_at,
                expires_at,
                created_at,
                updated_at
            FROM subscriptions
            WHERE user_id=%s
            ORDER BY created_at DESC
            """,
            (user_id,),
        )

        rows = cur.fetchall()

        cur.close()

        conn.close()

        history = []

        for row in rows:

            history.append(
                {
                    "subscription_id": row[0],
                    "plan": row[1],
                    "status": row[2],
                    "payment_method": row[3],
                    "transaction_reference": row[4],
                    "amount": float(row[5]) if row[5] else None,
                    "currency": row[6],
                    "started_at": row[7],
                    "expires_at": row[8],
                    "created_at": row[9],
                    "updated_at": row[10],
                }
            )

        return history

    # ==========================================================
    # ACTIVE SUBSCRIPTION
    # ==========================================================

    def get_active_subscription(
        self,
        user_id: int,
    ):

        conn = get_connection()

        cur = conn.cursor()

        cur.execute(
            """
            SELECT
                subscription_id,
                user_id,
                plan,
                status,
                payment_method,
                transaction_reference,
                amount,
                currency,
                started_at,
                expires_at,
                created_at,
                updated_at
            FROM subscriptions
            WHERE user_id=%s
            AND status='ACTIVE'
            ORDER BY expires_at DESC
            LIMIT 1
            """,
            (user_id,),
        )

        row = cur.fetchone()

        cur.close()

        conn.close()

        if row is None:
            return None

        return {
            "subscription_id": row[0],
            "user_id": row[1],
            "plan": row[2],
            "status": row[3],
            "payment_method": row[4],
            "transaction_reference": row[5],
            "amount": float(row[6]) if row[6] else None,
            "currency": row[7],
            "started_at": row[8],
            "expires_at": row[9],
            "created_at": row[10],
            "updated_at": row[11],
        }

    # ==========================================================
    # LATEST SUBSCRIPTION
    # ==========================================================

    def get_latest_subscription(
        self,
        user_id: int,
    ):

        conn = get_connection()

        cur = conn.cursor()

        cur.execute(
            """
            SELECT
                subscription_id,
                user_id,
                plan,
                status,
                payment_method,
                transaction_reference,
                amount,
                currency,
                started_at,
                expires_at,
                created_at,
                updated_at
            FROM subscriptions
            WHERE user_id=%s
            ORDER BY created_at DESC
            LIMIT 1
            """,
            (user_id,),
        )

        row = cur.fetchone()

        cur.close()

        conn.close()

        if row is None:
            return None

        return {
            "subscription_id": row[0],
            "user_id": row[1],
            "plan": row[2],
            "status": row[3],
            "payment_method": row[4],
            "transaction_reference": row[5],
            "amount": float(row[6]) if row[6] else None,
            "currency": row[7],
            "started_at": row[8],
            "expires_at": row[9],
            "created_at": row[10],
            "updated_at": row[11],
        }

    # ==========================================================
    # EXPIRE SUBSCRIPTION
    # ==========================================================

    def expire_subscription(
        self,
        subscription_id: int,
    ):

        conn = get_connection()

        cur = conn.cursor()

        cur.execute(
            """
            UPDATE subscriptions
            SET
                status='EXPIRED',
                updated_at=NOW()
            WHERE subscription_id=%s
            """,
            (subscription_id,),
        )

        conn.commit()

        cur.close()

        conn.close()

        logger.info(
            "Subscription %s expired.",
            subscription_id,
        )

    # ==========================================================
    # CANCEL SUBSCRIPTION
    # ==========================================================

    def cancel_subscription(
        self,
        user_id: int,
    ):

        conn = get_connection()

        cur = conn.cursor()

        cur.execute(
            """
            UPDATE subscriptions
            SET
                status='EXPIRED',
                updated_at=NOW()
            WHERE user_id=%s
            AND status='ACTIVE'
            """,
            (user_id,),
        )

        conn.commit()

        cur.close()

        conn.close()

        subscription_service.deactivate_subscription(
            user_id=user_id,
        )

        logger.info(
            "Cancelled subscription for user %s",
            user_id,
        )

        return True


# ==========================================================
# SINGLETON
# ==========================================================

payment_service = PaymentService()