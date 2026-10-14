import logging

logger = logging.getLogger(__name__)


def sync_football_data():

    logger.info("Running automatic football sync")


def process_finished_matches():

    logger.info("Processing finished fixtures")


def retrain_model():

    logger.info("Retraining prediction model")


def refresh_predictions():

    logger.info("Refreshing predictions")


def expire_subscriptions():

    logger.info("Checking expired subscriptions")