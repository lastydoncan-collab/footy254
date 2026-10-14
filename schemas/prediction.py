from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class ProbabilityResponse(BaseModel):

    home_win: float

    draw: float

    away_win: float


class XGResponse(BaseModel):

    home: float

    away: float


class PredictionResponse(BaseModel):

    match_id: int

    prediction: str

    home_win: float

    draw: float

    away_win: float

    xg_home: float

    xg_away: float

    generated_at: datetime

    class Config:

        from_attributes = True


class PredictionListResponse(BaseModel):

    count: int

    predictions: list[PredictionResponse]