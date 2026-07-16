import re
import requests

from kalshi import get_markets_for_series, BASE_URL
from tennis_utils import normalize_player_name

# Confirmed real via a live Kalshi link: kalshi.com/markets/kxatp/mens-tournament-winner/kxatp-26wim
# Series ticker is "KXATP" (general men's tournament winner series -- the
# specific tournament like Wimbledon or US Open is encoded in the EVENT
# ticker, e.g. "KXATP-26WIM", not a separate series per tournament).
KALSHI_CANDIDATE_TICKERS = [
    "KXATP",
    "KXWTA",
]

POLYMARKET_BASE_URL = "https://gamma-api.polymarket.com"


def raw_series_check(series_ticker):
    """
    Bypasses kalshi.py's status='open' filter entirely to see the RAW
    response -- if the confirmed-real ticker still returns nothing, the
    status filter (or something else) is the problem, not the ticker.
    """
    url = f"{BASE_URL}/markets"
    for status in [None, "open", "unopened", "active"]:
        params = {"limit": 20, "series_ticker": series_ticker}
        if status:
            params["status"] = status
        try:
            response = requests.get(url, params=params, timeout=20)
            response.raise_for_status()
            data = response.json()
            markets = data.get("markets", [])
            print(f"    status={status!r}: {len(markets)} markets")
            if markets:
                print(f"      Sample: {markets[0].get('yes_sub_title')}, status field on market: {markets[0].get('status')}")
        except Exception as error:
            print(f"    status={status!r}: error - {error}")


def discover_kalshi_futures():
    found = {}
    for ticker in KALSHI_CANDIDATE_TICKERS:
        print(f"  Checking {ticker}...")
        raw_series_check(ticker)
        try:
            markets = get_markets_for_series(ticker)
            if markets:
                found[ticker] = markets
        except Exception as error:
            print(f"    (normal open-status check) error - {error}")
    return found


def find_tag_id(label_keyword):
    """
    Looks up a tag's real ID by label (e.g. 'Tennis') -- more reliable
    than paginating through /events with an offset param that may not
    actually be honored by this API (their docs mention cursor-based
    pagination as the real mechanism, not offset).
    """
    response = requests.get(f"{POLYMARKET_BASE_URL}/tags", timeout=20)
    response.raise_for_status()
    tags = response.json()
    for tag in tags:
        label = (tag.get("label") or tag.get("name") or "")
        if label_keyword.lower() == label.lower():
            return tag.get("id")
    return None


def fetch_events_by_tag(tag_id, closed=False):
    response = requests.get(
        f"{POLYMARKET_BASE_URL}/events",
        params={"tag_id": tag_id, "closed": str(closed).lower(), "limit": 200},
        timeout=20,
    )
    response.raise_for_status()
    return response.json()


def fetch_polymarket_tournament_event(title_keyword, exclude_keyword=None):
    """
    Uses Polymarket's real /public-search endpoint (confirmed working,
    unlike the tag list and offset-based pagination we tried earlier --
    both turned out to be dead ends). Returns the first matching event.
    """
    response = requests.get(
        f"{POLYMARKET_BASE_URL}/public-search",
        params={"q": title_keyword},
        timeout=20,
    )
    response.raise_for_status()
    data = response.json()
    events = data.get("events", [])

    for event in events:
        title = (event.get("title", "") or "").lower()
        if exclude_keyword and exclude_keyword.lower() in title:
            continue
        return event

    return None


def parse_polymarket_player_name(question):
    """
    'Will Novak Djokovic win the US Open?' -> 'Novak Djokovic'
    Returns None if the pattern doesn't match.
    """
    match = re.search(r"[Ww]ill (.+?) win", question or "")
    return match.group(1).strip() if match else None


if __name__ == "__main__":
    print("=== Discovering Kalshi tournament futures tickers ===")
    kalshi_found = discover_kalshi_futures()

    if kalshi_found:
        for ticker, markets in kalshi_found.items():
            print(f"\nMarkets from {ticker}, grouped by tournament:")
            by_event = {}
            for m in markets:
                by_event.setdefault(m.get("event_ticker"), []).append(m)
            for event_ticker, event_markets in by_event.items():
                print(f"  {event_ticker} ({len(event_markets)} candidates):")
                for m in event_markets[:8]:
                    print(f"    {m.get('yes_sub_title')}: bid={m.get('yes_bid_dollars')} ask={m.get('yes_ask_dollars')}")

    print("\n=== Searching Polymarket for US Open winner event ===")
    event = fetch_polymarket_tournament_event("2026 US Open Winner", exclude_keyword="women")
    if event:
        print(f"Found event: {event.get('title')}")
        markets = event.get("markets", [])
        print(f"  {len(markets)} sub-markets (candidates)")
        for m in markets[:10]:
            player = parse_polymarket_player_name(m.get("question"))
            print(f"  {player or m.get('question')}: {m.get('outcomePrices')}")
    else:
        print("No matching Polymarket event found for 'US Open'.")