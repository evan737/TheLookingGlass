import requests

BASE_URL = "https://gamma-api.polymarket.com"

SLUG_GUESSES = [
    "2026-mens-us-open-winner",
    "mens-us-open-winner-2026",
    "us-open-winner-2026",
    "2026-us-open-mens-winner",
    "2026-men-s-us-open-winner",
]


def try_slug_lookup():
    print("=== Trying direct slug lookup ===")
    for slug in SLUG_GUESSES:
        try:
            response = requests.get(f"{BASE_URL}/events", params={"slug": slug}, timeout=20)
            print(f"  slug={slug!r}: status {response.status_code}")
            if response.status_code == 200:
                data = response.json()
                if data:
                    print(f"    FOUND: {data if isinstance(data, dict) else data[0].get('title')}")
        except Exception as error:
            print(f"  slug={slug!r}: error - {error}")


def try_search_endpoint():
    print("\n=== Trying search endpoint ===")
    for path in ["/public-search", "/search"]:
        try:
            response = requests.get(f"{BASE_URL}{path}", params={"q": "US Open Winner"}, timeout=20)
            print(f"  {path}: status {response.status_code}")
            if response.status_code == 200:
                data = response.json()
                print(f"    Response type: {type(data)}, sample: {str(data)[:500]}")
        except Exception as error:
            print(f"  {path}: error - {error}")


if __name__ == "__main__":
    try_slug_lookup()
    try_search_endpoint()