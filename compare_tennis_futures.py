import json

from kalshi import get_markets_for_series
from tennis_utils import normalize_player_name
from tennis_futures_compare import fetch_polymarket_tournament_event


def kalshi_implied_probability(market):
    try:
        bid = float(market.get("yes_bid_dollars"))
        ask = float(market.get("yes_ask_dollars"))
        return (bid + ask) / 2
    except (TypeError, ValueError):
        return None


def build_kalshi_probabilities(series_ticker, event_ticker):
    markets = get_markets_for_series(series_ticker)
    probs = {}
    for m in markets:
        if m.get("event_ticker") != event_ticker:
            continue
        prob = kalshi_implied_probability(m)
        if prob is None:
            continue
        name = m.get("yes_sub_title")
        probs[normalize_player_name(name)] = (name, prob)
    return probs


def build_polymarket_probabilities(title_keyword, exclude_keyword=None):
    """
    IMPORTANT: Polymarket's outcomePrices field is a JSON-encoded STRING
    (e.g. '["0.54", "0.46"]'), not an actual list -- must json.loads() it
    first. Also uses groupItemTitle for the player name (e.g. "Jannik
    Sinner") directly, rather than regex-parsing the question text.
    """
    event = fetch_polymarket_tournament_event(title_keyword, exclude_keyword=exclude_keyword)
    if not event:
        return {}

    probs = {}
    for m in event.get("markets", []):
        player = m.get("groupItemTitle")
        outcome_prices_raw = m.get("outcomePrices")
        if not player or not outcome_prices_raw:
            continue

        try:
            outcome_prices = json.loads(outcome_prices_raw)
            yes_prob = float(outcome_prices[0])
        except (TypeError, ValueError, IndexError, json.JSONDecodeError):
            continue

        probs[normalize_player_name(player)] = (player, yes_prob)
    return probs


def compare(kalshi_probs, polymarket_probs):
    rows = []
    all_keys = set(kalshi_probs.keys()) | set(polymarket_probs.keys())

    for key in all_keys:
        kalshi_entry = kalshi_probs.get(key)
        poly_entry = polymarket_probs.get(key)

        if not kalshi_entry or not poly_entry:
            continue  # only compare players present on both platforms

        name = kalshi_entry[0]
        kalshi_prob = kalshi_entry[1]
        poly_prob = poly_entry[1]
        edge = poly_prob - kalshi_prob

        rows.append({
            "player": name,
            "kalshi_pct": round(kalshi_prob * 100, 1),
            "polymarket_pct": round(poly_prob * 100, 1),
            "edge_pct": round(edge * 100, 1),
        })

    rows.sort(key=lambda r: abs(r["edge_pct"]), reverse=True)
    return rows


if __name__ == "__main__":
    print("Fetching Kalshi KXATP-26USO (Men's US Open winner)...")
    kalshi_probs = build_kalshi_probabilities("KXATP", "KXATP-26USO")
    print(f"  {len(kalshi_probs)} Kalshi candidates found")

    print("Fetching Polymarket Men's US Open Winner...")
    polymarket_probs = build_polymarket_probabilities("2026 US Open Winner", exclude_keyword="women")
    print(f"  {len(polymarket_probs)} Polymarket candidates found")

    rows = compare(kalshi_probs, polymarket_probs)

    if not rows:
        print("\nNo matched players between the two platforms.")
    else:
        print(f"\n=== {len(rows)} matched players, ranked by edge size ===")
        print(f"{'Player':<25}{'Kalshi %':<10}{'Polymarket %':<14}{'Edge %'}")
        print("-" * 60)
        for r in rows:
            print(f"{r['player']:<25}{r['kalshi_pct']:<10}{r['polymarket_pct']:<14}{r['edge_pct']:+.1f}")