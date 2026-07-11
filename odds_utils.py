def decimal_to_probability(decimal_odds):
    """
    Converts decimal odds (e.g. 2.00, 1.85) to implied probability.
    This is what odds-api.io actually returns -- still includes the vig
    until de-vigged with devig_two_way below.
    """
    if decimal_odds is None:
        return None
    try:
        decimal_odds = float(decimal_odds)
    except (TypeError, ValueError):
        return None
    if decimal_odds <= 0:
        return None
    return 1.0 / decimal_odds


def american_to_probability(odds):
    """
    Converts American odds (e.g. -150, +130) to implied probability.

    This is the *implied* probability from a single sportsbook line -- it
    still includes the vig (the book's built-in edge), so don't treat it
    as a calibrated "true" probability until it's been de-vigged.
    """
    if odds is None:
        return None
    odds = float(odds)
    if odds < 0:
        return -odds / (-odds + 100)
    return 100 / (odds + 100)


def devig_two_way(prob_a, prob_b):
    """
    Removes the vig from a two-outcome market by normalizing the two
    implied probabilities so they sum to 1.0.

    A real two-outcome market's true probabilities always sum to 1;
    sportsbooks price both sides so they sum to *more* than 1 (e.g. 1.05)
    -- that extra 5% is the vig. Dividing each side by the total removes it.
    """
    if prob_a is None or prob_b is None:
        return None, None
    total = prob_a + prob_b
    if total <= 0:
        return None, None
    return prob_a / total, prob_b / total