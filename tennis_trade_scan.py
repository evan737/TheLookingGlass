import sys

from kalshi import get_registered_markets
from market_registry import MARKET_SERIES
from tennis_opportunity_engine import build_tennis_opportunities, TENNIS_SERIES_TICKERS
from tennis_elo import build_elo_ratings_from_files
from tennis_utils import normalize_player_name
from sportsbook_odds import fetch_atp_matches, fetch_wta_matches
from paper_trader import log_paper_trade, has_open_paper_trade
from position_sizing import position_size, calibrate_win_prob
from bankroll import get_current_bankroll
from risk_manager import check_can_trade

# Single-book edges are noisier than the multi-model weather ensemble, so
# demand a bit more edge before acting. Not tuned -- a starting point.
EDGE_THRESHOLD_PCT = 5.0
CONFIDENCE_THRESHOLD_PCT = 30.0  # lower than weather's 40 since 1-2 books can't reach that naturally


def decide(opp):
    if opp["confidence"] < CONFIDENCE_THRESHOLD_PCT:
        return "SKIP", f"Confidence too low ({opp['confidence']}%)"

    # Calibrated edge, not raw -- see paper_trade_scan.py's decide() for why.
    calibrated_model_prob_pct = calibrate_win_prob(opp["sportsbook_prob_pct"] / 100) * 100
    calibrated_edge_pct = round(calibrated_model_prob_pct - opp["market_prob_pct"], 1)

    if calibrated_edge_pct >= EDGE_THRESHOLD_PCT:
        return "BUY YES", (
            f"Model {opp['sportsbook_prob_pct']}% vs Market {opp['market_prob_pct']}%, "
            f"edge +{opp['edge_pct']}% (calibrated +{calibrated_edge_pct}%), confidence {opp['confidence']}%, "
            f"tier: {opp['tournament_tier']}"
        )

    if calibrated_edge_pct <= -EDGE_THRESHOLD_PCT:
        return "BUY NO", (
            f"Model {opp['sportsbook_prob_pct']}% vs Market {opp['market_prob_pct']}%, "
            f"edge {opp['edge_pct']}% (calibrated {calibrated_edge_pct}%), confidence {opp['confidence']}%, "
            f"tier: {opp['tournament_tier']}"
        )

    return "SKIP", f"Edge too small after calibration ({calibrated_edge_pct}%, raw {opp['edge_pct']}%)"


def main():
    if len(sys.argv) < 2:
        print("Usage: python tennis_trade_scan.py YOUR_ODDS_API_KEY")
        sys.exit(1)

    api_key = sys.argv[1]

    print("Fetching live Kalshi tennis markets...")
    markets = get_registered_markets(MARKET_SERIES)
    tennis_markets = [m for m in markets if m.get("series_ticker") in TENNIS_SERIES_TICKERS]

    target_surnames = {
        normalize_player_name(m.get("yes_sub_title", ""))
        for m in tennis_markets
    }
    target_surnames.discard("")

    if not target_surnames:
        print("No open tennis markets to evaluate.")
        return

    print(f"Looking up odds for {len(target_surnames)} specific players...")
    atp_matches = fetch_atp_matches(api_key, target_surnames)
    wta_matches = fetch_wta_matches(api_key, target_surnames)

    print("Building ATP Elo ratings...")
    elo_years = range(2019, 2027)
    elo_file_urls = [f"https://stats.tennismylife.org/data/{year}.csv" for year in elo_years]
    atp_elo_ratings = build_elo_ratings_from_files(elo_file_urls)

    opportunities = build_tennis_opportunities(
        tennis_markets, atp_matches + wta_matches, atp_elo_ratings=atp_elo_ratings
    )

    if not opportunities:
        print("No opportunities to evaluate.")
        return

    acted_on = 0

    for opp in opportunities:
        decision, reason = decide(opp)

        if decision == "SKIP":
            continue

        if has_open_paper_trade(opp["ticker"]):
            print(f"Already paper-traded {opp['ticker']}, skipping duplicate.")
            continue

        can_trade, risk_reason = check_can_trade("Tennis", ticker=opp["ticker"])
        if not can_trade:
            print(f"[BLOCKED] {opp['player']} -- {risk_reason}")
            continue

        market_like = {
            "ticker": opp["ticker"],
            "title": opp["title"],
            # Tennis opportunities don't carry raw yes_bid/yes_ask through
            # (only market_prob_pct as a midpoint) -- log what we have.
            "yes_bid_dollars": None,
            "yes_ask_dollars": opp["market_prob_pct"] / 100,
            "last_price_dollars": None,
        }

        price = opp["market_prob_pct"] / 100 if decision == "BUY YES" else (1 - opp["market_prob_pct"] / 100)
        win_prob = (opp["sportsbook_prob_pct"] / 100) if decision == "BUY YES" else (1 - opp["sportsbook_prob_pct"] / 100)
        win_prob = calibrate_win_prob(win_prob)
        stake = position_size(get_current_bankroll(), win_prob, price)

        if stake <= 0:
            print(f"[SKIP] {opp['player']} -- Kelly sizing suggests no bet")
            continue

        log_paper_trade(
            market=market_like,
            category="Tennis",
            decision=decision,
            reason=reason,
            stake=stake,
            features={
                "model_prob_pct": opp["sportsbook_prob_pct"],
                "market_prob_pct": opp["market_prob_pct"],
                "edge_pct": opp["edge_pct"],
                "confidence_pct": opp["confidence"],
            },
        )
        acted_on += 1
        print(f"[{decision}] {opp['player']} ({opp['tournament_tier']}, ${stake:.2f}) -- {reason}")

    if acted_on == 0:
        print("No new paper trades this run (nothing cleared the edge/confidence bar, or risk limits blocked it).")
    else:
        print(f"\nLogged {acted_on} new paper trade(s) to paper_trades.csv")


if __name__ == "__main__":
    main()