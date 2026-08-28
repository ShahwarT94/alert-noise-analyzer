#!/usr/bin/env python3
"""
Recurring pattern detector for Alert Noise Analyzer.
Detects (condition, account_id) pairs that fire frequently within a rolling time window.
"""
import os
import argparse
import json
from collections import defaultdict
from datetime import datetime, timedelta


def load_alerts(filepath: str) -> list[dict]:
    """Load alerts from a JSON file."""
    with open(filepath) as f:
        data: list[dict] = json.load(f)
    return data


def detect_recurring_patterns(
    alerts: list[dict],
    window_days: int = 7,
    min_occurrences: int = 5,
) -> list[dict]:
    """
    Returns a list of findings, one per (condition, account_id) pair that
    meets the threshold, each shaped like:
    {
        "condition": str,
        "account_id": str,
        "occurrence_count": int,
        "first_seen": ISO8601 string,
        "last_seen": ISO8601 string,
        "violation_ids": list[str],
    }
    Sorted by occurrence_count descending.
    """
    window_delta = timedelta(days=window_days)

    grouped: dict[tuple[str, str], list[dict]] = defaultdict(list)

    for alert in alerts:
        condition = alert.get("condition")
        account_id = alert.get("account_id")
        opened_at_str = alert.get("opened_at_utc")
        violation_id = alert.get("violation_id")

        if not condition or not account_id or not opened_at_str:
            continue

        try:
            opened_at = datetime.fromisoformat(opened_at_str.replace("Z", "+00:00"))
        except (ValueError, AttributeError):
            continue

        grouped[(condition, account_id)].append(
            {
                "violation_id": violation_id,
                "opened_at": opened_at,
                "opened_at_str": opened_at_str,
            }
        )

    findings = []

    for (condition, account_id), records in grouped.items():
        unique_by_violation: dict[str, dict] = {}
        for record in records:
            vid = record["violation_id"]
            if vid and vid not in unique_by_violation:
                unique_by_violation[vid] = record

        unique_records = list(unique_by_violation.values())
        unique_records.sort(key=lambda r: r["opened_at"])

        for record in unique_records:
            window_start = record["opened_at"]
            window_end = window_start + window_delta

            window_violations = []
            for r in unique_records:
                if window_start <= r["opened_at"] <= window_end:
                    window_violations.append(r)

            if len(window_violations) >= min_occurrences:
                violation_ids = [
                    r["violation_id"] for r in window_violations if r["violation_id"]
                ]
                first_seen = min(r["opened_at_str"] for r in window_violations)
                last_seen = max(r["opened_at_str"] for r in window_violations)

                findings.append(
                    {
                        "condition": condition,
                        "account_id": account_id,
                        "occurrence_count": len(window_violations),
                        "first_seen": first_seen,
                        "last_seen": last_seen,
                        "violation_ids": violation_ids,
                    }
                )
                break

    findings.sort(key=lambda f: f["occurrence_count"], reverse=True)
    return findings


def print_findings(findings: list[dict]) -> None:
    """Print findings in a readable format."""
    if not findings:
        print("No recurring patterns found.")
        return

    print(
        f"\n{'Condition':<40} {'Account':<10} {'Count':>6} {'First Seen':<20} {'Last Seen':<20}"
    )
    print("-" * 100)
    for f in findings:
        condition = f["condition"][:39]
        account = f["account_id"]
        count = f["occurrence_count"]
        first = f["first_seen"][:19]
        last = f["last_seen"][:19]
        print(f"{condition:<40} {account:<10} {count:>6} {first:<20} {last:<20}")

    print(f"\nTotal findings: {len(findings)}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Detect recurring alert patterns")
    parser.add_argument(
        "--input", type=str, default="data/alerts.json", help="Path to alerts JSON file"
    )
    parser.add_argument(
        "--window-days", type=int, default=7, help="Rolling window in days"
    )
    parser.add_argument(
        "--min-occurrences", type=int, default=5, help="Minimum occurrences to flag"
    )
    args = parser.parse_args()

    alerts = load_alerts(args.input)
    findings = detect_recurring_patterns(alerts, args.window_days, args.min_occurrences)
    print_findings(findings)


if __name__ == "__main__":
    main()
