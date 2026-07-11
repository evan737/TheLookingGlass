import sys

from kalshi import get_registered_markets
from market_registry import MARKET_SERIES
from sportsbook_odds import fetch_atp_matches, fetch_wta_matches

if len(sys.argv) < 2:
    print("Usage: python debug_tennis.py YOUR_API_KEY")
    sys.exit(1)

api_key = sys.argv[1]

print("=== Kalshi tennis markets ===")
markets = get_registered_markets(MARKET_SERIES)
tennis_markets = [m for m in markets if m.get("series_ticker") in ("KXATPMATCH", "KXWTAMATCH")]
print(f"Found {len(tennis_markets)} Kalshi tennis markets (out of {len(markets)} total)")
for m in tennis_markets[:10]:
    print({
        "series_ticker": m.get("series_ticker"),
        "event_ticker": m.get("event_ticker"),
        "ticker": m.get("ticker"),
        "title": m.get("title"),
        "yes_sub_title": m.get("yes_sub_title"),
        "yes_bid_dollars": m.get("yes_bid_dollars"),
        "yes_ask_dollars": m.get("yes_ask_dollars"),
    })

print("\n=== Sportsbook ATP matches ===")
atp = fetch_atp_matches(api_key)
for m in atp:
    print({"home": m["home"], "away": m["away"], "league": m["league"], "bookmakers": m["bookmakers"]})

print("\n=== Sportsbook WTA matches ===")
wta = fetch_wta_matches(api_key)
for m in wta:
    print({"home": m["home"], "away": m["away"], "league": m["league"], "bookmakers": m["bookmakers"]})