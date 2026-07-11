import csv
import re
from pathlib import Path
from statistics import mean

TRADE_LOG = Path("paper_trades.csv")
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


def load_trades():
    if not TRADE_LOG.exists():
        return {}
    with TRADE_LOG.open("r", newline="", encoding="utf-8") as file:
        return {row["ticker"]: row for row in csv.DictReader(file)}


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

        records.append({
            "ticker": ticker,
            "category": trade_row.get("category"),
            "decision": trade_row.get("decision"),
            "brier": brier,
            "won": result_row["won"] == "True",
            "profit": float(result_row["profit"]),
            "abs_edge_pct": extract_abs_edge_pct(reason),
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

    print("\nReminder: with this few trades, none of these numbers are statistically "
          "reliable yet -- treat them as an early read, not a verdict. Dozens of "
          "settled trades per category is a more reasonable bar before trusting this.")


if __name__ == "__main__":
    analyze()