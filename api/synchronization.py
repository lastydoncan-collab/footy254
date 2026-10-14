import logging

from fastapi import APIRouter, Depends, HTTPException

from services.synchronization_service import synchronization_service
from services.collectors.fetch_upcoming_matches import fetch_upcoming_matches

from database.fixtures_repository import (
    upsert_fixtures,
)

from ml_pipeline.services.prediction_service import prediction_service
from ml_pipeline.core.model_loader import model_status
from security.dependencies import require_admin

router = APIRouter(
    prefix="/sync",
    tags=["Synchronization"],
)

logger = logging.getLogger(__name__)

sync_service = synchronization_service


# ==========================================================
# FULL SYNCHRONIZATION
# ==========================================================

@router.post("/")
def synchronize(days_ahead: int = 30, current_user=Depends(require_admin)):

    try:

        result = sync_service.synchronize(days_ahead)

        return {
            "success": True,
            "days_ahead": days_ahead,
            "result": result,
        }

    except Exception as exc:

        logger.exception("Synchronization failed")

        raise HTTPException(
            status_code=500,
            detail=str(exc),
        )


# ==========================================================
# DOWNLOAD FIXTURES ONLY
# ==========================================================

@router.post("/fixtures")
def synchronize_fixtures(days_ahead: int = 30, current_user=Depends(require_admin)):

    try:

        fixtures = fetch_upcoming_matches(days_ahead)

        sync_result = upsert_fixtures(fixtures)

        return {
            "success": True,
            "downloaded": len(fixtures),
            "result": sync_result,
        }

    except Exception as exc:

        logger.exception("Fixture synchronization failed")

        raise HTTPException(
            status_code=500,
            detail=str(exc),
        )


# ==========================================================
# GENERATE PREDICTIONS
# ==========================================================

@router.post("/predictions")
def synchronize_predictions(current_user=Depends(require_admin)):

    try:

        result = prediction_service.generate_predictions()
        logger.info("Prediction generation complete.")

        return {
            "success": True,
            "result": result,
        }

    except Exception as exc:

        logger.exception("Prediction synchronization failed")

        raise HTTPException(
            status_code=500,
            detail=str(exc),
        )
    

# ==========================================================
# FIXTURE LIFECYCLE PIPELINE
# ==========================================================

@router.post("/pipeline")
def run_pipeline(days_ahead: int = 30, current_user=Depends(require_admin)):

    try:

        sync_result = sync_service.synchronize(days_ahead)

        prediction_result = prediction_service.generate_predictions()

        return {

            "success": True,

            "days_ahead": days_ahead,

            "prediction_window": 30,

            "sync": sync_result,

            "predictions": prediction_result,

        }

    except Exception as exc:

        logger.exception("Pipeline execution failed")

        raise HTTPException(
            status_code=500,
            detail=str(exc),
        )


# ==========================================================
# SYSTEM STATUS
# ==========================================================

@router.get("/status")
def synchronization_status():

    return {
        "service": "FOOTY254 Synchronization Service",
        "status": "running",
        "model": model_status(),
        "pipeline": {

        "fixture_download": True,

        "prediction_engine": True,

        "prediction_window_days": 30,

        "automatic_lifecycle": True,

    },
        "description":
            "Synchronizes Football-Data API fixtures, updates PostgreSQL and generates AI predictions.",
    }
