from pydantic import BaseModel


class FixtureStatistics(BaseModel):

    downloaded: int

    inserted: int

    updated: int

    failed: int


class PredictionStatistics(BaseModel):

    generated: int

    saved: int

    failed: int


class SynchronizationResponse(BaseModel):

    success: bool

    fixtures: FixtureStatistics

    predictions: PredictionStatistics

    total_downloaded: int

    total_predictions: int