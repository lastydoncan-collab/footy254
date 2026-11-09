from datetime import datetime
from decimal import Decimal
from typing import List, Literal, Optional

from pydantic import BaseModel, Field

Pick = Literal["HOME", "DRAW", "AWAY"]


# ==========================================================
# ODDS
# ==========================================================

class OddsResponse(BaseModel):

    match_id: int

    home_odds: Decimal
    draw_odds: Decimal
    away_odds: Decimal

    margin: Decimal
    generated_at: datetime

    class Config:
        from_attributes = True


class OddsBoardEntry(OddsResponse):

    home_team: str
    away_team: str
    competition: Optional[str] = None
    kickoff: Optional[datetime] = None
    fixture_status: str


# ==========================================================
# BET SLIPS
# ==========================================================

class PlaceSingleBetRequest(BaseModel):

    match_id: int
    pick: Pick
    stake: Decimal = Field(gt=0)
    idempotency_key: Optional[str] = Field(default=None, max_length=100)


class MultiBetLeg(BaseModel):

    match_id: int
    pick: Pick


class PlaceMultiBetRequest(BaseModel):

    legs: List[MultiBetLeg] = Field(min_length=2)
    stake: Decimal = Field(gt=0)
    idempotency_key: Optional[str] = Field(default=None, max_length=100)


class BetLegResponse(BaseModel):

    id: int
    match_id: int
    pick: Pick
    odds: Decimal
    status: str
    home_team: Optional[str] = None
    away_team: Optional[str] = None
    kickoff: Optional[datetime] = None

    class Config:
        from_attributes = True


class BetSlipResponse(BaseModel):

    id: int
    user_id: int
    bet_type: Literal["SINGLE", "MULTI"]
    stake: Decimal
    combined_odds: Decimal
    potential_payout: Decimal
    status: Literal["PENDING", "WON", "LOST", "VOID"]
    payout: Optional[Decimal] = None
    placed_at: datetime
    settled_at: Optional[datetime] = None
    legs: List[BetLegResponse] = []

    class Config:
        from_attributes = True


class BetSlipListResponse(BaseModel):

    count: int
    bet_slips: List[BetSlipResponse]


# ==========================================================
# WALLET
# ==========================================================

class WalletResponse(BaseModel):

    user_id: int
    balance: Decimal
    currency: str
    updated_at: datetime

    class Config:
        from_attributes = True


class WalletTransactionResponse(BaseModel):

    id: int
    type: str
    amount: Decimal
    balance_after: Decimal
    reference: Optional[str] = None
    description: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True


class WalletTransactionListResponse(BaseModel):

    count: int
    transactions: List[WalletTransactionResponse]


# ==========================================================
# JACKPOTS
# ==========================================================

class JackpotFixtureResponse(BaseModel):

    match_id: int
    sequence: int
    home_team: str
    away_team: str
    kickoff: Optional[datetime] = None


class JackpotResponse(BaseModel):

    id: int
    name: str
    stake_amount: Decimal
    status: Literal["OPEN", "CLOSED", "SETTLED"]
    opens_at: Optional[datetime] = None
    closes_at: Optional[datetime] = None
    fixtures: List[JackpotFixtureResponse] = []

    class Config:
        from_attributes = True


class JackpotTierRequest(BaseModel):

    min_correct: int = Field(ge=1)
    payout_multiplier: Decimal = Field(ge=0)


class JackpotCreateRequest(BaseModel):

    name: str
    stake_amount: Decimal = Field(gt=0)
    match_ids: List[int] = Field(min_length=2)
    tiers: List[JackpotTierRequest] = Field(min_length=1)
    opens_at: Optional[datetime] = None
    closes_at: Optional[datetime] = None


class JackpotEntryRequest(BaseModel):

    picks: dict[int, Pick]


class JackpotEntryResponse(BaseModel):

    id: int
    jackpot_id: int
    user_id: int
    stake: Decimal
    status: Literal["PENDING", "SETTLED"]
    correct_count: Optional[int] = None
    payout: Optional[Decimal] = None
    placed_at: datetime
    settled_at: Optional[datetime] = None

    class Config:
        from_attributes = True
