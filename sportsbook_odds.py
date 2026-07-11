import requests

from tennis_utils import normalize_player_name

# odds-api.io's real flow (confirmed against a live response):
#   1. GET /v3/events?sport=tennis  -> list of events with home/away names,
#      date, status, league info -- but NO odds included.
#   2. GET /v3/odds?eventId=X&bookmakers=Name -> odds for one event, ONE
#      bookmaker at a time. Requesting several bookmakers in one comma-
#      separated list returned 403 Forbidden on the free tier -- so we
#      query each book separately and merge results, at the cost of one
#      API call per (event, book) pair instead of one per event.
#
# Free tier is capped at 100 requests/hour -- with a handful of candidate
# matches and 2 books, that's roughly (matches * 2) calls, which stays
# comfortably under the limit. Don't add more books than needed without
# checking the math.
BASE_URL = "https://api.odds-api.io/v3"

# 22Bet returned 403 Forbidden even alone -- likely not included in this
# free-tier plan despite showing "active" in the bookmaker list. Sticking
# with 1xbet, which is confirmed working, until another book is verified.
DEFAULT_BOOKMAKERS = ["1xbet"]


def fetch_events(sport, api_key):
    response = requests.get(
        f"{BASE_URL}/events",
        params={"apiKey": api_key, "sport": sport},
        timeout=20,
    )
    response.raise_for_status()
    return response.json()


def fetch_odds_for_event_and_book(event_id, api_key, bookmaker):
    """One book at a time -- combined lists were rejected (403) on this tier."""
    response = requests.get(
        f"{BASE_URL}/odds",
        params={
            "apiKey": api_key,
            "eventId": event_id,
            "bookmakers": bookmaker,
        },
        timeout=20,
    )
    response.raise_for_status()
    return response.json()


def is_candidate_match(event, tour_prefix, target_surnames):
    """
    tour_prefix: "ATP" or "WTA"
    target_surnames: set of normalized surnames we actually care about
                     (from Kalshi's open markets) -- this is what keeps
                     the number of odds API calls small.

    NOTE: this data provider's league names are unreliable for filtering
    round/quality -- real Wimbledon semifinal matches came back labeled
    "...Qualifying" even though they're clearly not qualifiers. So we
    don't filter on that text at all; we rely on target_surnames plus a
    doubles exclusion instead.
    """
    league_name = event.get("league", {}).get("name", "")
    home = event.get("home", "") or ""
    away = event.get("away", "") or ""

    if event.get("status") not in ("live", "not_started", "pending"):
        return False
    if not league_name.startswith(tour_prefix):
        return False
    if "Doubles" in league_name or "/" in home or "/" in away:
        return False

    home_key = normalize_player_name(home)
    away_key = normalize_player_name(away)
    return home_key in target_surnames or away_key in target_surnames


def fetch_tennis_matches(tour_prefix, api_key, target_surnames, bookmakers=None):
    """
    tour_prefix: "ATP" or "WTA"
    target_surnames: set of normalized surnames to restrict odds lookups to
                     (required -- pass the surnames of players in Kalshi's
                     currently open markets to avoid burning API quota on
                     hundreds of irrelevant matches)

    Returns a list of dicts: {home, away, league, bookmakers}
    where bookmakers is {book_name: (home_decimal_odds, away_decimal_odds)}
    -- built from querying each book separately per event.
    """
    bookmakers = bookmakers or DEFAULT_BOOKMAKERS
    events = fetch_events("tennis", api_key)
    candidates = [e for e in events if is_candidate_match(e, tour_prefix, target_surnames)]
    print(f"  {tour_prefix}: {len(candidates)} candidate matches "
          f"(out of {len(events)} total tennis events) -- fetching odds for these only "
          f"({len(bookmakers)} book(s) x {len(candidates)} match(es) = "
          f"{len(bookmakers) * len(candidates)} API calls)")

    matches = []
    for event in candidates:
        book_prices = {}

        for bookmaker in bookmakers:
            try:
                odds_data = fetch_odds_for_event_and_book(event["id"], api_key, bookmaker)
            except Exception as error:
                print(f"    Could not fetch {bookmaker} odds for event {event.get('id')}: {error}")
                continue

            for book_name, markets in odds_data.get("bookmakers", {}).items():
                for market in markets:
                    if market.get("name") != "ML":
                        continue
                    for line in market.get("odds", []):
                        book_prices[book_name] = (line.get("home"), line.get("away"))

        if not book_prices:
            continue

        matches.append({
            "home": event.get("home"),
            "away": event.get("away"),
            "league": event.get("league", {}).get("name"),
            "bookmakers": book_prices,
        })

    return matches


def fetch_atp_matches(api_key, target_surnames, bookmakers=None):
    return fetch_tennis_matches("ATP", api_key, target_surnames, bookmakers)


def fetch_wta_matches(api_key, target_surnames, bookmakers=None):
    return fetch_tennis_matches("WTA", api_key, target_surnames, bookmakers)