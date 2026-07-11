import sys
import json
import requests

if len(sys.argv) < 2:
    print("Usage: python test_odds_api.py YOUR_API_KEY")
    sys.exit(1)

api_key = sys.argv[1]

print("--- Fetching tennis events ---")
events_response = requests.get(
    "https://api.odds-api.io/v3/events",
    params={"apiKey": api_key, "sport": "tennis"},
    timeout=20,
)
print("Status:", events_response.status_code)
events = events_response.json()
print(f"Got {len(events) if isinstance(events, list) else '?'} events")
print(json.dumps(events[0] if isinstance(events, list) and events else events, indent=2)[:2000])

if isinstance(events, list) and events:
    first_id = events[0].get("id")
    print(f"\n--- Fetching odds for event {first_id} ---")
    odds_response = requests.get(
        "https://api.odds-api.io/v3/odds",
        params={"apiKey": api_key, "eventId": first_id},
        timeout=20,
    )
    print("Status:", odds_response.status_code)
    print(json.dumps(odds_response.json(), indent=2)[:2000])