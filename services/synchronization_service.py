import logging
from typing import Any

from services.collectors.fetch_upcoming_matches import (
    fetch_upcoming_matches,
)

from database.fixtures_repository import (
    upsert_fixtures,
)

from database.automation_repository import (
    increment_finished_matches,
)

from ml_pipeline.services.prediction_service import (
    prediction_service,
)

logger = logging.getLogger(__name__)


class SynchronizationService:
    """
    Synchronizes real-world football fixtures from football-data.org
    into the local database and generates predictions for newly
    synchronized fixtures.
    """

    def __init__(self):

        self.prediction_service = prediction_service

    # ==========================================================
    # SYNCHRONIZE FIXTURES
    # ==========================================================

    def synchronize(
        self,
        days_ahead: int = 30,
    ) -> dict[str, Any]:

        logger.info(
            "Starting FOOTY254 synchronization..."
        )

        # ------------------------------------------------------
        # STEP 1 : Download fixtures
        # ------------------------------------------------------

        fixtures = fetch_upcoming_matches(days_ahead)

        logger.info(
            "Downloaded %d fixtures.",
            len(fixtures),
        )

        if not fixtures:

            logger.warning(
                "No fixtures were downloaded."
            )

            return {
                "success": False,
                "message": "No fixtures downloaded.",
                "fixtures": {},
                "predictions": {},
                "total_downloaded": 0,
            }
        
        logger.info(
            "Downloaded %d fixtures.",
            len(fixtures),
)

        # ------------------------------------------------------
        # STEP 2 : Synchronize database
        # ------------------------------------------------------

        fixture_stats = upsert_fixtures(fixtures)

        fixtures_to_predict = (
            fixture_stats.get(
                "fixtures_to_predict",
                [],
            )
        )

        newly_finished = fixture_stats.get(
            "newly_finished",
            [],
        )

        logger.info(
            "%d fixtures have just finished.",
            len(newly_finished),
        )

        if newly_finished:

            increment_finished_matches(
                len(newly_finished)
            )

            logger.info(
                "%d finished fixtures added to training queue.",
                len(newly_finished),
            )

        logger.info(
            "%d fixtures require predictions.",
            len(fixtures_to_predict),
        )

        logger.info(
            "Fixtures synchronized."
        )

        # ------------------------------------------------------
        # STEP 3 : Generate predictions
        # ------------------------------------------------------

        prediction_stats = (
            self.prediction_service.generate_predictions()
        )

        logger.info(
            "Synchronization completed successfully."
        )

        # ------------------------------------------------------
        # RESPONSE
        # ------------------------------------------------------

        return {

                "prediction_summary": {

                "generated": prediction_stats.get("generated", 0),

                "saved": prediction_stats.get("saved", 0),

                "skipped": prediction_stats.get("skipped", 0),

                "failed": prediction_stats.get("failed", 0),

            },
        }

    # ==========================================================
    # QUICK HEALTH CHECK
    # ==========================================================

    def ping(self) -> dict[str, Any]:

        return {
            "service": "SynchronizationService",
            "status": "healthy",
        }

    # ==========================================================
    # SINGLETON
    # ==========================================================


synchronization_service = SynchronizationService()