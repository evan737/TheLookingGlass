from probability_model import bracket_probability
from claims_forecast import get_claims_forecast

CLAIMS_SERIES_TICKER = "KXJOBLESSCLAIMS"


def market_implied_probability(market):
    yes_bid = market.get("yes_bid_dollars")
    yes_ask = market.get("yes_ask_dollars")
    if yes_bid is None or yes_ask is None:
        return None
    try:
        return (float(yes_bid) + float(yes_ask)) / 2.0
    except (TypeError, ValueError):
        return None


def build_claims_opportunities(markets, fred_api_key):
    """
    markets: raw Kalshi market dicts (only KXJOBLESSCLAIMS is used)
    fred_api_key: your free FRED API key

    Reuses bracket_probability() from the weather engine -- jobless claims
    markets are threshold bets ("at least 200,000"), which is the same
    one-sided-bracket math already built for weather.

    NOTE: assumes Kalshi's claims markets expose floor_strike/cap_strike
    and yes_sub_title fields the same way weather markets do. This is
    unverified against a real KXJOBLESSCLAIMS market -- if nothing comes
    back, print a raw market dict and check the actual field names.
    """
    forecast = get_claims_forecast(fred_api_key)
    opportunities = []

    if not forecast:
        return opportunities

    for market in markets:
        if market.get("series_ticker") != CLAIMS_SERIES_TICKER:
            continue

        model_prob = bracket_probability(
            market.get("floor_strike"),
            market.get("cap_strike"),
            forecast["forecast_mean"],
            forecast["forecast_std"],
        )
        market_prob = market_implied_probability(market)

        if model_prob is None or market_prob is None:
            continue

        edge = model_prob - market_prob

        volume = market.get("volume_fp") or 0
        try:
            volume = float(volume)
        except (TypeError, ValueError):
            volume = 0.0

        if volume <= 0:
            continue  # skip untouched brackets -- a flat 50% with no volume isn't a real price

        opportunities.append({
            "ticker": market.get("ticker"),
            "title": market.get("title"),
            "bracket": market.get("yes_sub_title"),
            "market_prob_pct": round(market_prob * 100, 1),
            "model_prob_pct": round(model_prob * 100, 1),
            "edge_pct": round(edge * 100, 1),
            "forecast_mean": round(forecast["forecast_mean"]),
            "forecast_std": round(forecast["forecast_std"]),
            "last_observed_value": forecast["last_observed_value"],
            "last_observed_date": forecast["last_observed_date"],
            "volume": volume,
            "yes_bid_dollars": market.get("yes_bid_dollars"),
            "yes_ask_dollars": market.get("yes_ask_dollars"),
            "last_price_dollars": market.get("last_price_dollars"),
        })

    opportunities.sort(key=lambda o: abs(o["edge_pct"]), reverse=True)
    return opportunities