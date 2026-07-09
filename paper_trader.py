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
            market.get("yes_bid"),
            market.get("yes_ask"),
            market.get("last_price"),
            reason,
        ])