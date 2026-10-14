from decimal import Decimal

# ==========================================================
# FOOTY254 SUBSCRIPTION PLANS
# ==========================================================

SUBSCRIPTION_PLANS = {
    "MONTHLY": {
        "name": "Premium Monthly",
        "price": Decimal("499.00"),
        "currency": "KES",
        "duration_days": 30,
    },
    "QUARTERLY": {
        "name": "Premium Quarterly",
        "price": Decimal("1299.00"),
        "currency": "KES",
        "duration_days": 90,
    },
    "ANNUAL": {
        "name": "Premium Annual",
        "price": Decimal("4499.00"),
        "currency": "KES",
        "duration_days": 365,
    },
}


# ==========================================================
# HELPERS
# ==========================================================

def get_plan(plan: str):
    """
    Returns a subscription plan or None.
    """

    if not plan:
        return None

    return SUBSCRIPTION_PLANS.get(plan.upper())


def get_duration(plan: str) -> int:
    """
    Returns duration in days.
    """

    selected = get_plan(plan)

    if selected is None:
        raise ValueError(f"Unknown subscription plan: {plan}")

    return selected["duration_days"]


def get_price(plan: str):
    """
    Returns Decimal price.
    """

    selected = get_plan(plan)

    if selected is None:
        raise ValueError(f"Unknown subscription plan: {plan}")

    return selected["price"]


def get_currency(plan: str):
    """
    Returns plan currency.
    """

    selected = get_plan(plan)

    if selected is None:
        raise ValueError(f"Unknown subscription plan: {plan}")

    return selected["currency"]


def list_plans():
    """
    Returns all plans for the frontend.
    """

    plans = []

    for plan_id, plan in SUBSCRIPTION_PLANS.items():

        plans.append(
            {
                "id": plan_id.lower(),
                "name": plan["name"],
                "price": float(plan["price"]),
                "currency": plan["currency"],
                "duration_days": plan["duration_days"],
            }
        )

    return plans