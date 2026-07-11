import csv
import io
import requests
from collections import defaultdict

# Jeff Sackmann's original tennis_atp/tennis_wta repos appear to be
# inaccessible as of this writing (404s from GitHub directly). Using
# TennisMyLife instead -- an actively maintained continuation of the same
# project, same non-commercial license lineage, live-updated through
# current tournaments. https://stats.tennismylife.org
DATA_FILES_API = "https://stats.tennismylife.org/api/data-files"

K_FACTOR = 32  # standard Elo update size -- simple fixed value, no surface/match-count adjustment yet
STARTING_ELO = 1500


def discover_data_files():
    """
    Lists every available data file from TennisMyLife's API. Run this
    first (via the __main__ block below) to see the real file names
    before assuming any particular naming convention.
    """
    response = requests.get(DATA_FILES_API, timeout=30)
    response.raise_for_status()
    return response.json().get("files", [])


def fetch_csv_from_url(url):
    response = requests.get(url, timeout=30)
    response.raise_for_status()
    reader = csv.DictReader(io.StringIO(response.text))
    rows = list(reader)
    if rows:
        print(f"  Columns found: {list(rows[0].keys())[:10]}... ({len(rows[0])} total)")
    return rows


def build_elo_ratings_from_files(file_urls):
    """
    file_urls: list of CSV URLs containing match data (winner_name,
    loser_name, tourney_date columns expected -- same convention as
    Sackmann's original files, since TennisMyLife is explicitly modeled
    on that format).
    """
    all_matches = []
    for url in file_urls:
        print(f"Fetching {url}...")
        try:
            rows = fetch_csv_from_url(url)
            all_matches.extend(rows)
        except Exception as error:
            print(f"  Could not fetch: {error}")

    all_matches.sort(key=lambda row: row.get("tourney_date", ""))

    ratings = defaultdict(lambda: STARTING_ELO)

    for match in all_matches:
        winner = match.get("winner_name")
        loser = match.get("loser_name")
        if not winner or not loser:
            continue

        winner_elo = ratings[winner]
        loser_elo = ratings[loser]

        expected_winner = 1 / (1 + 10 ** ((loser_elo - winner_elo) / 400))
        expected_loser = 1 - expected_winner

        ratings[winner] = winner_elo + K_FACTOR * (1 - expected_winner)
        ratings[loser] = loser_elo + K_FACTOR * (0 - expected_loser)

    print(f"Built ratings for {len(ratings)} players from {len(all_matches)} matches")
    return dict(ratings)


def elo_win_probability(rating_a, rating_b):
    """Standard Elo win-probability formula."""
    return 1 / (1 + 10 ** ((rating_b - rating_a) / 400))


def get_elo_rating(player_name, ratings, default=STARTING_ELO):
    """
    Looks up a player's Elo rating. Tries an exact name match first (since
    Kalshi's yes_sub_title and TennisMyLife's winner_name/loser_name both
    appear to use "Firstname Lastname" format); falls back to matching by
    surname alone if no exact match is found. Returns `default` (the
    starting Elo) if the player has no rating history at all -- meaning
    this is treated as "no information", not "bad player".
    """
    if player_name in ratings:
        return ratings[player_name]

    from tennis_utils import normalize_player_name
    target_surname = normalize_player_name(player_name)
    for name, rating in ratings.items():
        if normalize_player_name(name) == target_surname:
            return rating

    return default


if __name__ == "__main__":
    # Confirmed real file list from stats.tennismylife.org/api/data-files.
    # Using main tour-level yearly files only (not _challenger or
    # atp_quali variants) to match what Kalshi's KXATPMATCH actually
    # covers -- tour-level matches, not lower-tier events.
    #
    # NOTE: this source appears to be ATP-only -- no WTA files were found
    # in the discovery step. WTA opportunities will keep relying on
    # sportsbook consensus alone until a comparable WTA data source
    # is found.
    years = range(2019, 2027)
    file_urls = [f"https://stats.tennismylife.org/data/{year}.csv" for year in years]

    atp_ratings = build_elo_ratings_from_files(file_urls)

    top_10 = sorted(atp_ratings.items(), key=lambda x: x[1], reverse=True)[:10]
    print("\nTop 10 ATP players by Elo:")
    for name, rating in top_10:
        print(f"  {name}: {round(rating)}")