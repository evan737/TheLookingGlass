from statistics import mean, pstdev

from fred_client import get_series_observations

ICSA_SERIES_ID = "ICSA"  # Initial Claims, Seasonally Adjusted, weekly


def get_claims_forecast(api_key, lookback_weeks=12):
    """
    Builds a simple trend-based forecast for next week's initial jobless
    claims using recent history from FRED.

    IMPORTANT HONESTY NOTE: this is intentionally simple, and cruder than
    the weather engine's approach. The weather forecast averages several
    genuinely independent models and uses their *disagreement* as a real
    uncertainty signal. Here, there's only one data source (the actual
    historical claims series), so instead we project forward using the
    average recent week-over-week change, and use the volatility of those
    changes as a stand-in for uncertainty. This is a real statistical
    estimate, but it's not validated against how well it actually predicts
    -- unlike weather models, which meteorologists have spent decades
    calibrating. Treat this as a first-pass hypothesis, not a proven edge.
    """
    observations = get_series_observations(ICSA_SERIES_ID, api_key, limit=lookback_weeks + 1)
    values = []
    for obs in observations:
        value = obs.get("value")
        if value not in (None, "."):
            try:
                values.append(float(value))
            except ValueError:
                continue

    if len(values) < 2:
        return None

    changes = [values[i] - values[i - 1] for i in range(1, len(values))]
    avg_change = mean(changes)
    change_std = pstdev(changes) if len(changes) > 1 else abs(values[-1] * 0.05)

    last_value = values[-1]
    forecast_mean = last_value + avg_change
    # Floor the uncertainty so a freak quiet stretch doesn't make the model
    # falsely overconfident.
    forecast_std = max(change_std, 1000)

    return {
        "last_observed_value": last_value,
        "last_observed_date": observations[-1]["date"],
        "forecast_mean": forecast_mean,
        "forecast_std": forecast_std,
    }