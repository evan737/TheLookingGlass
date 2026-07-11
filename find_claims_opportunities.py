import sys

from kalshi import get_registered_markets
from market_registry import MARKET_SERIES
from claims_opportunity_engine import build_claims_opportunities, CLAIMS_SERIES_TICKER


def main():
    if len(sys.argv) < 2:
        print("Usage: python find_claims_opportunities.py YOUR_FRED_API_KEY")
        sys.exit(1)

    fred_api_key = sys.argv[1]

    print("Fetching live Kalshi jobless claims markets...")
    markets = get_registered_markets(MARKET_SERIES)
    claims_markets = [m for m in markets if m.get("series_ticker") == CLAIMS_SERIES_TICKER]
    print(f"Found {len(claims_markets)} KXJOBLESSCLAIMS markets (out of {len(markets)} total)")

    opportunities = build_claims_opportunities(claims_markets, fred_api_key)

    if not opportunities:
        print("No opportunities found -- either no KXJOBLESSCLAIMS markets "
              "are open, or the FRED forecast couldn't be built. If markets "
              "exist but nothing showed up, print a raw market dict to check "
              "the actual field names (see caveat in claims_opportunity_engine.py).")
        return

    header = (
        f"{'Bracket':<24}{'Market %':<10}{'Model %':<10}{'Edge %':<9}"
        f"{'Last Actual':<14}{'Forecast':<12}{'Volume'}"
    )
    print()
    print(header)
    print("-" * len(header))
    for opp in opportunities:
        print(
            f"{(opp['bracket'] or '')[:23]:<24}"
            f"{opp['market_prob_pct']:<10}"
            f"{opp['model_prob_pct']:<10}"
            f"{opp['edge_pct']:<9}"
            f"{opp['last_observed_value']:<14}"
            f"{opp['forecast_mean']:<12}"
            f"{opp['volume']}"
        )


if __name__ == "__main__":
    main()