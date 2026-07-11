"""
Manual correlation groupings for positions that are likely to move
together, even though they're technically different markets/categories.

This is a defensible heuristic based on geography/meteorology, NOT a
statistically fitted correlation matrix -- a real quant desk would
compute actual historical correlation coefficients between cities'
daily highs (or between economic releases, etc.) once enough data
exists. Treat this as a reasonable starting approximation, worth
replacing with real correlation analysis later.
"""

# Weather: cities close enough together that the same weather system
# (heat wave, cold front, storm) often affects them simultaneously.
WEATHER_CORRELATION_GROUPS = {
    "Northeast": {"KXHIGHNY", "KXHIGHPHIL"},
    "Texas": {"KXHIGHAUS", "KXHIGHHOU", "KXHIGHDFW"},
    # Chicago, Miami, Denver, LA are each geographically distant enough
    # from the others that they're left as their own implicit singleton
    # groups below (no explicit entry needed).
}


def get_correlation_group(series_ticker):
    """
    Returns the name of the correlation group a series_ticker belongs to.
    If it's not part of any explicitly defined group, it's treated as its
    own independent singleton group (its own series_ticker as the group
    name) -- which also correctly handles cases like jobless claims,
    where every bracket in KXJOBLESSCLAIMS is inherently correlated with
    every other bracket in the same series (they all resolve off the
    same underlying weekly number), without needing a special case.
    """
    if not series_ticker:
        return "Unknown"
    for group_name, tickers in WEATHER_CORRELATION_GROUPS.items():
        if series_ticker in tickers:
            return group_name
    return series_ticker