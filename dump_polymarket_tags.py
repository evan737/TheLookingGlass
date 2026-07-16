import requests

response = requests.get("https://gamma-api.polymarket.com/tags", timeout=20)
response.raise_for_status()
tags = response.json()

print(f"Total tags returned: {len(tags)}\n")

for tag in tags:
    label = tag.get("label") or tag.get("name") or ""
    if any(k in label.lower() for k in ["tennis", "sport"]):
        print(f"MATCH: {tag}")

print("\nFull list of all labels:")
for tag in tags:
    print(f"  {tag.get('id')}: {tag.get('label') or tag.get('name')}")