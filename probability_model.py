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


def bracket_probability_with_floor(floor_strike, cap_strike, forecast_mean, forecast_std, observed_max_so_far=None):
    """
    Same as bracket_probability, but incorporates a same-day observed
    running maximum temperature as a hard floor: the day's final high can
    never be lower than what's already been recorded, so we condition the
    forecast distribution on "true high >= observed_max_so_far" (a
    left-truncated normal). This sharpens the estimate as the day goes on.

    If observed_max_so_far is None, behaves identically to
    bracket_probability -- this is meant to be used only once a station
    has same-day observations, not for future-day markets.

    Note: being "in the bracket already" doesn't guarantee a high
    probability -- if forecast_std is wide relative to the bracket width,
    the day's true high can still climb past the bracket before the
    day is over. This is expected, correct behavior, not a bug.
    """
    if observed_max_so_far is None:
        return bracket_probability(floor_strike, cap_strike, forecast_mean, forecast_std)

    # If the observed temperature is running notably BELOW the forecast
    # mean, that's a signal the forecast itself is likely busting (e.g.
    # persistent marine layer keeping LA cooler than 3 models expected) --
    # not just something the floor/truncation math should quietly absorb.
    # Simply truncating a wrong, overconfident distribution at the
    # observed floor barely helps if the mean itself is still far too
    # high (confirmed empirically: even widening std alone left model
    # probability near 87% against a market pricing ~28%). So when this
    # happens, blend the forecast mean toward the observation and widen
    # uncertainty accordingly.
    #
    # HONEST LIMITATION: blend_weight is a fixed heuristic (0.6), not
    # time-of-day aware. Late in the day, the observed max-so-far is
    # usually very close to the final value (little room left to rise);
    # early in the day, there's much more legitimate room for the actual
    # high to still climb toward the forecast. A more correct version
    # would scale blend_weight by how far past typical peak-heating hours
    # the station currently is. This is a reasonable first correction,
    # not a fully solved problem.
    if observed_max_so_far < forecast_mean:
        gap = forecast_mean - observed_max_so_far
        blend_weight = 0.6
        forecast_mean = (1 - blend_weight) * forecast_mean + blend_weight * observed_max_so_far
        forecast_std = forecast_std + 0.3 * gap

    p_below_observed = normal_cdf(observed_max_so_far, forecast_mean, forecast_std)
    denominator = 1 - p_below_observed

    if denominator <= 1e-9:
        if cap_strike is not None and observed_max_so_far > cap_strike:
            return 0.0
        if floor_strike is not None and observed_max_so_far < floor_strike:
            return 0.0
        return 1.0

    effective_floor = max(floor_strike, observed_max_so_far) if floor_strike is not None else observed_max_so_far

    if cap_strike is not None and effective_floor > cap_strike:
        return 0.0

    p_below_cap = normal_cdf(cap_strike, forecast_mean, forecast_std) if cap_strike is not None else 1.0
    p_below_effective_floor = normal_cdf(effective_floor, forecast_mean, forecast_std)

    numerator = p_below_cap - p_below_effective_floor
    return max(0.0, min(1.0, numerator / denominator))