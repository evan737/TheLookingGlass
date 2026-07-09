import time
from datetime import datetime

from kalshi import get_markets
from scanner import categorize_market
from strategy import analyze_market
from paper_trader import log_paper_trade


SCAN_INTERVAL_SECONDS = 300


def scan_once():
    print("\n" + "=" * 70)
    print(f"The Looking Glass - Auto Scanner")
    print(datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    print("=" * 70)

    markets = get_markets(limit=100)

    opportunities = 0

    for market in markets:
        title = market.get("title", "")
        category = categorize_market(title)
        analysis = analyze_market(market, category)

        decision = analysis["decision"]
        reason = analysis["reason"]

        if decision == "WATCH":
            opportunities += 1
            log_paper_trade(market, category, decision, reason)

            print(f"[{category}] {title}")
            print(f"Ticker: {market.get('ticker')}")
            print(f"Decision: {decision}")
            print(f"Reason: {reason}")
            print("-" * 70)

    print(f"Scan complete. Opportunities logged: {opportunities}")


def main():
    print("The Looking Glass automated paper scanner started.")
    print("Press CTRL + C to stop.")

    while True:
        scan_once()
        time.sleep(SCAN_INTERVAL_SECONDS)


if __name__ == "__main__":
    main()