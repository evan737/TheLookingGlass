import requests

BASE_URL = "https://gamma-api.polymarket.com"


def list_tags():
    """
    Looks for a tags endpoint to find the real tag_id for categories like
    'Tennis', 'Sports', or 'Economy' -- more reliable than guessing at
    keyword matches in titles.
    """
    try:
        response = requests.get(f"{BASE_URL}/tags", timeout=20)
        response.raise_for_status()
        return response.json()
    except Exception as error:
        print(f"Could not fetch /tags: {error}")
        return []


def fetch_events_page(offset, limit=100):
    response = requests.get(
        f"{BASE_URL}/events",
        params={"active": "true", "closed": "false", "limit": limit, "offset": offset},
        timeout=20,
    )
    response.raise_for_status()
    return response.json()


def paginated_keyword_search(keywords, max_pages=10, page_size=100):
    """
    Pages through up to max_pages * page_size events (not just the first
    100), checking each event's title against every keyword. This is
    slower but much more thorough than a single-page check.
    """
    matches = {kw: [] for kw in keywords}
    total_checked = 0

    for page in range(max_pages):
        offset = page * page_size
        try:
            events = fetch_events_page(offset, page_size)
        except Exception as error:
            print(f"  Stopped paginating at offset {offset}: {error}")
            break

        if not events:
            print(f"  No more events after offset {offset} -- stopping.")
            break

        total_checked += len(events)

        for event in events:
            title = (event.get("title", "") or "").lower()
            for kw in keywords:
                if kw.lower() in title:
                    matches[kw].append(event)

    print(f"\nChecked {total_checked} total events across up to {max_pages} pages.")
    return matches


if __name__ == "__main__":
    print("=== Checking for a tags/category endpoint ===")
    tags = list_tags()
    if tags:
        print(f"Found {len(tags)} tags. Looking for relevant ones...")
        relevant = [
            t for t in tags
            if any(k in (t.get("label", "") or t.get("name", "") or "").lower()
                   for k in ["tennis", "sport", "econom", "jobs", "labor"])
        ]
        for t in relevant:
            print(f"  {t}")
        if not relevant:
            print("  No obviously relevant tags found in the list.")
    else:
        print("No usable /tags response.")

    print("\n=== Paginated keyword search across more events ===")
    keywords = ["tennis", "ATP", "WTA", "wimbledon", "jobless", "unemployment", "nonfarm", "payrolls"]
    matches = paginated_keyword_search(keywords, max_pages=10, page_size=100)

    for kw, events in matches.items():
        print(f"\n'{kw}': {len(events)} matching events")
        for event in events[:5]:
            print(f"  {event.get('title')}")