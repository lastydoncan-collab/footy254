from database.db_config import get_connection


# ==========================================================
# CREATE SUBSCRIPTION
# ==========================================================

def create_subscription(
    user_id,
    plan,
    status,
    payment_method,
    transaction_reference,
    amount,
    currency,
    started_at,
    expires_at,
):

    with get_connection() as conn:

        with conn.cursor() as cur:

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
                    %s,%s,%s,%s,%s,%s,%s,%s,%s
                )

                RETURNING subscription_id;
                """,
                (
                    user_id,
                    plan,
                    status,
                    payment_method,
                    transaction_reference,
                    amount,
                    currency,
                    started_at,
                    expires_at,
                ),
            )

            subscription = cur.fetchone()

        conn.commit()

    return subscription

# ==========================================================
# GET USER SUBSCRIPTION
# ==========================================================

def get_subscription(user_id):

    with get_connection() as conn:

        with conn.cursor() as cur:

            cur.execute(
                """
                SELECT *

                FROM subscriptions

                WHERE user_id=%s

                ORDER BY subscription_id DESC

                LIMIT 1;
                """,
                (user_id,),
            )

            return cur.fetchone()
        
# ==========================================================
# ACTIVE SUBSCRIPTION
# ==========================================================

def has_active_subscription(user_id):

    with get_connection() as conn:

        with conn.cursor() as cur:

            cur.execute(
                """
                SELECT EXISTS(

                    SELECT 1

                    FROM subscriptions

                    WHERE

                        user_id=%s

                        AND status='ACTIVE'

                        AND expires_at > NOW()

                );
                """,
                (user_id,),
            )

            return cur.fetchone()["exists"]
        
# ==========================================================
# UPDATE SUBSCRIPTION STATUS
# ==========================================================

def update_subscription_status(
    subscription_id,
    status,
):

    with get_connection() as conn:

        with conn.cursor() as cur:

            cur.execute(
                """
                UPDATE subscriptions

                SET

                    status=%s,
                    updated_at=NOW()

                WHERE subscription_id=%s;
                """,
                (
                    status,
                    subscription_id,
                ),
            )

        conn.commit()

# ==========================================================
# EXPIRE SUBSCRIPTIONS
# ==========================================================

def expire_subscriptions():

    with get_connection() as conn:

        with conn.cursor() as cur:

            cur.execute(
                """
                UPDATE subscriptions

                SET

                    status='EXPIRED',
                    updated_at=NOW()

                WHERE

                    status='ACTIVE'

                    AND expires_at <= NOW();
                """
            )

        conn.commit()

# ==========================================================
# UPDATE USER SUBSCRIPTION
# ==========================================================

def update_user_subscription(

    user_id,

    status,

    expires_at,

    payment_provider,

    payment_reference,

):

    with get_connection() as conn:

        with conn.cursor() as cur:

            cur.execute(
                """
                UPDATE users

                SET

                    subscription_status=%s,
                    subscription_expires=%s,
                    payment_provider=%s,
                    payment_reference=%s

                WHERE id=%s;
                """,
                (
                    status,
                    expires_at,
                    payment_provider,
                    payment_reference,
                    user_id,
                ),
            )

        conn.commit()