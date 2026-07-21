"""
A lightweight risk management layer. Not professional-grade risk
infrastructure, but the same underlying discipline real trading desks
use: no single model, no single day, and no single category should be
able to do disproportionate damage, no matter how confident the model
currently seems.
"""
import csv
from pathlib import Path
from datetime import datetime, timezone

from bankroll import get_current_bankroll, STARTING_BANKROLL
from correlation_groups import get_correlation_group

TRADE_LOG = Path("paper_trades.csv")
RESULTS_LOG = Path("paper_trade_results.csv")
KILL_SWITCH_FILE = Path("STOP_TRADING")

# ---- Hard limits -- edit these to taste as you get more comfortable ----
MAX_DRAWDOWN_PCT = 20.0                 # halt new trades if bankroll falls this % below start
MAX_DAILY_TRADES = 10                   # cap on new positions opened per day, across everything
MAX_CATEGORY_EXPOSURE_PCT = 40.0        # no single category > this % of currently-open stake
MAX_CORRELATED_GROUP_EXPOSURE_PCT = 40.0  # no single correlated group > this % of open stake

# Same-event stacking (two different bracket thresholds on the exact same
# underlying number -- e.g. two Chicago temperature brackets for the same
# day, or two jobless-claims thresholds for the same week's release) is
# enforced as a hard one-position-per-event rule in check_can_trade
# below, not a percentage cap. A % cap gets diluted away by whatever else
# happens to be open (verified: even 20% wouldn't have caught the actual
# Chicago incident on 2026-07-19, which came out to 17.7% once other open
# positions were factored in) -- "same underlying number" isn't a sizing
# question, so there's no threshold constant here.


def kill_switch_engaged():
    """
    Instant manual override: create an empty file named STOP_TRADING in
    the project folder and every scan script will refuse to open new
    trades until you delete it. No code changes needed to pull this lever.
    """
    return KILL_SWITCH_FILE.exists()


def drawdown_pct():
    bankroll = get_current_bankroll()
    return max(0.0, (STARTING_BANKROLL - bankroll) / STARTING_BANKROLL * 100)


def trades_opened_today():
    if not TRADE_LOG.exists():
        return 0
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    count = 0
    with TRADE_LOG.open("r", newline="", encoding="utf-8") as file:
        for row in csv.DictReader(file):
            if row["timestamp"].startswith(today):
                count += 1
    return count


def extract_series_ticker(ticker):
    """
    'KXHIGHNY-26JUL10-B85' -> 'KXHIGHNY'. Works for any of this project's
    tickers since series tickers themselves never contain a dash.
    """
    if not ticker:
        return None
    return ticker.split("-")[0]


def extract_event_id(ticker):
    """
    'KXHIGHCHI-26JUL19-B78.5' -> 'KXHIGHCHI-26JUL19'
    'KXJOBLESSCLAIMS-26JUL16-205000' -> 'KXJOBLESSCLAIMS-26JUL16'

    The first two dash-separated segments identify the specific
    underlying event/release a market resolves against -- everything
    after that (the third segment) is just which threshold/bracket of
    that one number this particular market is betting on. Two markets
    with the same event_id aren't just "likely correlated" the way
    different cities are; they're bets on the exact same outcome, so
    they should never be treated as diversification.
    """
    if not ticker:
        return None
    parts = ticker.split("-")
    if len(parts) < 2:
        return ticker
    return "-".join(parts[:2])


def _safe_float(value, default=10.0):
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _get_open_rows():
    """Returns all logged trade rows whose ticker hasn't settled yet."""
    if not TRADE_LOG.exists():
        return []

    settled_tickers = set()
    if RESULTS_LOG.exists():
        with RESULTS_LOG.open("r", newline="", encoding="utf-8") as file:
            settled_tickers = {row["ticker"] for row in csv.DictReader(file)}

    open_rows = []
    with TRADE_LOG.open("r", newline="", encoding="utf-8") as file:
        for row in csv.DictReader(file):
            if row["ticker"] not in settled_tickers:
                open_rows.append(row)
    return open_rows


def category_exposure_pct(category):
    """
    What fraction of currently-OPEN (unsettled) stake sits in one
    category, as a % of all open stake. Prevents accidentally piling
    everything into one market type just because it's on a hot streak.
    """
    open_rows = _get_open_rows()
    total_open_stake = sum(_safe_float(row.get("stake", 10.0)) for row in open_rows)
    if total_open_stake <= 0:
        return 0.0

    category_open_stake = sum(
        _safe_float(row.get("stake", 10.0))
        for row in open_rows
        if row.get("category") == category
    )
    return (category_open_stake / total_open_stake) * 100


