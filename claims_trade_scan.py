import sys

from kalshi import get_registered_markets
from market_registry import MARKET_SERIES
from claims_opportunity_engine import build_claims_opportunities, CLAIMS_SERIES_TICKER
from paper_trader import log_paper_trade, has_open_paper_trade
from position_sizing import position_size
from bankroll import get_current_bankroll
from risk_manager import check_can_trade

# Higher bar than the weather engine (5%) since this model is cruder --
# a single trend-based estimate, not a genuine multi-source ensemble.
# Demanding a bigger edge before acting is a simple way to compensate for
# that lower confidence in the model itself.
EDGE_THRESHOLD_PCT = 10.0


def decide(opp):
    if opp["edge_pct"] >= EDGE_THRESHOLD_PCT:
        return "BUY YES", (
            f"Model {opp['model_prob_pct']}% vs Market {opp['market_prob_pct']}%, "
            f"edge +{opp['edge_pct']}% (FRED trend model, last actual "
            f"{opp['last_observed_value']}, forecast {opp['forecast_mean']})"
        )
    if opp["edge_pct"] <= -EDGE_THRESHOLD_PCT:
        return "BUY NO", (
            f"Model {opp['model_prob_pct']}% vs Market {opp['market_prob_pct']}%, "
            f"edge {opp['edge_pct']}% (FRED trend model, last actual "
            f"{opp['last_observed_value']}, forecast {opp['forecast_mean']})"
        )
    return "SKIP", f"Edge too small ({opp['edge_pct']}%)"


def main():
    if len(sys.argv) < 2:
        print("Usage: python claims_trade_scan.py YOUR_FRED_API_KEY")
        sys.exit(1)

    fred_api_key = sys.argv[1]

    print("Fetching live Kalshi jobless claims markets...")
    markets = get_registered_markets(MARKET_SERIES)
    claims_markets = [m for m in markets if m.get("series_ticker") == CLAIMS_SERIES_TICKER]

    opportunities = build_claims_opportunities(claims_markets, fred_api_key)

    if not opportunities:
        print("No opportunities to evaluate (no volume-backed markets found).")
        return

    acted_on = 0

    for opp in opportunities:
        decision, reason = decide(opp)

        if decision == "SKIP":
            print(f"[SKIP] {opp['bracket']} -- {reason}")
            continue

        if has_open_paper_trade(opp["ticker"]):
            print(f"Already paper-traded {opp['ticker']}, skipping duplicate.")
            continue

        can_trade, risk_reason = check_can_trade("Economics", ticker=opp["ticker"])
        if not can_trade:
            print(f"[BLOCKED] {opp['bracket']} -- {risk_reason}")
            continue

        market_like = {
            "ticker": opp["ticker"],
            "title": opp["title"],
            "yes_bid_dollars": opp["yes_bid_dollars"],
            "yes_ask_dollars": opp["yes_ask_dollars"],
            "last_price_dollars": opp["last_price_dollars"],
        }

        # Kelly sizing: use the model's stated probability and the price
        # of the side we're actually buying -- same approach as the
        # weather/tennis/futures scanners, so Economics stakes scale with
        # edge/confidence instead of always betting a flat $10.
        price = float(opp["yes_ask_dollars"]) if decision == "BUY YES" else (1 - float(opp["yes_bid_dollars"]))
        win_prob = (opp["model_prob_pct"] / 100) if decision == "BUY YES" else (1 - opp["model_prob_pct"] / 100)
        stake = position_size(get_current_bankroll(), win_prob, price)

        if stake <= 0:
            print(f"[SKIP] {opp['bracket']} -- Kelly sizing suggests no bet")
            continue

        log_paper_trade(
            market=market_like,
            category="Economics",
            decision=decision,
            reason=reason,
            stake=stake,
            features={
                "model_prob_pct": opp["model_prob_pct"],
                "market_prob_pct": opp["market_prob_pct"],
                "edge_pct": opp["edge_pct"],
            },
        )
        acted_on += 1
        print(f"[{decision}] {opp['bracket']} (${stake:.2f}) -- {reason}")

    if acted_on == 0:
        print("No new paper trades this run (nothing cleared the edge bar).")
    else:
        print(f"\nLogged {acted_on} new paper trade(s) to paper_trades.csv")


if __name__ == "__main__":
    main()