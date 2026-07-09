import math


def normal_cdf(x, mean, std):
    if std <= 0:
        return 1.0 if x >= mean else 0.0
    z = (x - mean) / (std * math.sqrt(2))
    return 0.5 * (1 + math.erf(z))


def bracket_probability(floor_strike, cap_strike, forecast_mean, forecast_std):
    """
    Estimate P(YES) for a Kalshi temperature bracket, modeling the actual
    high temperature as Normal(forecast_mean, forecast_std).

    This is deliberately simple: real daily-high distributions aren't
    perfectly normal (they can skew, especially near seasonal extremes),
    but it's a reasonable first-pass estimate and easy to improve later
    (e.g. swap in a skew-normal, or calibrate against settlement history).

    floor_strike / cap_strike come straight from Kalshi's market object --
    don't parse them out of the ticker string, per Kalshi's own docs.
    """
    if floor_strike is not None and cap_strike is not None:
        p_below_cap = normal_cdf(cap_strike, forecast_mean, forecast_std)
        p_below_floor = normal_cdf(floor_strike, forecast_mean, forecast_std)
        return max(0.0, min(1.0, p_below_cap - p_below_floor))

    if floor_strike is not None:
        return max(0.0, min(1.0, 1 - normal_cdf(floor_strike, forecast_mean, forecast_std)))

    if cap_strike is not None:
        return max(0.0, min(1.0, normal_cdf(cap_strike, forecast_mean, forecast_std)))

    return None
