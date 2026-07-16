import json

from kalshi import get_markets_for_series
from tennis_utils import normalize_player_name
from tennis_elo import build_elo_ratings_from_files, get_elo_rating
from tennis_futures_compare import fetch_polymarket_tournament_event
from paper_trader import log_paper_trade, has_open_paper_trade
from position_sizing import position_size
from bankroll import get_current_bankroll
from risk_manager import check_can_trade

KALSHI_SERIES = "KXATP"
KALSHI_EVENT = "KXATP-26USO"
POLYMARKET_QUERY = "2026 US Open Winner"
POLYMARKET_EXCLUDE = "women"

# A two-way disagreement (Kalshi vs Polymarket) doesn't tell you WHICH one
# is wrong -- only that they differ. Requiring a third independent source
# (Elo) to agree with Polymarket's read before trading is a real
# corroboration check, not just noise-filtering on one comparison.
EDGE_THRESHOLD_PCT = 3.0
MIN_KALSHI_VOLUME = 100

# Above this Kalshi-implied probability, a player is a "heavy favorite" --
# our flat softmax Elo approximation understates true favorites badly
# (confirmed: Sinner's real ~55% corresponded to only ~24% under Elo), so
# we skip the Elo requirement for these and trust Polymarket vs Kalshi alone.
HEAVY_FAVORITE_THRESHOLD_PCT = 25.0


def build_kalshi_markets(series_ticker, event_ticker):
    markets = get_markets_for_series(series_ticker)
    result = {}
    for m in markets:
        if m.get("event_ticker") != event_ticker:
            continue
        try:
            bid = float(m.get("yes_bid_dollars"))
            ask = float(m.get("yes_ask_dollars"))
        except (TypeError, ValueError):
            continue
        prob = (bid + ask) / 2
        name = m.get("yes_sub_title")
        result[normalize_player_name(name)] = {"name": name, "prob": prob, "market": m}
    return result


def build_polymarket_probs(title_keyword, exclude_keyword=None):
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
        probs[normalize_player_name(player)] = yes_prob
    return probs


def build_elo_field_probabilities(kalshi_data, atp_elo_ratings):
    """
    Converts each candidate's single-match Elo rating into a tournament-
    winner probability via a softmax over the field (a Bradley-Terry-style
    extension of Elo -- Elo IS a Bradley-Terry model already). This is a
    real approximation, not a full bracket simulation: it ignores actual
    draw structure, seeding, and round-by-round survival odds, so treat it
    as cruder than the single-match Elo (which WAS properly backtested
    earlier with a large sample and good calibration). Good enough as a
    second opinion for corroboration, not as a standalone trading signal.
    """
    scores = {}
    for key, entry in kalshi_data.items():
        rating = get_elo_rating(entry["name"], atp_elo_ratings)
        scores[key] = 10 ** (rating / 400)

    total = sum(scores.values())
    if total <= 0:
        return {}
    return {key: score / total for key, score in scores.items()}


def decide_with_corroboration(kalshi_prob, poly_prob, elo_prob):
    """
    For HEAVY FAVORITES (Kalshi price >= 25%), skip the Elo requirement
    entirely and fall back to the plain Polymarket-vs-Kalshi comparison.
    This is because our Elo-to-tournament-winner conversion is a flat
    softmax over the field, which badly understates a true favorite's
    real odds (it doesn't model the compounding advantage of winning
    several rounds in a row) -- confirmed empirically when Sinner's real
    ~55% market price corresponded to only ~24% under our Elo estimate.
    That's not a small error, it's a structural mismatch for dominant
    players specifically.

    For everyone else (closer contenders, where the softmax distortion is
    much smaller), require genuine 2-of-3 corroboration: Polymarket AND
    Elo must agree on the direction of disagreement with Kalshi.
    """
    poly_edge = round((poly_prob - kalshi_prob) * 100, 4)
    elo_edge = round((elo_prob - kalshi_prob) * 100, 4)

    if kalshi_prob * 100 >= HEAVY_FAVORITE_THRESHOLD_PCT:
        if poly_edge >= EDGE_THRESHOLD_PCT:
            return "BUY YES", poly_edge, elo_edge, None
        if poly_edge <= -EDGE_THRESHOLD_PCT:
            return "BUY NO", poly_edge, elo_edge, None
        return "SKIP", poly_edge, elo_edge, (
            f"Heavy favorite ({kalshi_prob*100:.1f}%) -- Elo corroboration skipped "
            f"(unreliable for dominant players), Polymarket edge too small ({poly_edge:+.1f}%)"
        )

    same_direction = (poly_edge > 0 and elo_edge > 0) or (poly_edge < 0 and elo_edge < 0)
    if not same_direction:
        return "SKIP", poly_edge, elo_edge, "Polymarket and Elo disagree on direction -- no corroboration"

    # Use the smaller-magnitude edge as the "confirmed" edge size -- the
    # more conservative of the two corroborating estimates.
    confirmed_edge = poly_edge if abs(poly_edge) < abs(elo_edge) else elo_edge

    if confirmed_edge >= EDGE_THRESHOLD_PCT:
        return "BUY YES", poly_edge, elo_edge, None
    if confirmed_edge <= -EDGE_THRESHOLD_PCT:
        return "BUY NO", poly_edge, elo_edge, None

    return "SKIP", poly_edge, elo_edge, f"Corroborated edge too small ({confirmed_edge:+.1f}%)"


