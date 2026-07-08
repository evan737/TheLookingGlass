import time
from datetime import datetime

from kalshi import get_markets
from scanner import categorize_market
from strategy import calculate_basic_edge


SCAN_INTERVAL_SECONDS = 300  # 5 minutes


def scan_once():
    print("\n" + "=" * 60)
    print(f"Kalshi Auto Scanner - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)

    markets = get_markets(limit=100)

    for market in markets:
        title = market.get("title", "")
        category = categorize_market(title)
        edge_note = calculate_basic_edge(market)

        print(f"[{category}] {title}")
        print(f"Ticker: {market.get('ticker')}")
        print(f"YES bid: {market.get('yes_bid')}¢")
        print(f"YES ask: {market.get('yes_ask')}¢")
        print(f"Market quality: {edge_note}")
        print("-" * 60)


def main():
    print("Automated Kalshi scanner started.")
    print("Press CTRL + C to stop.")

    while True:
        scan_once()
        time.sleep(SCAN_INTERVAL_SECONDS)


if __name__ == "__main__":
    main()