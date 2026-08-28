#!/usr/bin/env python3
"""
Correlation detector for Alert Noise Analyzer.
Detects clusters of alerts on different conditions/entities but same account_id
opening within a short time window (cascading incidents).
"""

import argparse
import json
from datetime import datetime, timedelta


def load_alerts(filepath: str) -> list[dict]:
    """Load alerts from a JSON file."""
    with open(filepath) as f:
        data: list[dict] = json.load(f)
    return data


def detect_correlated_clusters(
    alerts: list[dict],
    cluster_window_minutes: int = 5,
    min_cluster_size: int = 2,
) -> list[dict]:
    """
    Returns a list of cluster findings, each shaped like:
    {
        "account_id": str,
        "cluster_start": ISO8601 string,
        "cluster_end": ISO8601 string,
        "alert_count": int,
        "conditions_involved": list[str],   # unique conditions in the cluster
        "violation_ids": list[str],
    }
    Sorted by alert_count descending, then cluster_start ascending.
    """
    window_delta = timedelta(minutes=cluster_window_minutes)

    by_account: dict[str, list[dict]] = {}
    for alert in alerts:
        account_id = alert.get("account_id")
        opened_at_str = alert.get("opened_at_utc")
        condition = alert.get("condition")
        violation_id = alert.get("violation_id")

        if not account_id or not opened_at_str:
            continue

        try:
            opened_at = datetime.fromisoformat(opened_at_str.replace("Z", "+00:00"))
        except (ValueError, AttributeError):
            continue

        if account_id not in by_account:
            by_account[account_id] = []
        by_account[account_id].append(
            {
                "condition": condition,
                "violation_id": violation_id,
                "opened_at": opened_at,
                "opened_at_str": opened_at_str,
            }
        )

    findings: list[dict] = []

    for account_id, records in by_account.items():
        records.sort(key=lambda r: r["opened_at"])

        current_cluster: list[dict] = []

        for record in records:
            if not current_cluster:
                current_cluster.append(record)
                continue

            last_alert_time = current_cluster[-1]["opened_at"]
            if record["opened_at"] <= last_alert_time + window_delta:
                current_cluster.append(record)
            else:
                if len(current_cluster) >= min_cluster_size:
                    _add_finding(findings, account_id, current_cluster)
                current_cluster = [record]

        if len(current_cluster) >= min_cluster_size:
            _add_finding(findings, account_id, current_cluster)

    findings.sort(key=lambda f: (-f["alert_count"], f["cluster_start"]))
    return findings


def _add_finding(findings: list[dict], account_id: str, cluster: list[dict]) -> None:
    """Add a cluster finding to the findings list."""
    unique_conditions = []
    seen_conditions = set()
    unique_violations = []
    seen_violations = set()

    for record in cluster:
        condition = record["condition"]
        if condition and condition not in seen_conditions:
            unique_conditions.append(condition)
            seen_conditions.add(condition)

        vid = record["violation_id"]
        if vid and vid not in seen_violations:
            unique_violations.append(vid)
            seen_violations.add(vid)

    findings.append(
        {
            "account_id": account_id,
            "cluster_start": cluster[0]["opened_at_str"],
            "cluster_end": cluster[-1]["opened_at_str"],
            "alert_count": len(cluster),
            "conditions_involved": unique_conditions,
            "violation_ids": unique_violations,
        }
    )


def print_findings(findings: list[dict]) -> None:
    """Print findings in a readable format."""
    if not findings:
        print("No correlated clusters found.")
        return

    print(f"\n{'Account':<10} {'Start':<20} {'End':<20} {'Count':>5} {'Conditions'}")
    print("-" * 100)
    for f in findings:
        account = f["account_id"]
        start = f["cluster_start"][:19]
        end = f["cluster_end"][:19]
        count = f["alert_count"]
        conditions = ", ".join(f["conditions_involved"][:3])
        if len(f["conditions_involved"]) > 3:
            conditions += f" (+{len(f['conditions_involved']) - 3} more)"
        print(f"{account:<10} {start:<20} {end:<20} {count:>5} {conditions}")

    print(f"\nTotal clusters: {len(findings)}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Detect correlated alert clusters")
    parser.add_argument(
        "--input", type=str, default="data/alerts.json", help="Path to alerts JSON file"
    )
    parser.add_argument(
        "--window-minutes", type=int, default=5, help="Cluster window in minutes"
    )
    parser.add_argument("--min-size", type=int, default=2, help="Minimum cluster size")
    args = parser.parse_args()

    alerts = load_alerts(args.input)
    findings = detect_correlated_clusters(alerts, args.window_minutes, args.min_size)
    print_findings(findings)


if __name__ == "__main__":
    main()
