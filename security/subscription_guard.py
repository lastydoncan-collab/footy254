from datetime import datetime, timezone

from fastapi import Depends, HTTPException

from security.dependencies import get_current_user

from services.subscription_service import subscription_service


def require_active_subscription(
    current_user=Depends(get_current_user),
):
    """
    Allows:
        - Admins
        - Users with an ACTIVE, unexpired subscription

    Blocks (403):
        - Free users
        - Expired / failed / pending subscriptions
    """

    # Administrator bypass
    if current_user.get("is_admin"):
        return current_user

    subscription = subscription_service.get_subscription(current_user["id"])

    if subscription is None:
        raise HTTPException(
            status_code=403,
            detail="Premium subscription required.",
        )

    if subscription["status"] != "ACTIVE":
        raise HTTPException(
            status_code=403,
            detail="Subscription inactive.",
        )

    expires = subscription.get("expires_at")

    if expires is not None:
        # Compare in UTC whether the driver returned an aware or naive value.
        if expires.tzinfo is None:
            expires = expires.replace(tzinfo=timezone.utc)

        if expires <= datetime.now(timezone.utc):
            raise HTTPException(
                status_code=403,
                detail="Subscription expired.",
            )

    return current_user
