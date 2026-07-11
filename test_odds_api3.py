import sys
import json
import requests

if len(sys.argv) < 2:
    print("Usage: python test_odds_api3.py YOUR_API_KEY")
    sys.exit(1)

api_key = sys.argv[1]

events_response = requests.get(
    "https://api.odds-api.io/v3/events",
    params={"apiKey": api_key, "sport": "tennis"},
    timeout=20,
)
events = events_response.json()

candidates = [
    e for e in events
    if e.get("status") in ("live", "not_started")
    and e.get("league", {}).get("name", "").startswith(("ATP", "WTA"))
    and "Challenger" not in e.get("league", {}).get("name", "")
    and "125K" not in e.get("league", {}).get("name", "")
]
print(f"Found {len(candidates)} ATP/WTA main-tour matches")

if candidates:
    sample = candidates[0]
    print("Sample match:", sample["home"], "vs", sample["away"], "-", sample["league"]["name"])

    odds_response = requests.get(
        "https://api.odds-api.io/v3/odds",
        params={
            "apiKey": api_key,
            "eventId": sample["id"],
            "bookmakers": "Bet365",
        },
        timeout=20,
    )
    print("Status:", odds_response.status_code)
    print(json.dumps(odds_response.json(), indent=2)[:3000])
else:
    print("No ATP/WTA main-tour matches found right now.")