def main():
    print(f"Fetching Kalshi {KALSHI_EVENT} markets...")
    kalshi_data = build_kalshi_markets(KALSHI_SERIES, KALSHI_EVENT)
    print(f"  {len(kalshi_data)} Kalshi candidates found")

    print("Fetching Polymarket comparison data...")
    polymarket_probs = build_polymarket_probs(POLYMARKET_QUERY, exclude_keyword=POLYMARKET_EXCLUDE)
    print(f"  {len(polymarket_probs)} Polymarket candidates found")

    print("Building ATP Elo ratings (this takes a bit)...")
    elo_years = range(2019, 2027)
    elo_file_urls = [f"https://stats.tennismylife.org/data/{year}.csv" for year in elo_years]
    atp_elo_ratings = build_elo_ratings_from_files(elo_file_urls)

    elo_field_probs = build_elo_field_probabilities(kalshi_data, atp_elo_ratings)

    acted_on = 0

    for key, kalshi_entry in kalshi_data.items():
        poly_prob = polymarket_probs.get(key)
        elo_prob = elo_field_probs.get(key)
        if poly_prob is None or elo_prob is None:
            continue

        market = kalshi_entry["market"]
        kalshi_prob = kalshi_entry["prob"]
        name = kalshi_entry["name"]

        volume = market.get("volume_fp") or 0
        try:
            volume = float(volume)
        except (TypeError, ValueError):
            volume = 0.0
        if volume < MIN_KALSHI_VOLUME:
            continue

        decision, poly_edge, elo_edge, skip_reason = decide_with_corroboration(kalshi_prob, poly_prob, elo_prob)

        if decision == "SKIP":
            print(f"[SKIP] {name} -- {skip_reason} (Polymarket edge {poly_edge:+.1f}%, Elo edge {elo_edge:+.1f}%)")
            continue

        ticker = market.get("ticker")

        if has_open_paper_trade(ticker):
            print(f"Already paper-traded {ticker}, skipping duplicate.")
            continue

        can_trade, risk_reason = check_can_trade("Futures", ticker=ticker)
        if not can_trade:
            print(f"[BLOCKED] {name} -- {risk_reason}")
            continue

        market_like = {
            "ticker": ticker,
            "title": market.get("title"),
            "yes_bid_dollars": market.get("yes_bid_dollars"),
            "yes_ask_dollars": market.get("yes_ask_dollars"),
            "last_price_dollars": market.get("last_price_dollars"),
        }

        # Blend Polymarket + Elo as the "corroborated" probability for sizing
        # -- EXCEPT for heavy favorites, where Elo is known to be unreliable
        # (that's the whole reason we skipped it for the decision above);
        # using it for sizing would reintroduce the same problem.
        is_heavy_favorite = kalshi_prob * 100 >= HEAVY_FAVORITE_THRESHOLD_PCT
        consensus_prob = poly_prob if is_heavy_favorite else (poly_prob + elo_prob) / 2
        price = float(market.get("yes_ask_dollars")) if decision == "BUY YES" else (1 - float(market.get("yes_bid_dollars")))
        win_prob = consensus_prob if decision == "BUY YES" else (1 - consensus_prob)
        stake = position_size(get_current_bankroll(), win_prob, price)

        if stake <= 0:
            print(f"[SKIP] {name} -- Kelly sizing suggests no bet")
            continue

        reason = (
            f"Polymarket {round(poly_prob * 100, 1)}% & Elo {round(elo_prob * 100, 1)}% "
            f"both vs Kalshi {round(kalshi_prob * 100, 1)}% "
            f"(Polymarket edge {poly_edge:+.1f}%, Elo edge {elo_edge:+.1f}%), tournament: US Open"
        )

        log_paper_trade(
            market=market_like,
            category="Futures",
            decision=decision,
            reason=reason,
            stake=stake,
            features={
                "model_prob_pct": round(consensus_prob * 100, 1),
                "market_prob_pct": round(kalshi_prob * 100, 1),
                "edge_pct": round((consensus_prob - kalshi_prob) * 100, 1),
                "confidence_pct": None,
            },
        )
        acted_on += 1
        print(f"[{decision}] {name} (${stake:.2f}) -- {reason}")

    if acted_on == 0:
        print("\nNo new paper trades this run (nothing cleared corroborated edge bar, or risk limits blocked it).")
    else:
        print(f"\nLogged {acted_on} new paper trade(s) to paper_trades.csv")


if __name__ == "__main__":
    main()