import csv
from pathlib import Path
from datetime import datetime, timezone

from kalshi import get_market
from fees import estimate_trade_fee

TRADE_LOG = Path("paper_trades.csv")
RESULTS_LOG = Path("paper_trade_results.csv")

STARTING_BANKROLL = 1000.0

# Statuses that mean Kalshi is done trading this market. If we land here
# without a "yes"/"no" result, the market was voided/canceled (walkover,
# retirement before the match started, event postponed indefinitely, etc.)
# rather than genuinely decided -- most common on lower-tier tennis
# (Qualifying/Challenger) matches. Without this, those trades would sit in
# paper_trades.csv forever: never a win, never a loss, never reflected in
# the bankroll, and never removed from open risk exposure.
FINISHED_STATUSES = {"closed", "settled", "finalized"}


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

    P&L now subtracts real Kalshi trading fees (see fees.py) -- taker fee,
    since we always simulate buying at the current ask, not a resting
    limit order. Without this, backtested returns would overstate real
    profitability -- fees are a real cost, not a rounding footnote.
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
        status = (market.get("status") or "").lower()

        if result not in ("yes", "no"):
            if status in FINISHED_STATUSES:
                # Market stopped trading but never posted a yes/no result --
                # treat as void: refund the stake, no win/loss, no fee.
                new_results.append({
                    "ticker": ticker,
                    "decision": trade["decision"],
                    "entry_price": "",
                    "result": "void",
                    "won": "",
                    "profit": 0.0,
                    "fee": 0.0,
                    "settled_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                })
                print(f"{ticker}: closed with no result (status={status or 'unknown'}) -- "
                      f"treating as VOID, stake refunded")
            continue  # still open, not settled yet -- try again later

        decision = trade["decision"]

        def parse_price(value):
            try:
                return float(value)
            except (TypeError, ValueError):
                return None

        yes_ask = parse_price(trade.get("yes_ask"))
        yes_bid = parse_price(trade.get("yes_bid"))

        try:
            stake = float(trade.get("stake", 10.0))
        except (TypeError, ValueError):
            stake = 10.0

        if decision == "BUY YES":
            entry_price = yes_ask
            won = (result == "yes")
        elif decision == "BUY NO":
            # Kalshi doesn't give us the NO-side ask directly in our log --
            # approximate it from the YES bid (no_ask =~ 1 - yes_bid).
            # This is an approximation, not the exact fill price.
            if yes_bid is not None:
                entry_price = 1 - yes_bid
            elif yes_ask is not None:
                # No resting YES bid was ever recorded (illiquid market at
                # trade time, e.g. a thin qualifying-round tennis match) --
                # fall back to approximating from the YES ask instead.
                # Less precise (ignores the bid/ask spread), but keeps the
                # trade from sitting open forever with no result just
                # because one field was missing.
                entry_price = 1 - yes_ask
            else:
                entry_price = None
            won = (result == "no")
        else:
            continue

        if not entry_price or entry_price <= 0:
            print(f"{ticker}: settled ({result}) but no usable price data to compute P&L "
                  f"(yes_bid={trade.get('yes_bid')!r}, yes_ask={trade.get('yes_ask')!r}) -- skipping, needs manual review")
            continue

        contracts = stake / entry_price
        payout = contracts * 1.0 if won else 0.0
        fee = estimate_trade_fee(stake, entry_price, order_type="taker")
        profit = round(payout - stake - fee, 2)

        new_results.append({
            "ticker": ticker,
            "decision": decision,
            "entry_price": round(entry_price, 4),
            "result": result,
            "won": won,
            "profit": profit,
            "fee": round(fee, 2),
            "settled_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        })

        outcome = "WIN" if won else "LOSS"
        print(f"{ticker}: {decision} @ {entry_price:.2f} -> settled {result.upper()} -> "
              f"{outcome} ({profit:+.2f}, fee ${fee:.2f})")

    if not new_results:
        print("No newly settled trades this run.")
        return

    file_exists = RESULTS_LOG.exists()
    with RESULTS_LOG.open("a", newline="", encoding="utf-8") as file:
        fieldnames = ["ticker", "decision", "entry_price", "result", "won", "profit", "fee", "settled_at"]
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
    total_fees = sum(float(row.get("fee", 0)) for row in results)
    wins = sum(1 for row in results if row["won"] == "True")
    losses = sum(1 for row in results if row["won"] == "False")
    voids = sum(1 for row in results if row.get("result") == "void")

    print(f"\nSettled trades: {len(results)}  (Wins: {wins}, Losses: {losses}, Voids: {voids})")
    print(f"Total P&L (after fees): {total_profit:+.2f}")
    print(f"Total fees paid: ${total_fees:.2f}")
    print(f"Bankroll: ${STARTING_BANKROLL + total_profit:.2f} (started at ${STARTING_BANKROLL:.2f})")


if __name__ == "__main__":
    settle_trades()
    print_summary()