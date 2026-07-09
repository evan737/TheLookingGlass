import time
from datetime import datetime

from database import initialize_database, save_market_scans
from kalshi import get_registered_markets
from market_registry import MARKET_SERIES


SCAN_INTERVAL_SECONDS = 15
LIMIT_PER_SERIES = 10


def scan_once():
    print("=" * 60)
    print(f"The Looking Glass scan: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    markets = get_registered_markets(
        MARKET_SERIES,
        limit_per_series=LIMIT_PER_SERIES,
    )

    save_market_scans(markets)

    print(f"Saved {len(markets)} market scans")
    print("=" * 60)


def main():
    initialize_database()

    print("The Looking Glass scanner service started.")
    print("Press CTRL + C to stop.")

    while True:
        scan_once()
        time.sleep(SCAN_INTERVAL_SECONDS)


if __name__ == "__main__":
    main()