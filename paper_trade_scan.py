from kalshi import get_registered_markets
from market_registry import MARKET_SERIES
from opportunity_engine import build_opportunities
from paper_trader import log_paper_trade, has_open_paper_trade

# How big an edge has to be, and how much we trust the forecast behind it,
# before we bother paper-trading it at all. These are starting points, not
# tuned values -- adjust as you see how the log performs over time.
EDGE_THRESHOLD_PCT = 5.0
CONFIDENCE_THRESHOLD_PCT = 40.0


def decide(opp):
    """
    Returns (decision, reason). decision is one of "BUY YES", "BUY NO",
    or "SKIP". This is intentionally simple -- a real sizing/risk model
    (Kelly criterion, position caps, etc.) would go here later once
    there's enough logged history to know if the edge signal is any good.
    """
    if opp["confidence"] < CONFIDENCE_THRESHOLD_PCT:
        return "SKIP", f"Confidence too low ({opp['confidence']}%)"

    if opp["edge_pct"] >= EDGE_THRESHOLD_PCT:
        return "BUY YES", (
            f"Model {opp['model_prob_pct']}% vs Market {opp['market_prob_pct']}%, "
            f"edge +{opp['edge_pct']}%, confidence {opp['confidence']}%"
        )

    if opp["edge_pct"] <= -EDGE_THRESHOLD_PCT:
        return "BUY NO", (
            f"Model {opp['model_prob_pct']}% vs Market {opp['market_prob_pct']}%, "
            f"edge {opp['edge_pct']}%, confidence {opp['confidence']}%"
        )

    return "SKIP", f"Edge too small ({opp['edge_pct']}%)"


def main():
    print("Fetching live markets and computing opportunities...")
    markets = get_registered_markets(MARKET_SERIES)
    opportunities = build_opportunities(markets)

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

        market_like = {
            "ticker": opp["ticker"],
            "title": opp["title"],
            "yes_bid_dollars": opp["yes_bid_dollars"],
            "yes_ask_dollars": opp["yes_ask_dollars"],
            "last_price_dollars": opp["last_price_dollars"],
        }

        log_paper_trade(
            market=market_like,
            category="Weather",
            decision=decision,
            reason=reason,
        )
        acted_on += 1
        print(f"[{decision}] {opp['city']} {opp['bracket']} ({opp['target_date']}) -- {reason}")

    if acted_on == 0:
        print("No new paper trades this run (nothing cleared the edge/confidence bar).")
    else:
        print(f"\nLogged {acted_on} new paper trade(s) to paper_trades.csv")


if __name__ == "__main__":
    main()