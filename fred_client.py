import requests

BASE_URL = "https://api.stlouisfed.org/fred/series/observations"


def get_series_observations(series_id, api_key, limit=26):
    """
    Returns a list of {"date": "YYYY-MM-DD", "value": "123.4"} observations
    for a FRED series, oldest first.
    """
    params = {
        "series_id": series_id,
        "api_key": api_key,
        "file_type": "json",
        "sort_order": "desc",
        "limit": limit,
    }
    response = requests.get(BASE_URL, params=params, timeout=20)
    response.raise_for_status()
    data = response.json()
    observations = data.get("observations", [])
    observations.reverse()  # FRED gives newest-first; we want chronological
    return observations