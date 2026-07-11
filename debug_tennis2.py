import sys
import json

from sportsbook_odds import fetch_events

if len(sys.argv) < 2:
    print("Usage: python debug_tennis2.py YOUR_API_KEY")
    sys.exit(1)

api_key = sys.argv[1]

events = fetch_events("tennis", api_key)
print(f"Total tennis events: {len(events)}")

names_to_find = ["Djokovic", "Sinner", "Muchova", "Gauff", "Kostyuk", "Noskova", "Zverev", "Fery"]

matches = [
    e for e in events
    if any(name in e.get("home", "") or name in e.get("away", "") for name in names_to_find)
]

print(f"\nFound {len(matches)} events involving our target players (unfiltered):")
for m in matches:
    print(json.dumps({
        "home": m.get("home"),
        "away": m.get("away"),
        "status": m.get("status"),
        "league_name": m.get("league", {}).get("name"),
        "date": m.get("date"),
    }, indent=2))