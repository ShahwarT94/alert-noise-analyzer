import json

with open("data/alerts.json") as f:
    alerts = json.load(f)

acc008 = [a for a in alerts if a.get("account_id") == "ACC-008"]
print(f"Total ACC-008 alerts: {len(acc008)}")

# Show all of them sorted by time, so you can eyeball whether they're
# actually tightly clustered or spread out
sortable = [a for a in acc008 if a.get("opened_at_utc")]
sortable.sort(key=lambda a: a["opened_at_utc"])

for a in sortable:
    print(f"{a['opened_at_utc']}  {a.get('condition', 'MISSING')}")
