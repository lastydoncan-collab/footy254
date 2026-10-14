import logging

from services.synchronization_service import synchronization_service

from database.automation_repository import (
    get_finished_match_counter,
    reset_finished_counter,
)

from ml_pipeline.dataset_builder import build_dataset
from ml_pipeline.train_model import train

from ml_pipeline.services.prediction_service import (
    prediction_service,
)

logger = logging.getLogger(__name__)

RETRAIN_THRESHOLD = 10


class AutomationService:

    def __init__(self):

        self.sync = synchronization_service

    def run(self):

        logger.info(
            "========== FOOTY254 Automation =========="
        )

        try:

            self.sync.synchronize()

        except Exception:

            logger.exception(
                "Synchronization failed."
            )

            return

        finished = get_finished_match_counter()

        logger.info(
            "Finished fixtures waiting: %d",
            finished,
        )

        if finished < RETRAIN_THRESHOLD:

            logger.info(
                "Training skipped."
            )

            return

        logger.info(
            "Building dataset..."
        )

        build_dataset()

        logger.info(
            "Training model..."
        )

        # Run the complete pipeline after the dataset has been rebuilt.
        train()

        logger.info(
            "Reloading AI..."
        )

        prediction_service.reload()

        logger.info(
            "Generating predictions..."
        )

        prediction_service.generate_predictions()

        reset_finished_counter()

        logger.info(
            "Automation cycle complete."
        )


automation_service = AutomationService()
