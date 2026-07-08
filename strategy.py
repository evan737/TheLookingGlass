def calculate_basic_edge(market):
    yes_bid = market.get("yes_bid")
    yes_ask = market.get("yes_ask")
    last_price = market.get("last_price")

    if yes_bid is not None and yes_ask is not None:
        spread = yes_ask - yes_bid

        if spread <= 3:
            return "Tight market"
        if spread <= 8:
            return "Medium spread"

        return "Wide spread"

    if last_price is not None:
        return f"No bid/ask, last traded at {last_price}¢"

    return "No pricing data"