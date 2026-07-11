import sys
import json
import requests

if len(sys.argv) < 2:
    print("Usage: python test_bookmakers.py YOUR_API_KEY")
    sys.exit(1)

api_key = sys.argv[1]

response = requests.get(
    "https://api.odds-api.io/v3/bookmakers",
    params={"apiKey": api_key},
    timeout=20,
)
print("Status:", response.status_code)
print(json.dumps(response.json(), indent=2)[:3000])