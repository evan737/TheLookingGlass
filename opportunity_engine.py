import re
from datetime import datetime, timezone

from probability_model import bracket_probability, bracket_probability_with_floor
from weather_forecast import get_high_forecast
from stations import WEATHER_STATIONS
from nws_observations import fetch_todays_max_temp_f

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
    Models any series listed in stations.py (currently the KXHIGH weather
    series). Markets from other categories -- Economics, Crypto, Politics,
    Sports -- are skipped until they get their own probability models.

    Forecasts are fetched once per city (not once per market) since a city
    can have many open bracket markets sharing the same underlying forecast.

    For markets whose target date is TODAY, this also pulls the actual
    same-day observed running max temperature from the NWS station itself
    and conditions the forecast on "the true high is at least this much"
    -- sharpening the estimate as the day progresses. Future-day markets
    just use the raw forecast, since there's no same-day observation yet.
    """
    opportunities = []
    forecast_cache = {}
    observed_max_cache = {}

    today_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    for market in markets:
        series_ticker = market.get("series_ticker")
        station = WEATHER_STATIONS.get(series_ticker)
        if not station:
            continue

        if series_ticker not in forecast_cache:
            forecast_cache[series_ticker] = get_high_forecast(
                station["lat"], station["lon"]
            )
        forecasts = forecast_cache[series_ticker]

        target_date = parse_event_date(market.get("event_ticker"))
        forecast = forecasts.get(target_date)
        if not forecast:
            continue  # market's event date is outside our forecast window

        observed_max_so_far = None
        if target_date == today_str and station.get("station_id"):
            if series_ticker not in observed_max_cache:
                observed_max_cache[series_ticker] = fetch_todays_max_temp_f(station["station_id"])
            observed_max_so_far = observed_max_cache[series_ticker]

        model_prob = bracket_probability_with_floor(
            market.get("floor_strike"),
            market.get("cap_strike"),
            forecast["forecast_mean"],
            forecast["forecast_std"],
            observed_max_so_far=observed_max_so_far,
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
            "city": station["name"],
            "series_ticker": series_ticker,
            "ticker": market.get("ticker"),
            "title": market.get("title"),
            "bracket": market.get("yes_sub_title"),
            "target_date": target_date,
            "market_prob_pct": round(market_prob * 100, 1),
            "model_prob_pct": round(model_prob * 100, 1),
            "edge_pct": round(edge * 100, 1),
            "confidence": confidence,
            "forecast_mean_f": round(forecast["forecast_mean"], 1),
            "forecast_std_f": round(forecast["forecast_std"], 2),
            "observed_max_so_far_f": round(observed_max_so_far, 1) if observed_max_so_far is not None else None,
            "volume": market.get("volume_fp"),
            "yes_bid_dollars": market.get("yes_bid_dollars"),
            "yes_ask_dollars": market.get("yes_ask_dollars"),
            "last_price_dollars": market.get("last_price_dollars"),
        })

    opportunities.sort(key=lambda o: abs(o["edge_pct"]), reverse=True)
    return opportunities