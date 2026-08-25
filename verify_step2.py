import json

with open("data/alerts.json") as f:
    alerts = json.load(f)

print(f"Total alerts: {len(alerts)}")

# Count how many raw records match the top flagged pair from the CLI output
target_condition = "Azure Gateway Latency"
target_account = "ACC-004"

matches = [
    a for a in alerts
    if a.get("condition") == target_condition and a.get("account_id") == target_account
]

print(f"Raw records matching '{target_condition}' / '{target_account}': {len(matches)}")

# Check for duplicate violation_ids among those matches
ids = [a.get("violation_id") for a in matches]
duplicates = [i for i in set(ids) if ids.count(i) > 1]
print(f"Duplicate violation_ids in this group: {duplicates if duplicates else 'none'}")
