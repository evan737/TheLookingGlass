import requests

BASE_URL = "https://gamma-api.polymarket.com"


def search_events(keyword, limit=20):
    """
    Polymarket's Gamma API doesn't have a simple full-text search param
    documented consistently across sources, so we fetch active events and
    filter client-side by keyword in the title -- same approach we used
    for discovering tennis events on odds-api.io earlier.
    """
    response = requests.get(
        f"{BASE_URL}/events",
        params={"active": "true", "closed": "false", "limit": 100},
        timeout=20,
    )
    response.raise_for_status()
    events = response.json()

    matches = [
        e for e in events
        if keyword.lower() in (e.get("title", "") or "").lower()
    ]
    return matches[:limit]


def print_matches(label, matches):
    print(f"\n=== {label}: {len(matches)} matching events found ===")
    for event in matches:
        print(f"  {event.get('title')}")
        for market in event.get("markets", [])[:3]:
            print(f"    - {market.get('question')}: {market.get('outcomePrices')}")


if __name__ == "__main__":
    for keyword in ["tennis", "ATP", "WTA", "Wimbledon"]:
        print_matches(f"Keyword '{keyword}'", search_events(keyword))

    for keyword in ["jobless claims", "unemployment", "initial claims"]:
        print_matches(f"Keyword '{keyword}'", search_events(keyword))