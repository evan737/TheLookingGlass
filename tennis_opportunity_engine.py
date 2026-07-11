import re
from statistics import mean, pstdev

from odds_utils import decimal_to_probability, devig_two_way
from tennis_utils import normalize_player_name
from tennis_elo import get_elo_rating, elo_win_probability
from tennis_tiers import infer_tournament_tier

TENNIS_SERIES_TICKERS = ("KXATPMATCH", "KXWTAMATCH")


def market_implied_probability(market):
    yes_bid = market.get("yes_bid_dollars")
    yes_ask = market.get("yes_ask_dollars")
    if yes_bid is None or yes_ask is None:
        return None
    try:
        return (float(yes_bid) + float(yes_ask)) / 2.0
    except (TypeError, ValueError):
        return None


def build_player_probability_index(sportsbook_matches):
    """
    sportsbook_matches: list from sportsbook_odds.fetch_atp_matches() /
    fetch_wta_matches(), each with 'home', 'away', 'league', and a
    'bookmakers' dict of {book_name: (home_decimal_odds, away_decimal_odds)}.

    De-vigs each book's line and buckets probabilities by normalized
    surname. A player's list of probabilities (one per book that has a
    line) gives a genuine confidence signal from book agreement, same
    idea as using multi-model spread for the weather forecasts.

    Also builds a surname -> tournament/league-name lookup, since Kalshi's
    own market data doesn't include the tournament name at all -- the
    sportsbook match data (the 'league' field) is the only place we
    actually have it.
    """
    prob_index = {}
    tournament_index = {}

    for match in sportsbook_matches:
        home_key = normalize_player_name(match.get("home"))
        away_key = normalize_player_name(match.get("away"))
        league = match.get("league")

        if home_key and league:
            tournament_index[home_key] = league
        if away_key and league:
            tournament_index[away_key] = league

        for book_name, (home_odds, away_odds) in match.get("bookmakers", {}).items():
            home_prob_raw = decimal_to_probability(home_odds)
            away_prob_raw = decimal_to_probability(away_odds)
            fair_home, fair_away = devig_two_way(home_prob_raw, away_prob_raw)

            if fair_home is None:
                continue

            if home_key:
                prob_index.setdefault(home_key, []).append(fair_home)
            if away_key:
                prob_index.setdefault(away_key, []).append(fair_away)

    return prob_index, tournament_index


def parse_opponent_name(title, player_name):
    """
    Kalshi's market title looks like:
    'Will Novak Djokovic win the Sinner vs Djokovic: Semifinal match?'

    Pulls the "X vs Y" part and returns whichever side ISN'T player_name's
    surname -- i.e. the opponent. Returns None if the pattern doesn't match
    (in which case Elo just won't be computed for this market).
    """
    match = re.search(r"the (.+?) vs (.+?):", title or "")
    if not match:
        return None

    side_a, side_b = match.group(1).strip(), match.group(2).strip()
    player_surname = normalize_player_name(player_name)

    if normalize_player_name(side_a) == player_surname:
        return side_b
    if normalize_player_name(side_b) == player_surname:
        return side_a
    return None


def build_tennis_opportunities(markets, sportsbook_matches, atp_elo_ratings=None):
    """
    markets: raw Kalshi market dicts (only KXATPMATCH/KXWTAMATCH series
             are used; everything else is skipped)
    sportsbook_matches: raw list from sportsbook_odds.fetch_atp_matches() /
                        fetch_wta_matches()
    atp_elo_ratings: optional dict from tennis_elo.build_elo_ratings_from_files().
                     ATP only right now -- no WTA Elo source found yet, so
                     WTA markets just won't get an elo_prob_pct.

    Elo is added as an independent, SIDE-BY-SIDE estimate rather than
    blended into the edge calculation -- edge/confidence are still based
    on sportsbook consensus alone, same as before. This is deliberate:
    blending two unvalidated models together would hide whether either one
    is actually any good. Once there's a track record for each, blending
    (or picking a winner) becomes a more informed decision.
    """
    player_index, tournament_index = build_player_probability_index(sportsbook_matches)
    opportunities = []

    for market in markets:
        series_ticker = market.get("series_ticker")
        if series_ticker not in TENNIS_SERIES_TICKERS:
            continue

        player_label = market.get("yes_sub_title", "")
        key = normalize_player_name(player_label)
        probs = player_index.get(key)
        if not probs:
            continue  # no sportsbook currently has a line on this player

        sportsbook_prob = mean(probs)
        spread = pstdev(probs) if len(probs) > 1 else 0.05  # can't judge agreement with only 1 book

        market_prob = market_implied_probability(market)
        if market_prob is None:
            continue

        volume = market.get("volume_fp") or 0
        try:
            volume = float(volume)
        except (TypeError, ValueError):
            volume = 0.0
        if volume <= 0:
            continue  # skip untouched brackets -- a flat price with no volume isn't real

        edge = sportsbook_prob - market_prob
        confidence = round((1 - min(spread / 0.1, 1)) * 100, 1)

        elo_prob_pct = None
        if atp_elo_ratings and series_ticker == "KXATPMATCH":
            opponent_name = parse_opponent_name(market.get("title"), player_label)
            if opponent_name:
                player_elo = get_elo_rating(player_label, atp_elo_ratings)
                opponent_elo = get_elo_rating(opponent_name, atp_elo_ratings)
                elo_prob = elo_win_probability(player_elo, opponent_elo)
                elo_prob_pct = round(elo_prob * 100, 1)

        tournament_name = tournament_index.get(key)

        opportunities.append({
            "player": player_label,
            "tournament": tournament_name,
            "tournament_tier": infer_tournament_tier(tournament_name),
            "ticker": market.get("ticker"),
            "title": market.get("title"),
            "market_prob_pct": round(market_prob * 100, 1),
            "sportsbook_prob_pct": round(sportsbook_prob * 100, 1),
            "elo_prob_pct": elo_prob_pct,
            "num_books": len(probs),
            "edge_pct": round(edge * 100, 1),
            "confidence": confidence,
            "volume": volume,
        })

    opportunities.sort(key=lambda o: abs(o["edge_pct"]), reverse=True)
    return opportunities