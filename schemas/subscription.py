from datetime import datetime
from decimal import Decimal
from typing import Optional, Literal

from pydantic import BaseModel, field_validator


# ==========================================================
# CREATE SUBSCRIPTION REQUEST
# ==========================================================

class SubscriptionCreate(BaseModel):

    plan: Literal["MONTHLY", "QUARTERLY", "ANNUAL"]

    payment_method: Literal["MPESA"] = "MPESA"

    phone_number: str

    @field_validator("plan", "payment_method", mode="before")
    @classmethod
    def _uppercase(cls, value: str) -> str:
        return value.strip().upper() if isinstance(value, str) else value

    @field_validator("phone_number")
    @classmethod
    def _validate_phone(cls, value: str) -> str:
        # Imported here (not at module load) to avoid a circular import
        # between schemas and services.
        from services.mpesa_service import mpesa_service

        if not mpesa_service.is_valid_phone_number(value):
            raise ValueError(
                "Enter a valid Safaricom number, e.g. 0712345678 or 254712345678."
            )

        return value


# ==========================================================
# SUBSCRIPTION RESPONSE
# ==========================================================

class SubscriptionResponse(BaseModel):

    subscription_id: int

    user_id: int

    plan: str

    status: str

    payment_method: Optional[str] = None

    transaction_reference: Optional[str] = None

    amount: Optional[Decimal] = None

    currency: Optional[str] = None

    started_at: Optional[datetime] = None

    expires_at: Optional[datetime] = None

    created_at: Optional[datetime] = None

    updated_at: Optional[datetime] = None


# ==========================================================
# PAYMENT CALLBACK
# ==========================================================

class PaymentCallback(BaseModel):

    transaction_reference: str

    payment_provider: str

    status: str


# ==========================================================
# SUBSCRIPTION STATUS
# ==========================================================

class SubscriptionStatus(BaseModel):

    is_active: bool

    plan: str

    status: str

    expires_at: Optional[datetime]


class CheckoutRequest(BaseModel):

    plan_id: str

    phone: str


class CheckoutResponse(BaseModel):

    success: bool

    checkout_id: str

    message: str
