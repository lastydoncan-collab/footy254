from fastapi import APIRouter, HTTPException

from database.predictions_repository import (
    get_all_predictions,
    get_latest_predictions,
    get_prediction,
    get_predictions_with_fixtures,
)

from ml_pipeline.services.prediction_service import (
    prediction_service,
)

from fastapi import Depends

from security.subscription_guard import (
    require_active_subscription,
)
from security.dependencies import require_admin

router = APIRouter(
    prefix="/predictions",
    tags=["Predictions"],
)

# ==========================================================
# GENERATE NEW PREDICTIONS
# ==========================================================

@router.post("/generate")
def generate_predictions(
    current_user=Depends(require_admin),
):

    result = prediction_service.generate_predictions()

    return {
        "success": True,
        "message": "Prediction generation completed.",
        **result,
    }


# ==========================================================
# ALL PREDICTIONS
# ==========================================================

@router.get("/")
def all_predictions(
    current_user=Depends(
        require_active_subscription,
    ),
):

    predictions = get_predictions_with_fixtures()

    return {
        "count": len(predictions),
        "predictions": predictions,
    }


# ==========================================================
# RAW DATABASE PREDICTIONS
# ==========================================================

@router.get("/database/all")
def raw_predictions(
    current_user=Depends(
        require_active_subscription,
    ),
):

    predictions = get_latest_predictions(limit=500)

    return {
        "count": len(predictions),
        "predictions": predictions,
    }


# ==========================================================
# SYSTEM STATUS
# ==========================================================

@router.get("/status")
def prediction_status():

    predictions = get_all_predictions()

    return {
        "prediction_count": len(predictions),
        "status": "ready",
    }

# ==========================================================
# SINGLE PREDICTION
# ==========================================================

@router.get("/{match_id}")
def prediction(
    match_id: int,
    current_user=Depends(
        require_active_subscription,
    ),
):

    prediction = get_prediction(match_id)

    if prediction is None:
        raise HTTPException(
            status_code=404,
            detail="Prediction not found.",
        )

    return prediction
