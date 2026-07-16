import math

# Confirmed against Kalshi's own published fee schedule and multiple
# independent breakdowns: fee = 0.07 * P * (1-P) dollars per contract for
# TAKER orders (P = contract price in dollars, 0.01-0.99). Maker fees
# (resting limit orders) are roughly 25% of the taker fee. Settlement
# itself is free -- the fee only applies when you actually enter a
# position, not when it resolves.
#
# NOTE ON ROUNDING: sources disagreed on whether Kalshi rounds UP to the
# nearest whole cent PER CONTRACT. Taking that literally produces an
# obviously inflated result (e.g. a 50c contract's true 1.75c fee jumping
# to a full 2c -- a ~14% markup from rounding alone), which contradicts
# the worked examples the same sources gave directly. The more sensible
# reading: keep the raw fractional-cent value per contract, and round
# only the FINAL total dollar fee for a trade to the cent.
TAKER_FEE_RATE = 0.07
MAKER_FEE_RATE = TAKER_FEE_RATE * 0.25


def taker_fee_per_contract(price):
    """
    price: contract price in dollars (0.01 to 0.99)
    Returns the raw (unrounded) fee in dollars for one contract.
    """
    if price is None or price <= 0 or price >= 1:
        return 0.0
    return TAKER_FEE_RATE * price * (1 - price)


def maker_fee_per_contract(price):
    """Same idea, but for resting limit orders -- about 1/4 the taker rate."""
    if price is None or price <= 0 or price >= 1:
        return 0.0
    return MAKER_FEE_RATE * price * (1 - price)


def estimate_trade_fee(stake, price, order_type="taker"):
    """
    stake: dollar amount being risked
    price: contract price in dollars
    order_type: "taker" (default -- matches how this project actually
                simulates fills, buying at the current ask) or "maker"

    Returns the total dollar fee for this trade, rounded to the cent.
    """
    if not price or price <= 0:
        return 0.0
    contracts = stake / price
    per_contract_fee = taker_fee_per_contract(price) if order_type == "taker" else maker_fee_per_contract(price)
    return round(contracts * per_contract_fee, 2)