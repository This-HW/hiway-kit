"""Price calculation for the checkout."""

MAX_DISCOUNT_RATE = 0.5


def discounted_price(price_cents, rate):
    """Apply a fractional discount rate to a price in cents, capped at 50%."""
    rate = min(rate, MAX_DISCOUNT_RATE)
    return round(price_cents * (1 - rate))
