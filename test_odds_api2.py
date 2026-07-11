import sys
import json
import requests

if len(sys.argv) < 2:
    print("Usage: python test_odds_api2.py YOUR_API_KEY")
    sys.exit(1)

api_key = sys.argv[1]

print("--- Fetching tennis events ---")
events_response = requests.get(
    "https://api.odds-api.io/v3/events",
    params={"apiKey": api_key, "sport": "tennis"},
    timeout=20,
)
events = events_response.json()
print(f"Got {len(events)} total events")

# Only look at ATP/WTA main tour matches that haven't finished yet
candidates = [
    e for e in events
    if e.get("status") != "settled"
    and ("ATP" in e.get("league", {}).get("name", "") or "WTA" in e.get("league", {}).get("name", ""))
    and "Challenger" not in e.get("league", {}).get("name", "")
]
print(f"Found {len(candidates)} live/upcoming ATP or WTA main-tour matches")

if candidates:
    sample = candidates[0]
    print("\nSample match:")
    print(json.dumps(sample, indent=2))

    print(f"\n--- Fetching odds for event {sample['id']} ---")
    odds_response = requests.get(
        "https://api.odds-api.io/v3/odds",
        params={
            "apiKey": api_key,
            "eventId": sample["id"],
            "bookmakers": "bet365,draftkings,fanduel,betmgm",
        },
        timeout=20,
    )
    print("Status:", odds_response.status_code)
    print(json.dumps(odds_response.json(), indent=2)[:2500])
else:
    print("No live/upcoming ATP or WTA matches found right now -- try again "
          "during an active tournament window.")