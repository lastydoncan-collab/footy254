import logging

from database.fixtures_repository import (
    get_fixtures_needing_predictions,
)

from database.predictions_repository import (
    save_prediction,
)

from ml_pipeline.core.model_loader import (
    load_all_cached,
    reload_model,
)

from ml_pipeline.core.predict_engine import (
    PredictionEngine,
)

logger = logging.getLogger(__name__)

from datetime import datetime, timedelta, timezone

PREDICTION_WINDOW_DAYS = 30


class PredictionService:
    """
    Generates and stores predictions.

    The engine is built lazily and rebuilt whenever the underlying model
    artifacts change (e.g. after retraining), so importing this module never
    loads the 60MB+ model and no caller can hold a stale engine.
    """

    def __init__(self):
        self._engine = None
        self._assets = None

    @property
    def engine(self):
        assets = load_all_cached()

        if self._engine is None or assets is not self._assets:
            logger.info("Loading prediction engine...")

            self._engine = PredictionEngine(
                model=assets["model"],
                scaler=assets["scaler"],
                encoder=assets["encoder"],
                elo=assets["elo"],
                team_stats=assets["team_stats"],
            )
            self._assets = assets

            logger.info("Prediction engine ready.")

        return self._engine

    def reload(self):
        logger.info("Reloading prediction engine...")

        reload_model()

        # Next access to .engine rebuilds it from the fresh artifacts.
        self._engine = None
        self._assets = None

        _ = self.engine

        logger.info("Prediction engine reloaded.")

    # =====================================================
    # FIXTURE ELIGIBILITY
    # =====================================================

    def is_prediction_eligible(self, fixture):
        kickoff = fixture.get("kickoff")
        status = fixture.get("status")

        if kickoff is None:
            return False

        if kickoff.tzinfo is None:
            kickoff = kickoff.replace(tzinfo=timezone.utc)

        kickoff = kickoff.astimezone(timezone.utc)

        now = datetime.now(timezone.utc)
        window_end = now + timedelta(days=PREDICTION_WINDOW_DAYS)

        if status not in ("SCHEDULED", "TIMED"):
            return False

        return now <= kickoff <= window_end

    # =====================================================
    # PREDICT ONE FIXTURE
    # =====================================================

    def predict_fixture(self, fixture):
        if not self.is_prediction_eligible(fixture):
            logger.info(
                "Skipping fixture %s (%s vs %s)",
                fixture["match_id"],
                fixture["home_team"],
                fixture["away_team"],
            )
            return None

        prediction = self.engine.predict(
            fixture["home_team"],
            fixture["away_team"],
        )

        if prediction is None:
            logger.warning(
                "No prediction returned for %s vs %s",
                fixture["home_team"],
                fixture["away_team"],
            )
            return None

        save_prediction(
            fixture["match_id"],
            prediction,
        )

        logger.info(
            "Generating prediction for %s vs %s",
            fixture["home_team"],
            fixture["away_team"],
        )

        return prediction

    # =====================================================
    # BULK PREDICTIONS
    # =====================================================

    def generate_predictions(self):

        fixtures = get_fixtures_needing_predictions()

        logger.info(

            "Found %d fixtures requiring predictions.",

            len(fixtures),

        )

        generated = 0
        failed = 0
        skipped = 0
        errors = []

        for fixture in fixtures:

            try:

                prediction = self.predict_fixture(fixture)

                if prediction is None:

                    skipped += 1
                    continue

                generated += 1

            except Exception as exc:

                failed += 1

                logger.exception(

                    "Prediction failed for Match %s",

                    fixture["match_id"],

                )

                errors.append({

                    "match_id": fixture["match_id"],

                    "home_team": fixture["home_team"],

                    "away_team": fixture["away_team"],

                    "error": str(exc),

                })

        logger.info(

            "Prediction job complete."

        )

        logger.info(

            "Generated : %d",

            generated,

        )

        logger.info(

            "Failed : %d",

            failed,

        )
        return {

            "processed": generated + failed + skipped,

            "generated": generated,

            "saved": generated,

            "skipped": skipped,

            "failed": failed,

            "errors": errors,

        }


prediction_service = PredictionService()