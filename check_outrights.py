import sys
import requests

if len(sys.argv) < 2:
    print("Usage: python check_outrights.py YOUR_ODDS_API_KEY")
    sys.exit(1)

api_key = sys.argv[1]

# Check the events list for anything that looks like a tournament outright
# (not a specific match between two named players)
response = requests.get(
    "https://api.odds-api.io/v3/events",
    params={"apiKey": api_key, "sport": "tennis"},
    timeout=20,
)
events = response.json()

# Outright futures often show up with a different structure -- e.g. no
# clear "home"/"away" two-player matchup, or a league name mentioning
# "Winner" or "Outright". Look for any such signal.
candidates = [
    e for e in events
    if "winner" in (e.get("league", {}).get("name", "") or "").lower()
    or "outright" in (e.get("league", {}).get("name", "") or "").lower()
]

print(f"Total tennis events: {len(events)}")
print(f"Possible outright/futures events found: {len(candidates)}")
for c in candidates[:10]:
    print(f"  {c}")

if not candidates:
    print("\nNo obvious outright futures events found in the events list.")
    print("Trying to fetch odds for a known US Open match to see available market types...")
    if events:
        sample_event = events[0]
        odds_response = requests.get(
            "https://api.odds-api.io/v3/odds",
            params={"apiKey": api_key, "eventId": sample_event["id"], "bookmakers": "1xbet"},
            timeout=20,
        )
        print(f"Sample odds response for event {sample_event['id']}:")
        print(odds_response.json())