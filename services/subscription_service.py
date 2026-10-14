import logging

from datetime import datetime, timedelta
from decimal import Decimal

from database.db_config import get_connection

from config.subscription_plans import get_plan

logger = logging.getLogger(__name__)


class SubscriptionService:
    """
    FOOTY254 Subscription Service

    Handles:

    • Subscription records
    • Premium activation
    • Premium expiry
    • Checkout references
    • Transaction references
    • Subscription history
    """

    # ==========================================================
    # INTERNAL
    # ==========================================================

    def _connection(self):
        return get_connection()

    # ==========================================================
    # GET LATEST SUBSCRIPTION
    # ==========================================================

    def get_subscription(
        self,
        user_id: int,
    ):

        conn = self._connection()

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
                merchant_request_id,
                checkout_request_id,
                amount,
                currency,
                started_at,
                expires_at,
                created_at,
                updated_at
            FROM subscriptions
            WHERE user_id=%s
            ORDER BY
                expires_at DESC NULLS LAST,
                created_at DESC
            LIMIT 1
            """,
            (user_id,),
        )

        row = cur.fetchone()

        cur.close()
        conn.close()

        if row is None:
            return None

        return dict(row)

    # ==========================================================
    # USER SUBSCRIPTION
    # ==========================================================

    def get_user_subscription(
        self,
        user_id: int,
    ):

        return self.get_subscription(user_id)

    # ==========================================================
    # ACTIVE SUBSCRIPTION
    # ==========================================================

    def has_active_subscription(
        self,
        user_id: int,
    ):
        conn = self._connection()
        cur = conn.cursor()
        cur.execute(
            """
            SELECT EXISTS(
                SELECT 1 FROM subscriptions
                WHERE user_id=%s AND status='ACTIVE' AND expires_at > NOW()
            ) AS active
            """,
            (user_id,),
        )
        active = bool(cur.fetchone()["active"])
        cur.close()
        conn.close()
        return active
    
        # ==========================================================
    # CREATE SUBSCRIPTION
    # ==========================================================

    def create_subscription(
        self,
        user_id: int,
        plan: str,
        payment_method: str,
        amount: Decimal,
        currency: str = "KES",
    ):

        conn = self._connection()
        cur = conn.cursor()

        cur.execute(
            """
            INSERT INTO subscriptions
            (
                user_id,
                plan,
                status,
                payment_method,
                amount,
                currency,
                created_at,
                updated_at
            )
            VALUES
            (
                %s,
                %s,
                'PENDING',
                %s,
                %s,
                %s,
                NOW(),
                NOW()
            )
            RETURNING subscription_id
            """,
            (
                user_id,
                plan.upper(),
                payment_method,
                amount,
                currency,
            ),
        )

        row = cur.fetchone()

        subscription_id = row["subscription_id"]

        conn.commit()

        cur.close()
        conn.close()

        logger.info(
            "Created subscription %s for user %s",
            subscription_id,
            user_id,
        )

        return subscription_id

    def get_recent_pending_checkout(self, user_id: int):
        """Return an in-flight checkout so a refresh cannot send a second STK prompt."""
        conn = self._connection()
        cur = conn.cursor()
        cur.execute(
            """
            SELECT subscription_id, checkout_request_id, plan, created_at
            FROM subscriptions
            WHERE user_id=%s AND status='PENDING' AND checkout_request_id IS NOT NULL
              AND created_at > NOW() - INTERVAL '5 minutes'
            ORDER BY created_at DESC
            LIMIT 1
            """,
            (user_id,),
        )
        row = cur.fetchone()
        cur.close()
        conn.close()
        return dict(row) if row else None

    # ==========================================================
    # ACTIVATE SUBSCRIPTION
    # ==========================================================

    def activate_subscription(
        self,
        subscription_id: int,
        transaction_reference: str,
        paid_amount: Decimal | None = None,
    ):

        conn = self._connection()
        cur = conn.cursor()

        cur.execute(
            """
            SELECT user_id, plan, status, amount, transaction_reference
            FROM subscriptions
            WHERE subscription_id=%s
            FOR UPDATE
            """,
            (subscription_id,),
        )

        row = cur.fetchone()

        if row is None:

            cur.close()
            conn.close()

            return False

        # Daraja can retry callbacks. Only a pending row may be activated;
        # an already-active row is intentionally a no-op.
        if row["status"] == "ACTIVE":
            conn.rollback()
            cur.close()
            conn.close()
            return row["transaction_reference"] == transaction_reference
        if row["status"] != "PENDING":
            conn.rollback()
            cur.close()
            conn.close()
            return False
        if paid_amount is not None and Decimal(str(row["amount"])) != paid_amount:
            conn.rollback()
            cur.close()
            conn.close()
            logger.warning("Payment amount mismatch for subscription %s", subscription_id)
            return False

        user_id = row["user_id"]

        plan = row["plan"].upper().strip()

        plan_config = get_plan(plan)

        if plan_config is None:

            logger.warning(
                "Unknown subscription plan '%s'. Falling back to 30 days.",
                plan,
            )

            duration_days = 30

        else:

            duration_days = plan_config["duration_days"]

        cur.execute(
            """
            SELECT MAX(expires_at) AS expires_at
            FROM subscriptions
            WHERE user_id=%s AND status='ACTIVE' AND expires_at > NOW()
            """,
            (user_id,),
        )
        existing_expiry = cur.fetchone()["expires_at"]
        now = datetime.now(existing_expiry.tzinfo) if existing_expiry else datetime.utcnow()
        expires = (
            max(now, existing_expiry) + timedelta(days=duration_days)
            if existing_expiry else now + timedelta(days=duration_days)
        )

        cur.execute(
            """
            UPDATE subscriptions
            SET
                status='ACTIVE',
                transaction_reference=%s,
                started_at=NOW(),
                expires_at=%s,
                updated_at=NOW()
            WHERE subscription_id=%s AND status='PENDING'
            """,
            (
                transaction_reference,
                expires,
                subscription_id,
            ),
        )

        if cur.rowcount != 1:
            conn.rollback()
            cur.close()
            conn.close()
            return False

        cur.execute(
            """
            UPDATE users
            SET
                subscription_status='ACTIVE',
                subscription_expires=%s,
                payment_reference=%s
            WHERE id=%s
            """,
            (
                expires,
                transaction_reference,
                user_id,
            ),
        )

        conn.commit()

        cur.close()
        conn.close()

        logger.info(
            "Activated subscription %s",
            subscription_id,
        )

        return True

    # ==========================================================
    # DEACTIVATE SUBSCRIPTION
    # ==========================================================

    def deactivate_subscription(
        self,
        user_id: int,
    ):

        conn = self._connection()
        cur = conn.cursor()

        cur.execute(
            """
            UPDATE subscriptions
            SET
                status='EXPIRED',
                updated_at=NOW()
            WHERE
                user_id=%s
                AND status='ACTIVE'
            """,
            (user_id,),
        )

        cur.execute(
            """
            UPDATE users
            SET
                subscription_status='FREE',
                subscription_expires=NULL,
                payment_reference=NULL
            WHERE id=%s
            """,
            (user_id,),
        )

        conn.commit()

        cur.close()
        conn.close()

        logger.info(
            "Subscription cancelled for user %s",
            user_id,
        )

        # ==========================================================
    # ADMIN
    # ==========================================================

    def is_admin(
        self,
        user_id: int,
    ):

        conn = self._connection()
        cur = conn.cursor()

        cur.execute(
            """
            SELECT is_admin
            FROM users
            WHERE id=%s
            """,
            (user_id,),
        )

        row = cur.fetchone()

        cur.close()
        conn.close()

        if row is None:
            return False

        return bool(row["is_admin"])

    # ==========================================================
    # PAYMENT FAILURE
    # ==========================================================

    def mark_payment_failed(
        self,
        subscription_id: int,
    ):
        """Record a failed STK payment without changing an active renewal."""

        conn = self._connection()
        cur = conn.cursor()
        cur.execute(
            """
            UPDATE subscriptions
            SET status='FAILED', updated_at=NOW()
            WHERE subscription_id=%s AND status='PENDING'
            """,
            (subscription_id,),
        )

        conn.commit()
        cur.close()
        conn.close()

    # ==========================================================
    # UPDATE CHECKOUT REQUEST
    # ==========================================================

    def update_checkout_request(
        self,
        subscription_id: int,
        merchant_request_id: str,
        checkout_request_id: str,
    ):

        conn = self._connection()
        cur = conn.cursor()

        cur.execute(
            """
            UPDATE subscriptions
            SET
                merchant_request_id=%s,
                checkout_request_id=%s,
                updated_at=NOW()
            WHERE subscription_id=%s
            """,
            (
                merchant_request_id,
                checkout_request_id,
                subscription_id,
            ),
        )

        conn.commit()

        cur.close()
        conn.close()

        logger.info(
            "Saved checkout request for subscription %s",
            subscription_id,
        )

    # ==========================================================
    # UPDATE TRANSACTION REFERENCE
    # ==========================================================

    def update_transaction_reference(
        self,
        subscription_id: int,
        transaction_reference: str,
    ):

        conn = self._connection()
        cur = conn.cursor()

        cur.execute(
            """
            UPDATE subscriptions
            SET
                transaction_reference=%s,
                updated_at=NOW()
            WHERE subscription_id=%s
            """,
            (
                transaction_reference,
                subscription_id,
            ),
        )

        conn.commit()

        cur.close()
        conn.close()

        logger.info(
            "Updated transaction reference for subscription %s",
            subscription_id,
        )

    # ==========================================================
    # LOOKUP BY TRANSACTION REFERENCE
    # ==========================================================

    def get_subscription_by_reference(
        self,
        transaction_reference: str,
    ):

        conn = self._connection()
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
                merchant_request_id,
                checkout_request_id,
                amount,
                currency,
                started_at,
                expires_at,
                created_at,
                updated_at
            FROM subscriptions
            WHERE transaction_reference=%s
            LIMIT 1
            """,
            (transaction_reference,),
        )

        row = cur.fetchone()

        cur.close()
        conn.close()

        if row is None:
            return None

        return dict(row)
    
        # ==========================================================
    # LOOKUP BY CHECKOUT REQUEST ID
    # ==========================================================

    def get_subscription_by_checkout_request(
        self,
        checkout_request_id: str,
    ):

        conn = self._connection()
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
                merchant_request_id,
                checkout_request_id,
                amount,
                currency,
                started_at,
                expires_at,
                created_at,
                updated_at
            FROM subscriptions
            WHERE checkout_request_id=%s
            LIMIT 1
            """,
            (checkout_request_id,),
        )

        row = cur.fetchone()

        cur.close()
        conn.close()

        if row is None:
            return None

        return dict(row)

    # ==========================================================
    # EXPIRE SUBSCRIPTION
    # ==========================================================

    def expire_subscription(
        self,
        subscription_id: int,
    ):

        conn = self._connection()
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
            "Expired subscription %s",
            subscription_id,
        )

    # ==========================================================
    # USER SUBSCRIPTION HISTORY
    # ==========================================================

    def list_user_subscriptions(
        self,
        user_id: int,
    ):

        conn = self._connection()
        cur = conn.cursor()

        cur.execute(
            """
            SELECT
                subscription_id,
                plan,
                status,
                payment_method,
                transaction_reference,
                merchant_request_id,
                checkout_request_id,
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

        subscriptions = []

        for row in rows:

            subscriptions.append({

                "subscription_id": row["subscription_id"],

                "plan": row["plan"],

                "status": row["status"],

                "payment_method": row["payment_method"],

                "transaction_reference": row["transaction_reference"],

                "merchant_request_id": row["merchant_request_id"],

                "checkout_request_id": row["checkout_request_id"],

                "amount": row["amount"],

                "currency": row["currency"],

                "started_at": row["started_at"],

                "expires_at": row["expires_at"],

                "created_at": row["created_at"],

                "updated_at": row["updated_at"],

            })

        return subscriptions


    # ==========================================================
    # RECONCILE STALE PENDING SUBSCRIPTIONS
    # ==========================================================

    def get_stale_pending_subscriptions(self, older_than_minutes: int = 3):
        """
        PENDING subscriptions with a CheckoutRequestID that are old enough
        that Safaricom's callback should have arrived by now (or never will,
        e.g. callback URL unreachable). These are candidates for an active
        M-Pesa status query rather than sitting PENDING forever.
        """

        conn = self._connection()
        cur = conn.cursor()

        cur.execute(
            """
            SELECT subscription_id, checkout_request_id, created_at
            FROM subscriptions
            WHERE status = 'PENDING'
              AND checkout_request_id IS NOT NULL
              AND created_at <= NOW() - (%s * INTERVAL '1 minute')
            ORDER BY created_at ASC
            LIMIT 50;
            """,
            (older_than_minutes,),
        )

        rows = cur.fetchall()
        cur.close()
        conn.close()

        return rows



    def expire_stale_subscriptions(self):
        """
        Flip any ACTIVE subscription whose expires_at has passed to EXPIRED,
        and reset the affected users' cached subscription_status on the
        users table to match. Without this, a lapsed subscription still
        reads as ACTIVE anywhere that trusts users.subscription_status
        directly instead of re-checking expires_at.

        Returns the number of subscriptions expired.
        """

        conn = self._connection()
        cur = conn.cursor()

        cur.execute(
            """
            UPDATE subscriptions
            SET status='EXPIRED', updated_at=NOW()
            WHERE status='ACTIVE' AND expires_at <= NOW()
            RETURNING user_id;
            """
        )

        expired_user_ids = [row["user_id"] for row in cur.fetchall()]

        if expired_user_ids:
            # Only reset users who have no *other* still-active subscription
            # row (relevant after a renewal, where an older row can lapse
            # while a newer one is still current).
            cur.execute(
                """
                UPDATE users
                SET subscription_status='FREE', subscription_expires=NULL
                WHERE id = ANY(%s)
                  AND NOT EXISTS (
                      SELECT 1 FROM subscriptions s
                      WHERE s.user_id = users.id
                        AND s.status = 'ACTIVE'
                        AND s.expires_at > NOW()
                  );
                """,
                (expired_user_ids,),
            )

        conn.commit()
        cur.close()
        conn.close()

        if expired_user_ids:
            logger.info(
                "Expired %d stale subscription(s).",
                len(expired_user_ids),
            )

        return len(expired_user_ids)


subscription_service = SubscriptionService()
