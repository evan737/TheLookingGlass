import requests
import json

response = requests.get(
    "https://gamma-api.polymarket.com/public-search",
    params={"q": "2026 US Open Winner"},
    timeout=20,
)
data = response.json()
events = data.get("events", [])

mens_event = next((e for e in events if "women" not in (e.get("title") or "").lower()), None)

if not mens_event:
    print("Could not find the men's event.")
else:
    print(f"Found: {mens_event.get('title')}")
    markets = mens_event.get("markets", [])
    print(f"Number of sub-markets: {len(markets)}")
    if markets:
        print("\nFirst sub-market, full structure:")
        print(json.dumps(markets[0], indent=2))