import csv
import re
from pathlib import Path
from statistics import mean

TRADE_LOG = Path("paper_trades.csv")
OLD_TRADE_LOG = Path("paper_trades_old.csv")
RESULTS_LOG = Path("paper_trade_results.csv")


def extract_model_prob_pct(reason):
    """
    Pulls the model's stated P(YES) out of the reason string logged by
    the trade-scan scripts (e.g. "Model 70.7% vs Market 87.0%, edge...").

    This is a bit fragile -- it depends on every trade-scan script phrasing
    its reason string the same way. If a future engine's reason string
    doesn't start with "Model X%", this will just skip those trades rather
    than crash; consider adding a real model_prob_pct column to
    paper_trades.csv instead if this becomes a maintenance headache.
    """
    match = re.search(r"Model ([\d.]+)%", reason or "")
    if not match:
        return None
    return float(match.group(1))


def extract_abs_edge_pct(reason):
    match = re.search(r"edge ([+-]?[\d.]+)%", reason or "")
    if not match:
        return None
    return abs(float(match.group(1)))


def extract_confidence_pct(reason):
    """
    Pulls the weather engine's forecast-agreement heuristic out of the
    reason string (e.g. "...confidence 89.1%"). Only weather trades
    currently log this field -- other categories will just return None.
    """
    match = re.search(r"confidence ([\d.]+)%", reason or "")
    if not match:
        return None
    return float(match.group(1))


def bet_implied_win_prob_pct(decision, model_prob_pct):
    """
    model_prob_pct is always P(YES). The actual probability the model is
    claiming for *this specific bet* depends on which side we took --
    for a BUY NO, the model's implied confidence in winning is the
    complement. This is what should actually be checked against reality:
    a trade logged as "90% confidence" ought to win about 90% of the
    time, regardless of which side of the market it was.
    """
    if decision == "BUY YES":
        return model_prob_pct
    if decision == "BUY NO":
        return 100 - model_prob_pct
    return None


def load_trades():
    """
    Reads both the active trade log and paper_trades_old.csv (older
    trades get rotated out of paper_trades.csv over time). Without the
    old log, most settled trades have no matching row here and silently
    drop out of the analysis entirely -- only ~13 of ~30+ settled trades
    would ever get analyzed, which makes any calibration read on this
    data close to meaningless.
    """
    trades = {}
    for path in (OLD_TRADE_LOG, TRADE_LOG):
        if not path.exists():
            continue
        with path.open("r", newline="", encoding="utf-8") as file:
            for row in csv.DictReader(file):
                trades[row["ticker"]] = row  # TRADE_LOG read second, wins on overlap
    return trades


def load_results():
    if not RESULTS_LOG.exists():
        return []
    with RESULTS_LOG.open("r", newline="", encoding="utf-8") as file:
        return list(csv.DictReader(file))


