from kalshi import get_registered_markets
from market_registry import MARKET_SERIES
from opportunity_engine import build_opportunities


def main():
    print("Fetching live markets...")
    markets = get_registered_markets(MARKET_SERIES)
    print(f"Loaded {len(markets)} registered markets")

    print("Fetching forecasts and computing opportunities...")
    opportunities = build_opportunities(markets)

    if not opportunities:
        print("No opportunities found. Either no registered weather markets "
              "are open right now, or their event dates fall outside the "
              "10-day forecast window.")
        return

    header = (
        f"{'City':<14}{'Bracket':<14}{'Date':<12}{'Market %':<10}"
        f"{'Model %':<10}{'Edge %':<9}{'Confidence':<12}{'Volume'}"
    )
    print()
    print(header)
    print("-" * len(header))
    for opp in opportunities:
        print(
            f"{opp['city']:<14}"
            f"{(opp['bracket'] or '')[:13]:<14}"
            f"{(opp['target_date'] or ''):<12}"
            f"{opp['market_prob_pct']:<10}"
            f"{opp['model_prob_pct']:<10}"
            f"{opp['edge_pct']:<9}"
            f"{opp['confidence']:<12}"
            f"{opp['volume']}"
        )


if __name__ == "__main__":
    main()