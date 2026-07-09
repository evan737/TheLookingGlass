import requests
from statistics import mean, pstdev

# Kalshi's KXHIGHNY series settles on the NWS Central Park station (KNYC),
# NOT wherever weather.py was pointed before. Use the station's coordinates.
STATION_LAT = 40.7829
STATION_LON = -73.9654

# Three independent forecast models. Using the *spread between models* as our
# uncertainty estimate is far more honest than a made-up fixed number -- if
# the models agree, we're confident; if they disagree, we should be too.
MODELS = ["ecmwf_ifs025", "gfs_seamless", "icon_seamless"]


def get_nyc_high_forecast(forecast_days=10):
    """
    Returns a dict keyed by date string ('YYYY-MM-DD') with:
      - forecast_mean: average daily high (F) across models
      - forecast_std: population stddev across models (uncertainty proxy)
      - model_values: the raw per-model forecasts, for transparency
    """
    url = (
        "https://api.open-meteo.com/v1/forecast"
        f"?latitude={STATION_LAT}&longitude={STATION_LON}"
        "&daily=temperature_2m_max"
        f"&models={','.join(MODELS)}"
        "&temperature_unit=fahrenheit"
        "&timezone=America/New_York"
        f"&forecast_days={forecast_days}"
    )
    response = requests.get(url, timeout=20)
    response.raise_for_status()
    data = response.json()
    daily = data.get("daily", {})
    dates = daily.get("time", [])

    forecasts = {}
    for i, date in enumerate(dates):
        values = []
        for model in MODELS:
            key = f"temperature_2m_max_{model}"
            series = daily.get(key)
            if series and i < len(series) and series[i] is not None:
                values.append(series[i])

        if not values:
            continue

        if len(values) > 1:
            std = max(pstdev(values), 0.5)
        else:
            # Only one model responded -- fall back to a conservative
            # placeholder uncertainty rather than pretending we're sure.
            std = 2.0

        forecasts[date] = {
            "forecast_mean": mean(values),
            "forecast_std": std,
            "model_values": values,
        }

    return forecasts


if __name__ == "__main__":
    forecasts = get_nyc_high_forecast()
    for date, forecast in forecasts.items():
        print(
            date,
            "mean:", round(forecast["forecast_mean"], 1),
            "std:", round(forecast["forecast_std"], 2),
            "models:", forecast["model_values"],
        )
