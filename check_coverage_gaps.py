import sys
import requests

from tennis_elo import build_elo_ratings_from_files, fetch_csv_from_url
from tennis_utils import normalize_player_name

# Surnames pulled directly from the live Kalshi qualifying-round markets
QUALIFYING_PLAYERS = [
    "Virtanen", "Dietrich", "Monteiro", "Herbert", "Skatov", "Chandrasekar",
    "Dhamne", "Sachko", "Cina", "Zahraj", "Michalski", "Hemery", "Tabur",
    "Jebens", "Huesler", "Butvilas", "Sziedat", "Tang", "Nepliy",
    "Panagiotidou", "Kulikova", "Tona", "Ninomiya", "Yashina", "Glushko",
    "Sieg", "Tsetsou", "Mansouri", "Hodzic", "Chan",
]


def check_sportsbook_coverage(api_key):
    print("=== Checking odds-api.io coverage for qualifying-round players ===")
    response = requests.get(
        "https://api.odds-api.io/v3/events",
        params={"apiKey": api_key, "sport": "tennis"},
        timeout=30,
    )
    response.raise_for_status()
    events = response.json()
    print(f"Total tennis events on odds-api.io right now: {len(events)}")

    found = []
    for event in events:
        home_surname = normalize_player_name(event.get("home", ""))
        away_surname = normalize_player_name(event.get("away", ""))
        for target in QUALIFYING_PLAYERS:
            target_norm = normalize_player_name(target)
            if target_norm == home_surname or target_norm == away_surname:
                found.append((target, event.get("home"), event.get("away"), event.get("league", {}).get("name")))

    if found:
        print(f"Found {len(found)} qualifying-round players WITH sportsbook coverage:")
        for target, home, away, league in found:
            print(f"  {target}: {home} vs {away} ({league})")
    else:
        print("Found 0 of these qualifying-round players anywhere in odds-api.io's tennis events.")
        print("This supports the hypothesis: mainstream sportsbook coverage doesn't reach this level.")


def check_elo_coverage():
    print("\n=== Checking Elo rating coverage (main tour data, 2019-2026) ===")
    years = range(2019, 2027)
    file_urls = [f"https://stats.tennismylife.org/data/{year}.csv" for year in years]
    ratings = build_elo_ratings_from_files(file_urls)

    found_in_main_tour = []
    missing = []
    for target in QUALIFYING_PLAYERS:
        target_norm = normalize_player_name(target)
        match = next((name for name in ratings if normalize_player_name(name) == target_norm), None)
        if match:
            found_in_main_tour.append((target, match, ratings[match]))
        else:
            missing.append(target)

    print(f"\nFound in main-tour Elo data: {len(found_in_main_tour)}/{len(QUALIFYING_PLAYERS)}")
    for target, match, rating in found_in_main_tour:
        print(f"  {target} -> {match}: {round(rating)}")

    if missing:
        print(f"\nMissing from main-tour data ({len(missing)}): {', '.join(missing)}")
        print("Checking recent Challenger-level files for these players...")

        challenger_years = [2023, 2024, 2025, 2026]
        challenger_urls = [f"https://stats.tennismylife.org/data/{year}_challenger.csv" for year in challenger_years]

        challenger_matches = []
        for url in challenger_urls:
            print(f"  Fetching {url}...")
            try:
                rows = fetch_csv_from_url(url)
            except Exception as error:
                print(f"    Could not fetch: {error}")
                continue
            for row in rows:
                for name_field in ("winner_name", "loser_name"):
                    name = row.get(name_field, "")
                    for target in missing:
                        if normalize_player_name(target) == normalize_player_name(name):
                            challenger_matches.append((target, name, url))

        unique_found = {t[0] for t in challenger_matches}
        print(f"\nFound {len(unique_found)}/{len(missing)} of the missing players in Challenger-level match history:")
        for target in unique_found:
            print(f"  {target}")

        still_missing = [t for t in missing if t not in unique_found]
        if still_missing:
            print(f"\nStill not found anywhere (main tour or recent Challenger data): {', '.join(still_missing)}")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python check_coverage_gaps.py YOUR_ODDS_API_KEY")
        sys.exit(1)

    check_sportsbook_coverage(sys.argv[1])
    check_elo_coverage()