import sys

from kalshi import get_registered_markets
from market_registry import MARKET_SERIES
from sportsbook_odds import fetch_atp_matches, fetch_wta_matches
from tennis_opportunity_engine import build_tennis_opportunities, TENNIS_SERIES_TICKERS
from tennis_utils import normalize_player_name


def main():
    if len(sys.argv) < 2:
        print("Usage: python find_tennis_opportunities.py YOUR_ODDS_API_KEY")
        sys.exit(1)

    api_key = sys.argv[1]

    print("Fetching live Kalshi tennis markets...")
    markets = get_registered_markets(MARKET_SERIES)
    tennis_markets = [m for m in markets if m.get("series_ticker") in TENNIS_SERIES_TICKERS]
    print(f"Loaded {len(tennis_markets)} Kalshi tennis markets (out of {len(markets)} total)")

    # Only spend odds-lookup API calls on players Kalshi actually has open
    # markets for -- keeps us well within the free tier's rate limit.
    target_surnames = {
        normalize_player_name(m.get("yes_sub_title", ""))
        for m in tennis_markets
    }
    target_surnames.discard("")
    print(f"Looking up odds for {len(target_surnames)} specific players...")

    atp_matches = fetch_atp_matches(api_key, target_surnames)
    wta_matches = fetch_wta_matches(api_key, target_surnames)
    print(f"Got {len(atp_matches)} ATP matches, {len(wta_matches)} WTA matches with odds")

    from tennis_elo import build_elo_ratings_from_files

    print("Building ATP Elo ratings (this takes a bit)...")
    elo_years = range(2019, 2027)
    elo_file_urls = [f"https://stats.tennismylife.org/data/{year}.csv" for year in elo_years]
    atp_elo_ratings = build_elo_ratings_from_files(elo_file_urls)

    opportunities = build_tennis_opportunities(tennis_markets, atp_matches + wta_matches, atp_elo_ratings=atp_elo_ratings)
    
    if not opportunities:
        print("No opportunities found -- no sportsbook currently has a "
              "matching line for these specific players.")
        return

    header = (
        f"{'Player':<22}{'Tournament':<22}{'Market %':<10}"
        f"{'Book %':<9}{'Books':<7}{'Edge %':<9}{'Confidence':<12}{'Volume'}"
    )
    print()
    print(header)
    print("-" * len(header))
    for opp in opportunities:
        print(
            f"{opp['player'][:21]:<22}"
            f"{(opp['tournament'] or '')[:21]:<22}"
            f"{opp['market_prob_pct']:<10}"
            f"{opp['sportsbook_prob_pct']:<9}"
            f"{opp['num_books']:<7}"
            f"{opp['edge_pct']:<9}"
            f"{opp['confidence']:<12}"
            f"{opp['volume']}"
        )


if __name__ == "__main__":
    main()