def correlated_group_exposure_pct(group_name):
    """
    Like category_exposure_pct, but grouped by correlation group instead
    of category -- catches cases where e.g. NYC and Philadelphia weather
    positions are technically different tickers/markets but likely to
    move together because they're driven by the same weather system.
    """
    open_rows = _get_open_rows()
    total_open_stake = sum(_safe_float(row.get("stake", 10.0)) for row in open_rows)
    if total_open_stake <= 0:
        return 0.0

    group_open_stake = 0.0
    for row in open_rows:
        series = extract_series_ticker(row.get("ticker"))
        if get_correlation_group(series) == group_name:
            group_open_stake += _safe_float(row.get("stake", 10.0))

    return (group_open_stake / total_open_stake) * 100


def same_event_exposure_pct(event_id):
    """
    What fraction of currently-OPEN stake sits on markets sharing the
    same event_id (same underlying number, different threshold/bracket).
    """
    open_rows = _get_open_rows()
    total_open_stake = sum(_safe_float(row.get("stake", 10.0)) for row in open_rows)
    if total_open_stake <= 0:
        return 0.0

    event_open_stake = sum(
        _safe_float(row.get("stake", 10.0))
        for row in open_rows
        if extract_event_id(row.get("ticker")) == event_id
    )
    return (event_open_stake / total_open_stake) * 100


def all_correlated_group_exposures():
    """
    Computes exposure for every correlation group that currently has open
    positions -- so the dashboard/checks don't need to know the group
    list in advance.
    """
    open_rows = _get_open_rows()
    total_open_stake = sum(_safe_float(row.get("stake", 10.0)) for row in open_rows)
    if total_open_stake <= 0:
        return {}

    group_stakes = {}
    for row in open_rows:
        series = extract_series_ticker(row.get("ticker"))
        group = get_correlation_group(series)
        stake = _safe_float(row.get("stake", 10.0))
        group_stakes[group] = group_stakes.get(group, 0.0) + stake

    return {group: (stake / total_open_stake) * 100 for group, stake in group_stakes.items()}


def check_can_trade(category, ticker=None):
    """
    Call this before logging any new paper trade. Returns (allowed, reason).
    If allowed is False, skip the trade and surface the reason to the user
    instead of silently doing nothing.

    Pass `ticker` when available so the correlation-group check can run --
    without it, only the category-level check applies.
    """
    if kill_switch_engaged():
        return False, "Kill switch engaged (STOP_TRADING file present) -- no new trades."

    dd = drawdown_pct()
    if dd >= MAX_DRAWDOWN_PCT:
        return False, f"Max drawdown breached ({dd:.1f}% >= {MAX_DRAWDOWN_PCT}%) -- halting new trades."

    opened_today = trades_opened_today()
    if opened_today >= MAX_DAILY_TRADES:
        return False, f"Daily trade cap reached ({opened_today}/{MAX_DAILY_TRADES}) -- no more trades today."

    exposure = category_exposure_pct(category)
    if exposure >= MAX_CATEGORY_EXPOSURE_PCT:
        return False, f"{category} exposure already at {exposure:.1f}% of open stake (cap {MAX_CATEGORY_EXPOSURE_PCT}%)."

    if ticker:
        # Hard rule, not a percentage cap: a % threshold gets diluted away
        # by whatever else happens to be open at the time (verified this
        # against the actual Chicago incident -- even a 20% cap wouldn't
        # have caught it, since it came out to 17.7% once other unrelated
        # open stake was factored in). "Same underlying number" isn't a
        # sizing question, it's a yes/no one -- either you already have a
        # position on this event or you don't.
        event_id = extract_event_id(ticker)
        open_rows = _get_open_rows()
        if any(extract_event_id(row.get("ticker")) == event_id for row in open_rows):
            return False, (
                f"Already have an open position on event '{event_id}' -- "
                f"skipping to avoid stacking multiple bets on the same underlying number."
            )

        series = extract_series_ticker(ticker)
        group = get_correlation_group(series)
        group_exposure = correlated_group_exposure_pct(group)
        if group_exposure >= MAX_CORRELATED_GROUP_EXPOSURE_PCT:
            return False, (
                f"Correlated group '{group}' exposure already at "
                f"{group_exposure:.1f}% (cap {MAX_CORRELATED_GROUP_EXPOSURE_PCT}%) "
                f"-- these positions likely move together."
            )

    return True, "OK"