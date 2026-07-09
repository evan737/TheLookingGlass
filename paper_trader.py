import csv
from datetime import datetime
from pathlib import Path


TRADE_LOG = Path("paper_trades.csv")


def log_paper_trade(market, category, decision, reason):
    file_exists = TRADE_LOG.exists()

    with TRADE_LOG.open("a", newline="", encoding="utf-8") as file:
        writer = csv.writer(file)

        if not file_exists:
            writer.writerow([
                "timestamp",
                "category",
                "ticker",
                "title",
                "decision",
                "yes_bid",
                "yes_ask",
                "last_price",
                "reason",
            ])

        writer.writerow([
            datetime.now().isoformat(timespec="seconds"),
            category,
            market.get("ticker"),
            market.get("title"),
            decision,
            market.get("yes_bid_dollars"),
            market.get("yes_ask_dollars"),
            market.get("last_price_dollars"),
            reason,
        ])
def has_open_paper_trade(ticker):
    """
    Prevents logging the same market twice. Since each weather bracket
    market is date-specific (a new ticker each day), this naturally means
    'only paper-trade this exact market once' rather than needing a more
    complex open/closed position tracker -- which is a reasonable starting
    point but will need revisiting once these need to be closed out and
    scored against settlement results.
    """
    if not TRADE_LOG.exists():
        return False
    with TRADE_LOG.open("r", newline="", encoding="utf-8") as file:
        reader = csv.DictReader(file)
        return any(row["ticker"] == ticker for row in reader)