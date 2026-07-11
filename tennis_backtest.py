"""
Walk-forward backtest of the tennis Elo model: for every historical match,
computes what the model would have predicted using ONLY ratings built from
matches strictly before that one (never peeking at the match's own result
or anything after it), then checks that prediction against what actually
happened.

This is honest in a way the weather backtest can't be: Elo ratings are
built entirely from past match results, which we genuinely have archived
(unlike weather forecasts, which aren't available in historical archived
form for free). So this produces real, valid Brier-score and calibration
data across potentially thousands of matches -- a much bigger, more
meaningful sample than waiting weeks for live paper trades to settle.

NOTE: this tests whether the ELO MODEL ITSELF is well-calibrated -- it
does not test edge against Kalshi's actual historical prices (Kalshi's
ATP match markets are new enough that there may be little to no historical
settled data to compare against; that's a natural follow-up once this
core self-calibration check is confirmed working).
"""
from statistics import mean
from collections import defaultdict

from tennis_elo import fetch_csv_from_url, K_FACTOR, STARTING_ELO, elo_win_probability


def walk_forward_backtest(file_urls, warmup_matches_per_player=5):
    """
    warmup_matches_per_player: skip recording predictions for a player's
    first N matches, since their rating is still mostly uninformative
    noise at STARTING_ELO. Ratings still get updated during warmup --
    only the *predictions* are excluded from the scored sample.

    Returns a list of {"predicted_prob_winner_wins": p} for every scored
    match -- the winner's perspective. evaluate_predictions() below
    expands each into both perspectives for proper calibration testing.
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
    print(f"\nProcessing {len(all_matches)} matches in chronological order...")

    ratings = defaultdict(lambda: STARTING_ELO)
    match_counts = defaultdict(int)
    predictions = []

    for match in all_matches:
        winner = match.get("winner_name")
        loser = match.get("loser_name")
        if not winner or not loser:
            continue

        winner_elo = ratings[winner]
        loser_elo = ratings[loser]

        # Predict BEFORE updating -- this is the critical walk-forward step
        both_warmed_up = (
            match_counts[winner] >= warmup_matches_per_player
            and match_counts[loser] >= warmup_matches_per_player
        )
        if both_warmed_up:
            predicted_prob_winner_wins = elo_win_probability(winner_elo, loser_elo)
            predictions.append({"predicted_prob_winner_wins": predicted_prob_winner_wins})

        # Now update ratings with this match's real result
        expected_winner = 1 / (1 + 10 ** ((loser_elo - winner_elo) / 400))
        expected_loser = 1 - expected_winner
        ratings[winner] = winner_elo + K_FACTOR * (1 - expected_winner)
        ratings[loser] = loser_elo + K_FACTOR * (0 - expected_loser)

        match_counts[winner] += 1
        match_counts[loser] += 1

    return predictions, ratings


def evaluate_predictions(predictions):
    if not predictions:
        print("No predictions to evaluate (not enough warmed-up matches).")
        return

    n = len(predictions)
    print(f"\n=== Walk-forward backtest results across {n} matches ===")

    # Brier score from the winner's perspective: (predicted - 1)^2 for
    # every match. This is mathematically equivalent to averaging over
    # both perspectives (winner AND loser rows), so this single-pass
    # version is correct, just computed the simple way.
    brier = mean((p["predicted_prob_winner_wins"] - 1) ** 2 for p in predictions)
    print(f"Overall Brier score: {brier:.4f} (0.25 = coin-flip guessing, 0 = perfect)")

    correct = sum(1 for p in predictions if p["predicted_prob_winner_wins"] > 0.5)
    print(f"Model favored the actual winner in {correct}/{n} matches ({correct/n*100:.1f}%)")

    # Proper calibration table: expand each match into BOTH perspectives
    # (winner's predicted prob + actual=1, loser's predicted prob + actual=0)
    # -- this is the standard way to test calibration of a binary predictor,
    # and avoids the trivial "100% win rate" bug of only using one side.
    symmetric_records = []
    for p in predictions:
        pw = p["predicted_prob_winner_wins"]
        symmetric_records.append({"predicted": pw, "actual": 1})
        symmetric_records.append({"predicted": 1 - pw, "actual": 0})

    buckets = [(0.0, 0.1), (0.1, 0.2), (0.2, 0.3), (0.3, 0.4), (0.4, 0.5),
               (0.5, 0.6), (0.6, 0.7), (0.7, 0.8), (0.8, 0.9), (0.9, 1.01)]

    print("\nCalibration table (both perspectives per match, 2N records):")
    print(f"{'Predicted range':<18}{'N':<10}{'Actual win rate':<18}{'Expected (bucket mid)'}")
    for low, high in buckets:
        bucket = [r for r in symmetric_records if low <= r["predicted"] < high]
        if not bucket:
            continue
        actual_rate = mean(r["actual"] for r in bucket)
        expected_mid = (low + high) / 2 if high < 1.01 else 0.95
        print(f"{low:.1f}-{min(high,1.0):.1f}{'':<12}{len(bucket):<10}{actual_rate*100:<18.1f}{expected_mid*100:.0f}%")

    print("\nIf actual win rate tracks the expected bucket midpoint closely, "
          "Elo is well-calibrated on this data. Systematic divergence (e.g. "
          "the model consistently overstates favorites) would show up as a "
          "gap that grows in one direction as you move through the buckets.")


if __name__ == "__main__":
    years = range(2015, 2027)
    file_urls = [f"https://stats.tennismylife.org/data/{year}.csv" for year in years]

    predictions, final_ratings = walk_forward_backtest(file_urls)
    evaluate_predictions(predictions)