from kalshi import get_registered_markets
from market_registry import MARKET_SERIES

markets = get_registered_markets(MARKET_SERIES)
tennis_markets = [m for m in markets if m.get("series_ticker") in ("KXATPMATCH", "KXWTAMATCH")]

print(f"Found {len(tennis_markets)} open tennis markets on Kalshi right now (all series/events, unfiltered):\n")

seen_events = set()
for m in tennis_markets:
    event = m.get("event_ticker")
    if event in seen_events:
        continue
    seen_events.add(event)
    print(f"  {m.get('series_ticker')} | {event} | {m.get('title')}")

print(f"\n{len(seen_events)} distinct events/matches found.")