def analyze():
    trades = load_trades()
    results = load_results()

    if not results:
        print("No settled trades yet -- nothing to analyze. Check back after "
              "settle_trades.py has found some resolved markets.")
        return

    records = []
    for result_row in results:
        if result_row.get("result") == "void":
            continue  # refunded wash, not a real win/loss signal -- exclude from calibration

        ticker = result_row["ticker"]
        trade_row = trades.get(ticker)
        if not trade_row:
            continue

        reason = trade_row.get("reason", "")
        model_prob_pct = extract_model_prob_pct(reason)
        if model_prob_pct is None:
            continue

        actual_yes = 1.0 if result_row["result"] == "yes" else 0.0
        model_prob_yes = model_prob_pct / 100
        brier = (model_prob_yes - actual_yes) ** 2

        decision = trade_row.get("decision")

        records.append({
            "ticker": ticker,
            "category": trade_row.get("category"),
            "decision": decision,
            "brier": brier,
            "won": result_row["won"] == "True",
            "profit": float(result_row["profit"]),
            "abs_edge_pct": extract_abs_edge_pct(reason),
            "bet_confidence_pct": bet_implied_win_prob_pct(decision, model_prob_pct),
            "heuristic_confidence_pct": extract_confidence_pct(reason),
        })

    if not records:
        print("No settled trades had a parseable model probability -- nothing to analyze.")
        return

    print(f"Analyzed {len(records)} settled trade(s)\n")

    overall_brier = mean(r["brier"] for r in records)
    print(f"Overall Brier score: {overall_brier:.4f}")
    print("  (0 = perfect, 0.25 = equivalent to always guessing 50%, 1 = perfectly wrong)")

    win_rate = mean(1.0 if r["won"] else 0.0 for r in records)
    print(f"\nOverall win rate: {win_rate*100:.1f}%")

    total_profit = sum(r["profit"] for r in records)
    print(f"Total P&L on settled trades: {total_profit:+.2f}")

    print("\nBy category:")
    categories = sorted(set(r["category"] for r in records if r["category"]))
    for category in categories:
        cat_records = [r for r in records if r["category"] == category]
        cat_brier = mean(r["brier"] for r in cat_records)
        cat_win_rate = mean(1.0 if r["won"] else 0.0 for r in cat_records)
        cat_profit = sum(r["profit"] for r in cat_records)
        print(f"  {category}: n={len(cat_records)}, Brier={cat_brier:.4f}, "
              f"win rate={cat_win_rate*100:.1f}%, P&L={cat_profit:+.2f}")

    edge_records = [r for r in records if r["abs_edge_pct"] is not None]
    if edge_records:
        print("\nWin rate by edge size (does a bigger stated edge actually mean a better bet?):")
        buckets = [(0, 10), (10, 20), (20, 1000)]
        for low, high in buckets:
            bucket = [r for r in edge_records if low <= r["abs_edge_pct"] < high]
            if not bucket:
                continue
            bucket_win_rate = mean(1.0 if r["won"] else 0.0 for r in bucket)
            label = f"{low}-{high}%" if high < 1000 else f"{low}%+"
            print(f"  Edge {label}: n={len(bucket)}, win rate={bucket_win_rate*100:.1f}%")

    # Real calibration check: if the model says a bet has a 90% chance to
    # win, it should win about 90% of the time -- not just "more often
    # than a 50% bet." This uses the bet-level implied probability (the
    # complement for BUY NO), so it applies across every category, not
    # just weather.
    calib_records = [r for r in records if r["bet_confidence_pct"] is not None]
    if calib_records:
        print("\nCalibration -- stated win probability vs. actual win rate:")
        print("  (a well-calibrated model has these two columns roughly match)")
        buckets = [(50, 60), (60, 70), (70, 80), (80, 90), (90, 101)]
        for low, high in buckets:
            bucket = [r for r in calib_records if low <= r["bet_confidence_pct"] < high]
            if not bucket:
                continue
            bucket_win_rate = mean(1.0 if r["won"] else 0.0 for r in bucket)
            avg_stated = mean(r["bet_confidence_pct"] for r in bucket)
            gap = bucket_win_rate * 100 - avg_stated
            label = f"{low}-{min(high, 100)}%"
            print(f"  Stated {label}: n={len(bucket)}, avg stated={avg_stated:.1f}%, "
                  f"actual win rate={bucket_win_rate*100:.1f}%  (gap {gap:+.1f} pts)")

    # Separately, the weather engine's own "confidence" heuristic (based on
    # forecast spread tightness, not the model probability itself) --
    # worth checking on its own since it's a distinct, unvalidated proxy.
    heuristic_records = [r for r in records if r["heuristic_confidence_pct"] is not None]
    if heuristic_records:
        print("\nWin rate by weather engine's spread-based confidence heuristic:")
        buckets = [(0, 60), (60, 75), (75, 90), (90, 101)]
        for low, high in buckets:
            bucket = [r for r in heuristic_records if low <= r["heuristic_confidence_pct"] < high]
            if not bucket:
                continue
            bucket_win_rate = mean(1.0 if r["won"] else 0.0 for r in bucket)
            label = f"{low}-{min(high, 100)}%"
            print(f"  Heuristic {label}: n={len(bucket)}, win rate={bucket_win_rate*100:.1f}%")

    print("\nReminder: with this few trades, none of these numbers are statistically "
          "reliable yet -- treat them as an early read, not a verdict. Dozens of "
          "settled trades per category is a more reasonable bar before trusting this.")


if __name__ == "__main__":
    analyze()