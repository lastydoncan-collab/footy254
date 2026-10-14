import logging

from datetime import datetime, timedelta
from functools import wraps
import zlib

from apscheduler.schedulers.background import BackgroundScheduler

from services.synchronization_service import synchronization_service
from ml_pipeline.dataset_builder import build_dataset
from ml_pipeline.train_model import train
from services.automation_service import automation_service
from services.subscription_service import subscription_service
from services.mpesa_service import mpesa_service

from config import settings
from database.db_config import get_raw_connection
from database.auth_tokens_repository import purge_expired_tokens
from database.login_attempts_repository import purge_stale_attempts

from database.automation_repository import (
    get_finished_match_counter,
    reset_finished_counter,
)

RETRAIN_THRESHOLD = 10

logger = logging.getLogger(__name__)

scheduler = BackgroundScheduler(
    job_defaults={
        # A slow job (e.g. retraining) must never overlap itself, and missed
        # runs after a restart collapse into one.
        "max_instances": 1,
        "coalesce": True,
        "misfire_grace_time": 300,
    }
)


def exclusive(name: str):
    """
    Run a job on only ONE process at a time.

    With several uvicorn workers (or containers) every process starts its own
    scheduler, which would otherwise run each job N times (duplicate API calls,
    concurrent retraining). A PostgreSQL session advisory lock, taken on a
    dedicated connection and held for the job's duration, lets exactly one
    process run it; the others skip that tick.
    """

    # crc32, NOT hash(): str hashes are randomised per process, which would
    # give every worker a different key and defeat the lock.
    lock_key = zlib.crc32(f"footy254-job:{name}".encode())

    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            try:
                conn = get_raw_connection()
            except Exception:
                logger.exception("Job %s skipped: database unavailable.", name)
                return None

            try:
                conn.autocommit = True

                with conn.cursor() as cur:
                    cur.execute("SELECT pg_try_advisory_lock(%s) AS got", (lock_key,))

                    if not cur.fetchone()["got"]:
                        logger.debug("Job %s already running elsewhere; skipped.", name)
                        return None

                return func(*args, **kwargs)
            finally:
                conn.close()  # closing the session releases the advisory lock

        return wrapper

    return decorator


def sync_job():

    logger.info("===== Automatic Football Sync Started =====")

    try:

        result = synchronization_service.synchronize(
            days_ahead=30
        )

        logger.info(
            "Football synchronization completed successfully."
        )

        logger.info(result)

    except Exception:

        logger.exception(
            "Automatic synchronization failed."
        )


def retrain_job():

    finished = get_finished_match_counter()

    logger.info(
        "Finished fixtures waiting: %d",
        finished,
    )

    if finished < RETRAIN_THRESHOLD:

        logger.info(
            "Retraining skipped."
        )

        return

    logger.info(
        "Starting automatic retraining..."
    )

    try:

        build_dataset()

        # ``train`` owns dataset loading, feature preparation, artifact
        # persistence, and metadata updates.  Calling ``train_model`` here
        # bypasses those steps and requires feature matrices as arguments.
        train()

        from ml_pipeline.services.prediction_service import (
            prediction_service,
        )

        prediction_service.generate_predictions()

        prediction_service.reload()

        reset_finished_counter()

        logger.info(
            "Automatic retraining completed."
        )

    except Exception:

        logger.exception(
            "Automatic retraining failed."
        )


def expire_subscriptions_job():
    """
    Nothing previously called SubscriptionService.expire_subscription(), so a
    lapsed subscription's status column stayed 'ACTIVE' in the database
    forever (has_active_subscription() re-checks expires_at, so access
    control wasn't broken — but subscription history, admin views, and
    anything trusting the stored status directly would show it as live).
    """

    try:

        subscription_service.expire_stale_subscriptions()

    except Exception:

        logger.exception(
            "Failed to expire stale subscriptions."
        )


def reconcile_pending_payments_job():
    """
    Some PENDING subscriptions never get resolved by the callback route —
    the callback URL can be unreachable (common in local/dev setups without
    a public tunnel), or Safaricom's retries can be exhausted. Left alone,
    these sit PENDING forever and the frontend's status-polling times out
    with no way to ever resolve. This actively asks Daraja for the real
    status instead of only waiting to be told.
    """

    try:

        stale = subscription_service.get_stale_pending_subscriptions(
            older_than_minutes=3
        )

        if not stale:
            return

        logger.info(
            "Reconciling %d stale PENDING subscription(s).",
            len(stale),
        )

        for row in stale:

            subscription_id = row["subscription_id"]
            checkout_request_id = row["checkout_request_id"]

            try:
                result = mpesa_service.query_transaction(checkout_request_id)
            except Exception:
                logger.exception(
                    "Status query failed for subscription %s.",
                    subscription_id,
                )
                continue

            result_code = result.get("ResultCode")

            # "1032" = cancelled by user, "1037" = timeout, "0" = success.
            # Anything else Safaricom returns for a still-pending push (e.g.
            # ResultCode missing / request still in flight) is left alone.
            if result_code is None:
                continue

            result_code = str(result_code)

            if result_code == "0":
                # Genuinely paid but our callback never arrived for it.
                # There's no receipt number in this query response, so we
                # can't safely auto-activate here without duplicating the
                # callback's amount-verification logic; flag it loudly for
                # manual reconciliation instead of guessing.
                logger.warning(
                    "Subscription %s shows PAID via query but was never "
                    "activated by callback — needs manual review.",
                    subscription_id,
                )
                continue

            if result_code in ("1032", "1037"):
                subscription_service.mark_payment_failed(subscription_id)
                logger.info(
                    "Marked subscription %s FAILED (M-Pesa result_code=%s).",
                    subscription_id,
                    result_code,
                )

    except Exception:

        logger.exception(
            "Failed to reconcile stale pending subscriptions."
        )


def purge_auth_data_job():
    """Delete long-dead refresh/reset tokens and stale login-attempt rows."""

    try:
        removed = purge_expired_tokens()
        removed["login_attempts"] = purge_stale_attempts()
        logger.info("Auth housekeeping removed: %s", removed)
    except Exception:
        logger.exception("Auth housekeeping failed.")


def start_scheduler():
    if scheduler.running:
        return

    scheduler.add_job(
        exclusive("automation")(automation_service.run),
        "interval",
        minutes=20,
        id="automation",
        replace_existing=True,
        # First sync shortly after boot so a fresh deployment fills itself
        # instead of staying empty for the first 20 minutes.
        next_run_time=datetime.now() + timedelta(seconds=45),
    )

    scheduler.add_job(
        exclusive("expire_subscriptions")(expire_subscriptions_job),
        "interval",
        minutes=30,
        id="expire_subscriptions",
        replace_existing=True,
        next_run_time=datetime.now(),
    )

    scheduler.add_job(
        exclusive("reconcile_pending_payments")(reconcile_pending_payments_job),
        "interval",
        minutes=5,
        id="reconcile_pending_payments",
        replace_existing=True,
    )

    scheduler.add_job(
        exclusive("purge_auth_data")(purge_auth_data_job),
        "interval",
        hours=24,
        id="purge_auth_data",
        replace_existing=True,
        next_run_time=datetime.now() + timedelta(minutes=2),
    )

    scheduler.start()

    logger.info("Scheduler started.")

def stop_scheduler():
    if scheduler.running:
        scheduler.shutdown(wait=False)

        logger.info("Scheduler stopped.")
