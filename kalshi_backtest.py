"""
Tests whether Kalshi's OWN historical weather market prices were
well-calibrated -- i.e., did brackets priced around 40% actually resolve
YES about 40% of the time, historically?

IMPORTANT SCOPE NOTE: this does NOT test our forecast model's skill. It
only tests whether Kalshi's market itself has historically been
efficiently priced. Testing our specific model would require archived
historical weather *forecasts* (what models predicted in advance), which
isn't available through free APIs -- only the actual outcome is. Using
the actual outcome as a stand-in "forecast" would make any model look
artificially perfect, so we don't do that here. This script answers a
different, still-useful question: has this market category historically
had exploitable mispricing at all?
"""
import sys
import requests
from collections import defaultdict
from datetime import datetime, timezone

from stations import WEATHER_STATIONS

BASE_URL = "https://external-api.kalshi.com/trade-api/v2"
HEADERS = {}  # public endpoints, no auth needed for read-only historical data


def get_historical_cutoff():
    response = requests.get(f"{BASE_URL}/historical/cutoff", timeout=20)
    response.raise_for_status()
    data = response.json()
    print(f"Historical cutoff response: {data}")
    return data


def get_settled_events(series_ticker, max_events=100):
    """
    Paginates through settled events for a series. Prints the raw shape
    of the first page so we can confirm the pagination cursor format
    before trusting the loop logic.
    """
    events = []
    cursor = None
    first_page = True

    while len(events) < max_events:
        params = {
            "series_ticker": series_ticker,
            "status": "settled",
            "with_nested_markets": "true",
            "limit": 100,
        }
        if cursor:
            params["cursor"] = cursor

        response = requests.get(f"{BASE_URL}/events", params=params, timeout=20)
        response.raise_for_status()
        data = response.json()

        if first_page:
            print(f"  First page keys: {list(data.keys())}")
            first_page = False

        page_events = data.get("events", [])
        events.extend(page_events)

        cursor = data.get("cursor")
        if not cursor or not page_events:
            break

    return events[:max_events]


def get_reference_price(ticker, series_ticker, close_time_iso, cutoff_iso):
    """
    Gets a representative pre-close price using hourly candlesticks,
    looking at the window 6-1 hours before close (to avoid both stale
    early prices and last-minute settlement noise). Uses the historical
    endpoint if the market closed before Kalshi's historical cutoff.
    """
    close_ts = int(datetime.fromisoformat(close_time_iso.replace("Z", "+00:00")).timestamp())
    start_ts = close_ts - 6 * 3600
    end_ts = close_ts - 3600

    is_historical = cutoff_iso and close_time_iso < cutoff_iso

    if is_historical:
        url = f"{BASE_URL}/historical/markets/{ticker}/candlesticks"
    else:
        url = f"{BASE_URL}/series/{series_ticker}/markets/{ticker}/candlesticks"

    params = {"start_ts": start_ts, "end_ts": end_ts, "period_interval": 60}

    try:
        response = requests.get(url, params=params, timeout=20)
        response.raise_for_status()
        data = response.json()
    except Exception as error:
        print(f"    Could not fetch candlesticks for {ticker}: {error}")
        return None

    candles = data.get("candlesticks", [])
    if not candles:
        return None

    # Use the last available candle's mean price in the window
    last_candle = candles[-1]
    mean_price = last_candle.get("price", {}).get("mean_dollars")
    try:
        return float(mean_price)
    except (TypeError, ValueError):
        return None


def run_backtest(series_tickers, max_events_per_series=30):
    cutoff_data = get_historical_cutoff()
    cutoff_iso = cutoff_data.get("cutoff") or cutoff_data.get("historical_cutoff")

    bucket_totals = defaultdict(lambda: {"n": 0, "yes": 0})
    checked = 0

    for series_ticker in series_tickers:
        print(f"\nFetching settled events for {series_ticker}...")
        events = get_settled_events(series_ticker, max_events=max_events_per_series)
        print(f"  Got {len(events)} settled events")

        for event in events:
            for market in event.get("markets", []):
                result = market.get("result")
                if result not in ("yes", "no"):
                    continue

                ticker = market.get("ticker")
                close_time = market.get("close_time")
                if not ticker or not close_time:
                    continue

                price = get_reference_price(ticker, series_ticker, close_time, cutoff_iso)
                if price is None:
                    continue

                bucket = int(price * 10) * 10  # 0, 10, 20, ... 90
                bucket_totals[bucket]["n"] += 1
                if result == "yes":
                    bucket_totals[bucket]["yes"] += 1

                checked += 1

    if checked == 0:
        print("\nNo markets could be checked -- see errors above for what went wrong.")
        return

    print(f"\n=== Calibration check across {checked} historical settled markets ===")
    print(f"{'Price bucket':<15}{'N':<6}{'Actual YES rate':<18}{'Expected (bucket mid)'}")
    for bucket in sorted(bucket_totals.keys()):
        stats = bucket_totals[bucket]
        actual_rate = stats["yes"] / stats["n"] * 100
        expected_mid = bucket + 5
        print(f"{bucket}-{bucket+10}%{'':<8}{stats['n']:<6}{actual_rate:<18.1f}{expected_mid}%")

    print("\nIf actual YES rate consistently and substantially differs from the "
          "expected bucket midpoint, that's a sign of historical market "
          "inefficiency -- worth investigating further. Small samples per "
          "bucket won't be reliable; look for buckets with a meaningful N.")


if __name__ == "__main__":
    tickers = list(WEATHER_STATIONS.keys())
    run_backtest(tickers, max_events_per_series=30)