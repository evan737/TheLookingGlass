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