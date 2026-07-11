import csv
from pathlib import Path

STARTING_BANKROLL = 1000.0
RESULTS_LOG = Path("paper_trade_results.csv")


def get_current_bankroll():
    """
    Starting bankroll plus cumulative profit/loss from all settled trades
    so far. Used to size new positions against the *current* bankroll,
    not a fixed number -- so position sizes naturally shrink after losses
    and grow after wins, same as real Kelly betting would.
    """
    if not RESULTS_LOG.exists():
        return STARTING_BANKROLL

    with RESULTS_LOG.open("r", newline="", encoding="utf-8") as file:
        reader = csv.DictReader(file)
        total_profit = sum(float(row["profit"]) for row in reader)

    return STARTING_BANKROLL + total_profit