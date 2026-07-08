import requests


def get_markets(limit=20):
    url = "https://api.elections.kalshi.com/trade-api/v2/markets"

    params = {
        "limit": limit,
        "status": "open",
    }

    response = requests.get(url, params=params, timeout=20)
    data = response.json()

    return data.get("markets", [])


if __name__ == "__main__":
    markets = get_markets()

    print(f"Found {len(markets)} open markets")
    print()

    for market in markets:
        print(market.get("title"))
        print("Ticker:", market.get("ticker"))
        print("YES bid:", market.get("yes_bid"))
        print("YES ask:", market.get("yes_ask"))
        print("-" * 60)