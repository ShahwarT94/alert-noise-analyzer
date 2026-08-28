#!/usr/bin/env python3
"""
Threshold sanity checker for Alert Noise Analyzer.
Detects conditions where observed values significantly deviate from configured thresholds.
"""

import argparse
import json
from collections import defaultdict
from statistics import median


def load_alerts(filepath: str) -> list[dict]:
    """Load alerts from a JSON file."""
    with open(filepath) as f:
        data: list[dict] = json.load(f)
    return data


def detect_threshold_issues(
    alerts: list[dict],
    deviation_ratio: float = 0.3,
) -> list[dict]:
    """
    Returns findings like:
    {
        "condition": str,
        "configured_threshold": float,
        "median_observed": float,
        "sample_size": int,
        "deviation_pct": float,  # how far median is from threshold, as a %
        "direction": "over-sensitive" | "under-sensitive",
        # over-sensitive = threshold triggers too easily (median far below threshold... etc, use your judgment and document it)
    }
    Sorted by deviation_pct descending (biggest miscalibration first).
    """
    condition_data: dict[str, list[dict]] = defaultdict(list)

    for alert in alerts:
        condition = alert.get("condition")
        threshold_value = alert.get("threshold_value")
        observed_value = alert.get("observed_value")

        if condition is None or threshold_value is None or observed_value is None:
            continue

        try:
            threshold = float(threshold_value)
            observed = float(observed_value)
        except (ValueError, TypeError):
            continue

        condition_data[condition].append(
            {
                "threshold": threshold,
                "observed": observed,
            }
        )

    findings = []

    for condition, records in condition_data.items():
        if len(records) < 3:
            continue

        thresholds = [r["threshold"] for r in records]
        observed_values = [r["observed"] for r in records]

        threshold_counts: dict[float, int] = {}
        for t in thresholds:
            threshold_counts[t] = threshold_counts.get(t, 0) + 1
        configured_threshold = max(threshold_counts, key=lambda t: threshold_counts[t])
        configured_threshold_count = threshold_counts[configured_threshold]

        if configured_threshold_count < 2:
            continue

        if configured_threshold_count / len(records) < 0.2:
            continue

        median_observed = median(observed_values)

        if configured_threshold == 0:
            continue

        deviation_pct = (
            abs(median_observed - configured_threshold) / configured_threshold
        )

        if deviation_pct < deviation_ratio:
            continue

        if median_observed < configured_threshold:
            direction = "over-sensitive"
        else:
            direction = "under-sensitive"

        findings.append(
            {
                "condition": condition,
                "configured_threshold": configured_threshold,
                "median_observed": round(median_observed, 2),
                "sample_size": len(records),
                "deviation_pct": round(deviation_pct * 100, 2),
                "direction": direction,
            }
        )

    findings.sort(key=lambda f: f["deviation_pct"], reverse=True)
    return findings


def print_findings(findings: list[dict]) -> None:
    """Print findings in a readable format."""
    if not findings:
        print("No threshold issues detected.")
        return

    print(
        f"\n{'Condition':<40} {'Threshold':>10} {'Median':>10} {'Samples':>7} {'Dev%':>7} {'Direction'}"
    )
    print("-" * 95)
    for f in findings:
        condition = f["condition"][:39]
        threshold = f["configured_threshold"]
        median_obs = f["median_observed"]
        samples = f["sample_size"]
        dev_pct = f["deviation_pct"]
        direction = f["direction"]
        print(
            f"{condition:<40} {threshold:>10.2f} {median_obs:>10.2f} {samples:>7} {dev_pct:>7.2f} {direction}"
        )

    print(f"\nTotal findings: {len(findings)}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Detect threshold sanity issues")
    parser.add_argument(
        "--input", type=str, default="data/alerts.json", help="Path to alerts JSON file"
    )
    parser.add_argument(
        "--deviation-ratio",
        type=float,
        default=0.3,
        help="Deviation ratio threshold (0.3 = 30 percent)",
    )
    args = parser.parse_args()

    alerts = load_alerts(args.input)
    findings = detect_threshold_issues(alerts, args.deviation_ratio)
    print_findings(findings)


if __name__ == "__main__":
    main()
