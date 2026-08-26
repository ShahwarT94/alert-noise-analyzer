#!/usr/bin/env python3
"""
Runbook coverage checker for Alert Noise Analyzer.
Detects policies that have alerts but no corresponding runbook documentation.
"""

import argparse
import json
from collections import defaultdict
from typing import Any


def load_json(filepath: str) -> list[dict]:
    """Load JSON data from a file."""
    with open(filepath, "r") as f:
        return json.load(f)


def detect_runbook_gaps(
    alerts: list[dict],
    runbooks: list[dict],
) -> list[dict]:
    """
    Returns findings like:
    {
        "policy": str,
        "alert_count": int,  # how many alerts used this policy, for prioritization
    }
    Sorted by alert_count descending (policies causing the most alerts with
    no documented fix should be at the top).
    """
    policy_counts: dict[str, int] = defaultdict(int)

    for alert in alerts:
        policy = alert.get("policy")
        if policy:
            policy_counts[policy] += 1

    runbook_policies = set()
    for runbook in runbooks:
        if not isinstance(runbook, dict):
            continue
        policy = runbook.get("policy")
        if policy:
            runbook_policies.add(policy)

    findings = []
    for policy, count in policy_counts.items():
        if policy not in runbook_policies:
            findings.append({
                "policy": policy,
                "alert_count": count,
            })

    findings.sort(key=lambda f: f["alert_count"], reverse=True)
    return findings


def print_findings(findings: list[dict]) -> None:
    """Print findings in a readable format."""
    if not findings:
        print("No runbook gaps detected.")
        return

    print(f"\n{'Policy':<20} {'Alert Count':>11}")
    print("-" * 35)
    for f in findings:
        policy = f["policy"]
        count = f["alert_count"]
        print(f"{policy:<20} {count:>11}")

    print(f"\nTotal policies missing runbooks: {len(findings)}")


def main():
    parser = argparse.ArgumentParser(description="Detect runbook coverage gaps")
    parser.add_argument("--alerts", type=str, default="data/alerts.json", help="Path to alerts JSON file")
    parser.add_argument("--runbooks", type=str, default="data/runbooks.json", help="Path to runbooks JSON file")
    args = parser.parse_args()

    alerts = load_json(args.alerts)
    runbooks = load_json(args.runbooks)
    findings = detect_runbook_gaps(alerts, runbooks)
    print_findings(findings)


if __name__ == "__main__":
    main()