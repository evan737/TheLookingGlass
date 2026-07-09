# Station coordinates for Kalshi's KXHIGH (daily high temperature) markets.
#
# Kalshi settles these against NWS Climatological Reports for one specific
# station per city -- note the gotchas: Chicago settles on Midway (not
# O'Hare), Houston settles on Hobby (not Bush Intercontinental), Dallas
# settles on DFW airport.
#
# Confidence levels:
#   - KXHIGHNY, KXHIGHCHI: confirmed against Kalshi's own materials
#   - Everything else below: inferred from a third-party tracker of the
#     same markets, not independently verified against Kalshi. If a ticker
#     is wrong, get_registered_markets() will just quietly return nothing
#     for that city (no error) -- worth spot-checking a couple against
#     https://kalshi.com/markets/kxhigh before relying on them.
#
# This also isn't exhaustive -- Kalshi runs KXHIGH markets for roughly 20
# cities total. Add more here as you confirm their tickers/stations.
WEATHER_STATIONS = {
    "KXHIGHNY": {"name": "New York City", "lat": 40.7829, "lon": -73.9654},
    "KXHIGHCHI": {"name": "Chicago (Midway)", "lat": 41.7868, "lon": -87.7522},
    "KXHIGHMIA": {"name": "Miami", "lat": 25.7959, "lon": -80.2870},
    "KXHIGHAUS": {"name": "Austin", "lat": 30.1975, "lon": -97.6664},
    "KXHIGHDEN": {"name": "Denver", "lat": 39.8561, "lon": -104.6737},
    "KXHIGHLAX": {"name": "Los Angeles", "lat": 33.9416, "lon": -118.4085},
    "KXHIGHDFW": {"name": "Dallas-Fort Worth", "lat": 32.8998, "lon": -97.0403},
    "KXHIGHHOU": {"name": "Houston (Hobby)", "lat": 29.6454, "lon": -95.2789},
    "KXHIGHPHIL": {"name": "Philadelphia", "lat": 39.8729, "lon": -75.2437},
}