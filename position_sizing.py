CALIBRATION_SHRINK = 0.5  # 0 = trust the model's stated probability fully, 1 = always treat it as 50/50


def calibrate_win_prob(win_prob):
    """
    Shrinks a model-stated win probability toward 50% before it's used for
    Kelly sizing, to compensate for demonstrated overconfidence.

    WHY: analyze_performance.py's calibration check (30 settled trades, as
    of 2026-07-16) found that trades logged at 90-100% stated confidence
    (n=14 -- nearly half of everything settled so far) actually won only
    71.4% of the time, and 80-90% stated trades won 66.7% of the time.
    Since Kelly sizing bets bigger the more confident the model claims to
    be, that overconfidence was very likely inflating stake sizes exactly
    where the model was most wrong -- e.g. the Philly weather trade: 90%
    stated confidence, logged as a +76% edge, lost.

    HONEST LIMITATION: 0.5 (shrink the distance from 50% by half) is a
    deliberately round, conservative starting point chosen to roughly
    match the two largest calibration buckets (which independently
    implied shrink factors near 0.44-0.45) -- it is NOT a precisely
    fitted correction. 30 trades, many clustered on a handful of
    days/cities, isn't enough to reliably estimate an exact factor, and
    one bucket (60-70% stated) was already well-calibrated on its own,
    which argues against any single fixed factor being right everywhere.
    Revisit this once there's a larger, more independent sample --
    ideally replacing the hardcoded constant with a rolling calibration
    fit against real settlement history.
    """
    return 0.5 + (win_prob - 0.5) * (1 - CALIBRATION_SHRINK)


def kelly_fraction(win_prob, price):
    """
    Computes the full Kelly-optimal fraction of bankroll to stake on a
    binary contract bought at `price` (dollars, 0-1) given a model win
    probability of `win_prob`.

    Math: buying $1 worth of a contract priced at P gets you 1/P contracts,
    each paying $1 if it resolves YES. So a $1 stake nets (1-P)/P profit on
    a win, and loses the full $1 on a loss. Standard Kelly for a bet with
    net-odds b (profit per dollar staked if you win) and win probability p:

        f* = p - (1-p)/b

    Returns 0 for a zero-or-negative edge rather than a negative fraction
    (the calling code already decides which side to bet; a negative Kelly
    fraction here just means "don't take this side").
    """
    if price <= 0 or price >= 1:
        return 0.0

    b = (1 - price) / price
    q = 1 - win_prob
    f_star = win_prob - (q / b)

    return max(0.0, f_star)


def position_size(bankroll, win_prob, price, kelly_multiplier=0.25, max_fraction=0.05):
    """
    Returns the dollar amount to stake on one trade.

    kelly_multiplier: what fraction of "full Kelly" to actually bet.
    Full Kelly is only correct if win_prob is exactly right -- any
    estimation error gets amplified and can cause large drawdowns. None
    of this project's models are calibrated against real settlement
    history yet, so betting a conservative fraction of Kelly (a common
    practice called "fractional Kelly") compensates for that uncertainty.
    0.25 (quarter-Kelly) is a reasonably conservative starting point.

    max_fraction: a hard cap on bankroll fraction per trade, regardless
    of what Kelly suggests -- a safety backstop against a bug or a
    wildly overconfident probability estimate slipping through.
    """
    f_star = kelly_fraction(win_prob, price)
    fraction = min(f_star * kelly_multiplier, max_fraction)
    return round(bankroll * fraction, 2)