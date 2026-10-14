from datetime import date, datetime, time
from typing import Optional

from pydantic import BaseModel


class FixtureResponse(BaseModel):

    match_id: int

    competition_id: int

    competition: str

    competition_code: str

    season: int

    matchday: Optional[int] = None

    stage: Optional[str] = None

    home_team_id: int

    away_team_id: int

    home_team: str

    away_team: str

    utc_date: datetime

    match_date: date

    kickoff_time: time

    kickoff: datetime

    status: str

    score_home: Optional[int] = None

    score_away: Optional[int] = None

    winner: Optional[str] = None

    last_updated: Optional[datetime] = None

    class Config:

        from_attributes = True


class FixtureListResponse(BaseModel):

    count: int

    fixtures: list[FixtureResponse]