import csv
from pathlib import Path
from datetime import datetime, timezone

from kalshi import get_market

TRADE_LOG = Path("paper_trades.csv")
RESULTS_LOG = Path("paper_trade_results.csv")

STAKE_PER_TRADE = 10.0
STARTING_BANKROLL = 1000.0


def load_existing_results():
    if not RESULTS_LOG.exists():
        return {}
    with RESULTS_LOG.open("r", newline="", encoding="utf-8") as file:
        reader = csv.DictReader(file)
        return {row["ticker"]: row for row in reader}


def settle_trades():
    """
    Checks every logged paper trade against Kalshi's live market status.
    Markets that haven't closed/settled yet are simply skipped -- they'll
    get picked up on a future run once Kalshi determines a result.
    """
    if not TRADE_LOG.exists():
        print("No paper trades logged yet.")
        return

    existing_results = load_existing_results()
    new_results = []

    with TRADE_LOG.open("r", newline="", encoding="utf-8") as file:
        reader = csv.DictReader(file)
        trades = list(reader)

    for trade in trades:
        ticker = trade["ticker"]

        if ticker in existing_results:
            continue  # already settled and recorded in a prior run

        try:
            market = get_market(ticker)
        except Exception as error:
            print(f"Could not fetch {ticker}: {error}")
            continue

        result = market.get("result")  # "yes", "no", or "" if not settled yet
        if result not in ("yes", "no"):
            continue  # still open, not settled yet -- try again later

        decision = trade["decision"]

        def parse_price(value):
            try:
                return float(value)
            except (TypeError, ValueError):
                return None

        yes_ask = parse_price(trade.get("yes_ask"))
        yes_bid = parse_price(trade.get("yes_bid"))

        if decision == "BUY YES":
            entry_price = yes_ask
            won = (result == "yes")
        elif decision == "BUY NO":
            # Kalshi doesn't give us the NO-side ask directly in our log --
            # approximate it from the YES bid (no_ask =~ 1 - yes_bid).
            # This is an approximation, not the exact fill price.
            entry_price = (1 - yes_bid) if yes_bid is not None else None
            won = (result == "no")
        else:
            continue

        if not entry_price or entry_price <= 0:
            continue

        contracts = STAKE_PER_TRADE / entry_price
        payout = contracts * 1.0 if won else 0.0
        profit = round(payout - STAKE_PER_TRADE, 2)

        new_results.append({
            "ticker": ticker,
            "decision": decision,
            "entry_price": round(entry_price, 4),
            "result": result,
            "won": won,
            "profit": profit,
            "settled_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        })

        outcome = "WIN" if won else "LOSS"
        print(f"{ticker}: {decision} @ {entry_price:.2f} -> settled {result.upper()} -> {outcome} ({profit:+.2f})")

    if not new_results:
        print("No newly settled trades this run.")
        return

    file_exists = RESULTS_LOG.exists()
    with RESULTS_LOG.open("a", newline="", encoding="utf-8") as file:
        fieldnames = ["ticker", "decision", "entry_price", "result", "won", "profit", "settled_at"]
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        if not file_exists:
            writer.writeheader()
        writer.writerows(new_results)

    print(f"\nRecorded {len(new_results)} newly settled trade(s).")


def print_summary():
    if not RESULTS_LOG.exists():
        print(f"\nNo settled trades yet -- bankroll unchanged at ${STARTING_BANKROLL:.2f}")
        return

    with RESULTS_LOG.open("r", newline="", encoding="utf-8") as file:
        reader = csv.DictReader(file)
        results = list(reader)

    total_profit = sum(float(row["profit"]) for row in results)
    wins = sum(1 for row in results if row["won"] == "True")
    losses = len(results) - wins

    print(f"\nSettled trades: {len(results)}  (Wins: {wins}, Losses: {losses})")
    print(f"Total P&L: {total_profit:+.2f}")
    print(f"Bankroll: ${STARTING_BANKROLL + total_profit:.2f} (started at ${STARTING_BANKROLL:.2f})")


if __name__ == "__main__":
    settle_trades()
    print_summary()