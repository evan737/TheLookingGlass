from kalshi import get_registered_markets
from market_registry import MARKET_SERIES
from stations import WEATHER_STATIONS
from weather_forecast import get_high_forecast
from nws_observations import fetch_todays_max_temp_f

la_station = WEATHER_STATIONS.get("KXHIGHLAX")
print(f"LA station config: {la_station}")

print("\nFetching LA forecast directly...")
forecast = get_high_forecast(la_station["lat"], la_station["lon"])
for date, data in list(forecast.items())[:5]:
    print(f"  {date}: mean={data['forecast_mean']:.1f}F, std={data['forecast_std']:.2f}, models={data['model_values']}")

if la_station.get("station_id"):
    print(f"\nFetching same-day observed max for station {la_station['station_id']}...")
    observed = fetch_todays_max_temp_f(la_station["station_id"])
    print(f"  Observed max so far today: {observed}")

print("\n=== Raw Kalshi LA market data ===")
markets = get_registered_markets(MARKET_SERIES)
la_markets = [m for m in markets if m.get("series_ticker") == "KXHIGHLAX"]
for m in la_markets:
    print(f"  {m.get('yes_sub_title')}: floor={m.get('floor_strike')}, cap={m.get('cap_strike')}, "
          f"yes_bid={m.get('yes_bid_dollars')}, yes_ask={m.get('yes_ask_dollars')}, "
          f"volume={m.get('volume_fp')}, event_ticker={m.get('event_ticker')}")