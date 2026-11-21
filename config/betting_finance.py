"""
Tax and minimum-amount rules for betting wallet M-Pesa deposits/withdrawals.

Shared by database/wallet_mpesa_repository.py (applies the tax when moving
money) and api/betting.py (validates the minimums before an STK push / B2C
payout is even attempted), so the two can never drift apart.

Tax is DEDUCTED from the stated amount, not added on top — this mirrors how
Kenya's real betting excise duty actually works (taken from the stake/payout
itself):
  - Deposit KES 100 -> the user is charged 100 via M-Pesa, 5 is kept as tax,
    95 lands in their wallet.
  - Withdraw KES 100 -> the wallet is debited the full 100 (that's what
    "withdrawing KES 100" means to the user), 5 is kept as tax, 95 is what
    actually gets sent to their phone via M-Pesa.
"""

from decimal import Decimal, ROUND_HALF_UP

TWO_PLACES = Decimal("0.01")

# Applies to both deposits and withdrawals, per the product's own rule.
BETTING_TAX_RATE = Decimal("0.05")

MIN_DEPOSIT_KES = Decimal("10")
MIN_WITHDRAWAL_KES = Decimal("100")


def apply_tax(gross_amount):
    """
    Split a gross amount into (tax, net), both rounded to 2dp and summing
    back to the original gross (any rounding remainder is folded into tax,
    so the user's net is never accidentally rounded up at the tax's
    expense).
    """

    gross_amount = Decimal(str(gross_amount))

    tax_amount = (gross_amount * BETTING_TAX_RATE).quantize(
        TWO_PLACES, rounding=ROUND_HALF_UP
    )

    net_amount = gross_amount - tax_amount

    return tax_amount, net_amount
