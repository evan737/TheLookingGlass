import requests

BASE_URL = "https://external-api.kalshi.com/trade-api/v2"


def get_series(series_ticker):
    url = f"{BASE_URL}/series/{series_ticker}"
    response = requests.get(url, timeout=20)
    response.raise_for_status()
    return response.json()


def get_markets_for_series(series_ticker, limit=100):
    url = f"{BASE_URL}/markets"

    params = {
        "limit": limit,
        "status": "open",
        "series_ticker": series_ticker,
    }

    response = requests.get(url, params=params, timeout=20)
    response.raise_for_status()

    return response.json().get("markets", [])


def get_registered_markets(market_registry, limit_per_series=100):
    all_rows = []

    for category, series_group in market_registry.items():
        for series_name, series_ticker in series_group.items():
            try:
                markets = get_markets_for_series(series_ticker, limit=limit_per_series)

                for market in markets:
                    market["category"] = category
                    market["series_name"] = series_name
                    market["series_ticker"] = series_ticker
                    all_rows.append(market)

            except Exception as error:
                print(f"Error loading {series_ticker}: {error}")

    return all_rows


if __name__ == "__main__":
    from market_registry import MARKET_SERIES

    markets = get_registered_markets(MARKET_SERIES)

    print(f"Loaded {len(markets)} registered markets")

    for market in markets[:20]:
        print(market.get("category"), "-", market.get("series_name"))
        print(market.get("title"))
        print("YES bid:", market.get("yes_bid_dollars"))
        print("YES ask:", market.get("yes_ask_dollars"))
        print("-" * 60)

def get_market(ticker):
    url = f"{BASE_URL}/markets/{ticker}"
    response = requests.get(url, timeout=20)
    response.raise_for_status()
    return response.json().get("market", {})