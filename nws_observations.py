import requests
from datetime import datetime, timezone

# api.weather.gov requires a descriptive User-Agent per their usage policy
# (no API key needed -- it's free and public).
HEADERS = {"User-Agent": "TheLookingGlass (personal weather-market project)"}


def fetch_todays_max_temp_f(station_id):
    """
    Returns the highest temperature (Fahrenheit) recorded so far today at
    the given NWS station (e.g. "KNYC"), using api.weather.gov -- the same
    authoritative source Kalshi's settlement is actually based on.

    Returns None if no observations are available yet (e.g. very early in
    the day) or the request fails.

    NOTE: this does not replicate the exact hourly-vs-5-minute-station
    rounding quirks described in NWS station documentation -- it just
    takes the max of whatever api.weather.gov reports for today. Good
    enough as a same-day floor on the forecast distribution, but not a
    perfect reproduction of Kalshi's exact settlement value.
    """
    today_utc = datetime.now(timezone.utc).strftime("%Y-%m-%dT00:00:00Z")
    url = f"https://api.weather.gov/stations/{station_id}/observations"

    try:
        response = requests.get(
            url, params={"start": today_utc}, headers=HEADERS, timeout=20
        )
        response.raise_for_status()
        data = response.json()
    except Exception:
        return None

    max_temp_c = None
    for feature in data.get("features", []):
        temp = feature.get("properties", {}).get("temperature", {}).get("value")
        if temp is not None and (max_temp_c is None or temp > max_temp_c):
            max_temp_c = temp

    if max_temp_c is None:
        return None

    return max_temp_c * 9 / 5 + 32