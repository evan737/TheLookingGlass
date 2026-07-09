import re

from probability_model import bracket_probability
from weather_forecast import get_nyc_high_forecast

MONTH_MAP = {
    "JAN": 1, "FEB": 2, "MAR": 3, "APR": 4, "MAY": 5, "JUN": 6,
    "JUL": 7, "AUG": 8, "SEP": 9, "OCT": 10, "NOV": 11, "DEC": 12,
}


def parse_event_date(event_ticker):
    """
    'KXHIGHNY-26JUN10' -> '2026-06-10'

    Note: this is only used to line up a market with the *right day's*
    forecast, not to infer strike/threshold info (which comes from the
    market's own floor_strike/cap_strike fields, per Kalshi's docs).
    """
    match = re.search(r"-(\d{2})([A-Z]{3})(\d{2})$", event_ticker or "")
    if not match:
        return None
    yy, mon, dd = match.groups()
    month = MONTH_MAP.get(mon)
    if not month:
        return None
    year = 2000 + int(yy)
    return f"{year:04d}-{month:02d}-{int(dd):02d}"


def market_implied_probability(market):
    yes_bid = market.get("yes_bid_dollars")
    yes_ask = market.get("yes_ask_dollars")
    if yes_bid is None or yes_ask is None:
        return None
    try:
        return (float(yes_bid) + float(yes_ask)) / 2.0
    except (TypeError, ValueError):
        return None


def build_opportunities(markets):
    """
    Currently only models the KXHIGHNY (NYC High Temp) series -- that's the
    only series in market_registry.py with a matching weather model. Other
    categories (Economics, Crypto, Politics, Sports) will just be skipped
    until they get their own probability models.
    """
    forecasts = get_nyc_high_forecast()
    opportunities = []

    for market in markets:
        if market.get("series_ticker") != "KXHIGHNY":
            continue

        target_date = parse_event_date(market.get("event_ticker"))
        forecast = forecasts.get(target_date)
        if not forecast:
            continue  # market's event date is outside our forecast window

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

        # Crude confidence proxy: tighter model agreement -> higher confidence.
        # This is a heuristic, not a calibrated statistic -- treat it as a
        # sort-order hint, not a guarantee.
        spread_penalty = min(forecast["forecast_std"] / 5.0, 1.0)
        confidence = round((1 - spread_penalty) * 100, 1)

        opportunities.append({
            "ticker": market.get("ticker"),
            "title": market.get("title"),
            "bracket": market.get("bracket_label"),
            "target_date": target_date,
            "market_prob_pct": round(market_prob * 100, 1),
            "model_prob_pct": round(model_prob * 100, 1),
            "edge_pct": round(edge * 100, 1),
            "confidence": confidence,
            "forecast_mean_f": round(forecast["forecast_mean"], 1),
            "forecast_std_f": round(forecast["forecast_std"], 2),
            "volume": market.get("volume_fp"),
        })

    opportunities.sort(key=lambda o: abs(o["edge_pct"]), reverse=True)
    return opportunities
