import requests
import json

response = requests.get(
    "https://gamma-api.polymarket.com/public-search",
    params={"q": "2026 US Open Winner"},
    timeout=20,
)
data = response.json()
events = data.get("events", [])

print(f"Found {len(events)} events for query '2026 US Open Winner'\n")
for event in events[:5]:
    print(f"Title: {event.get('title')}")
    print(f"Keys on this event object: {list(event.keys())}")
    print(json.dumps(event, indent=2)[:1000])
    print("---")