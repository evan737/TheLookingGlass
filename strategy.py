def dollars_to_cents(value):
    if value is None:
        return None
    return float(value) * 100


def analyze_market(market, category):
    yes_bid = dollars_to_cents(market.get("yes_bid_dollars"))
    yes_ask = dollars_to_cents(market.get("yes_ask_dollars"))
    last_price = dollars_to_cents(market.get("last_price_dollars"))
    volume = float(market.get("volume_fp") or 0)

    if yes_bid == 0 and yes_ask == 0 and last_price == 0:
        return {
            "decision": "SKIP",
            "reason": "No active pricing",
        }

    if volume < 100:
        return {
            "decision": "SKIP",
            "reason": "Low volume",
        }

    if yes_bid is not None and yes_ask is not None:
        spread = yes_ask - yes_bid

        if spread > 10:
            return {
                "decision": "SKIP",
                "reason": f"Spread too wide: {spread:.1f}¢",
            }

        return {
            "decision": "WATCH",
            "reason": f"Tradable spread: {spread:.1f}¢",
        }

    return {
        "decision": "WATCH",
        "reason": "Has pricing data",
    }