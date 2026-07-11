# Station coordinates for Kalshi's KXHIGH (daily high temperature) markets.
#
# Kalshi settles these against NWS Climatological Reports for one specific
# station per city. station_id values below are the actual NWS station
# identifiers (confirmed against a detailed community writeup on how these
# markets settle) -- used to pull same-day observed temperatures directly
# from api.weather.gov, the same source Kalshi settlement is based on.
#
# Confidence levels:
#   - KXHIGHNY, KXHIGHCHI, KXHIGHMIA, KXHIGHDEN, KXHIGHAUS, KXHIGHHOU,
#     KXHIGHPHIL: station IDs confirmed (KNYC, KMDW, KMIA, KDEN, KAUS,
#     KHOU, KPHL respectively)
#   - KXHIGHLAX, KXHIGHDFW: series tickers inferred earlier, station IDs
#     here are a best guess (main airport station) -- not yet confirmed
#
# This also isn't exhaustive -- Kalshi runs KXHIGH markets for roughly 20
# cities total. Add more here as you confirm their tickers/stations.
WEATHER_STATIONS = {
    "KXHIGHNY": {"name": "New York City", "lat": 40.7829, "lon": -73.9654, "station_id": "KNYC"},
    "KXHIGHCHI": {"name": "Chicago (Midway)", "lat": 41.7868, "lon": -87.7522, "station_id": "KMDW"},
    "KXHIGHMIA": {"name": "Miami", "lat": 25.7959, "lon": -80.2870, "station_id": "KMIA"},
    "KXHIGHAUS": {"name": "Austin", "lat": 30.1975, "lon": -97.6664, "station_id": "KAUS"},
    "KXHIGHDEN": {"name": "Denver", "lat": 39.8561, "lon": -104.6737, "station_id": "KDEN"},
    "KXHIGHLAX": {"name": "Los Angeles", "lat": 33.9416, "lon": -118.4085, "station_id": "KLAX"},
    "KXHIGHDFW": {"name": "Dallas-Fort Worth", "lat": 32.8998, "lon": -97.0403, "station_id": "KDFW"},
    "KXHIGHHOU": {"name": "Houston (Hobby)", "lat": 29.6454, "lon": -95.2789, "station_id": "KHOU"},
    "KXHIGHPHIL": {"name": "Philadelphia", "lat": 39.8729, "lon": -75.2437, "station_id": "KPHL"},
}