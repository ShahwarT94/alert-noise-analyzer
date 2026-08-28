import json
import statistics

with open("data/alerts.json") as f:
    alerts = json.load(f)

target = "Azure Gateway Latency"

matches = [
    a
    for a in alerts
    if a.get("condition") == target
    and a.get("threshold_value") is not None
    and a.get("observed_value") is not None
]

print(f"Valid samples for '{target}': {len(matches)}")

thresholds = [a["threshold_value"] for a in matches]
observed = [a["observed_value"] for a in matches]

print(f"Threshold values seen: {sorted(set(thresholds))}")
print(f"Observed values: {sorted(observed)}")
print(f"Median observed: {statistics.median(observed)}")

most_common_threshold = max(set(thresholds), key=thresholds.count)
ratio = statistics.median(observed) / most_common_threshold
print(f"Most common threshold: {most_common_threshold}")
print(f"Ratio (median observed / threshold): {ratio:.2f}")
