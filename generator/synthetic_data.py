#!/usr/bin/env python3
"""
Synthetic data generator for Alert Noise Analyzer.
Generates alerts.json and runbooks.json with seeded patterns for testing.
"""

import argparse
import json
import random
import uuid
from datetime import datetime, timedelta
from typing import Any


POLICIES = [
    "HAL-NR-P0001", "HAL-NR-P0002", "HAL-NR-P0003", "HAL-NR-P0004",
    "HAL-NR-P0005", "HAL-NR-P0006", "HAL-NR-P0007", "HAL-NR-P0008",
    "HAL-NR-P0009", "HAL-NR-P0010", "HAL-NR-P0011", "HAL-NR-P0012",
    "HAL-NR-P0013", "HAL-NR-P0014", "HAL-NR-P0015",
]

CONDITIONS = [
    ("DWP-MIDDLEWARE Response Time", "APM Service"),
    ("Payment-API Response Time", "APM Service"),
    ("Auth-Service Response Time", "APM Service"),
    ("Order-Service Response Time", "APM Service"),
    ("Inventory-API Response Time", "APM Service"),
    ("Host CPU Utilization", "Host"),
    ("Host Memory Utilization", "Host"),
    ("Host Disk Usage", "Host"),
    ("Host Network I/O", "Host"),
    ("Azure Gateway Latency", "Gateway"),
    ("AWS ALB Latency", "Gateway"),
    ("CloudFront Latency", "Gateway"),
    ("AWX Job Failure Rate", "AWX Job"),
    ("Jenkins Build Failure Rate", "AWX Job"),
    ("GitLab Pipeline Failure Rate", "AWX Job"),
    ("Database Connection Pool Exhaustion", "APM Service"),
    ("Kubernetes Pod Restart Rate", "APM Service"),
    ("Message Queue Depth", "APM Service"),
    ("Cache Hit Ratio", "APM Service"),
    ("SSL Certificate Expiry", "Gateway"),
]

ACCOUNT_IDS = [
    "ACC-001", "ACC-002", "ACC-003", "ACC-004", "ACC-005",
    "ACC-006", "ACC-007", "ACC-008", "ACC-009", "ACC-010",
]

ENTITY_TEMPLATES = {
    "APM Service": [
        "dwp-middleware-prod-{:02d}", "payment-api-prod-{:02d}", "auth-service-prod-{:02d}",
        "order-service-prod-{:02d}", "inventory-api-prod-{:02d}", "notification-service-prod-{:02d}",
        "user-profile-prod-{:02d}", "search-service-prod-{:02d}", "analytics-api-prod-{:02d}",
        "billing-service-prod-{:02d}", "shipping-service-prod-{:02d}", "cart-service-prod-{:02d}",
    ],
    "Host": [
        "ip-10-0-{:02d}-{:02d}.ec2.internal", "ip-10-1-{:02d}-{:02d}.ec2.internal",
        "ip-10-2-{:02d}-{:02d}.ec2.internal", "ip-10-3-{:02d}-{:02d}.ec2.internal",
        "vm-prod-{:03d}", "vm-staging-{:03d}", "k8s-worker-{:03d}", "k8s-master-{:03d}",
        "db-primary-{:02d}", "db-replica-{:02d}", "cache-node-{:02d}", "lb-node-{:02d}",
    ],
    "Gateway": [
        "azure-gateway-{:02d}.cloudapp.net", "aws-alb-{:02d}.elb.amazonaws.com",
        "cloudfront-{:02d}.cloudfront.net", "api-gateway-{:02d}.example.com",
        "nginx-ingress-{:02d}", "traefik-{:02d}", "envoy-{:02d}",
    ],
    "AWX Job": [
        "awx-deploy-{:03d}", "jenkins-build-{:03d}", "gitlab-pipeline-{:03d}",
        "ansible-playbook-{:03d}", "terraform-apply-{:03d}", "helm-deploy-{:03d}",
    ],
}

PRIORITIES = ["P1", "P2", "P3"]

DESCRIPTIONS = [
    "Threshold exceeded for sustained period",
    "Sudden spike detected",
    "Gradual degradation over time",
    "Intermittent failures observed",
    "Capacity limit reached",
    "Dependency failure cascade",
    "Configuration drift detected",
    "Resource exhaustion",
    "Network partition suspected",
    "Downstream service unavailable",
]


def generate_entity_name(entity_type: str, rng: random.Random) -> str:
    templates = ENTITY_TEMPLATES[entity_type]
    template = rng.choice(templates)
    count_02d = template.count("{:02d}")
    count_03d = template.count("{:03d}")
    if count_03d > 0:
        return template.format(rng.randint(1, 999))
    elif count_02d == 2:
        return template.format(rng.randint(1, 99), rng.randint(1, 99))
    elif count_02d == 1:
        return template.format(rng.randint(1, 99))
    else:
        return template


def generate_violation_id(rng: random.Random) -> str:
    return f"V-{rng.randint(100000, 999999)}"


def format_iso(dt: datetime) -> str:
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


def generate_alert(
    rng: random.Random,
    window_start: datetime,
    window_end: datetime,
    policy: str = None,
    condition: str = None,
    entity_type: str = None,
    account_id: str = None,
    opened_at: datetime = None,
    priority: str = None,
    threshold_value: float = None,
    observed_value: float = None,
) -> dict:
    if opened_at is None:
        total_seconds = int((window_end - window_start).total_seconds())
        offset = rng.randint(0, total_seconds)
        opened_at = window_start + timedelta(seconds=offset)

    if policy is None:
        policy = rng.choice(POLICIES)
    if condition is None or entity_type is None:
        condition, entity_type = rng.choice(CONDITIONS)
    if account_id is None:
        account_id = rng.choice(ACCOUNT_IDS)
    if priority is None:
        priority = rng.choice(PRIORITIES)

    entity_name = generate_entity_name(entity_type, rng)
    violation_id = generate_violation_id(rng)

    duration_minutes = rng.randint(5, 240)
    closed_at = opened_at + timedelta(minutes=duration_minutes)
    if rng.random() < 0.15:
        closed_at = None

    if threshold_value is None and entity_type in ("APM Service", "Host", "Gateway"):
        threshold_value = round(rng.uniform(10, 100), 2)
    if observed_value is None and threshold_value is not None:
        observed_value = round(threshold_value * rng.uniform(0.8, 2.5), 2)

    description = rng.choice(DESCRIPTIONS)

    return {
        "violation_id": violation_id,
        "policy": policy,
        "condition": condition,
        "priority": priority,
        "entity_name": entity_name,
        "entity_type": entity_type,
        "account_id": account_id,
        "opened_at_utc": format_iso(opened_at),
        "closed_at_utc": format_iso(closed_at) if closed_at else None,
        "threshold_value": threshold_value,
        "observed_value": observed_value,
        "description": description,
    }


def add_messiness(alerts: list, rng: random.Random, messiness_rate: float = 0.09) -> tuple:
    messy_count = 0
    n = len(alerts)
    num_messy = int(n * messiness_rate)

    indices = rng.sample(range(n), min(num_messy, n))

    for idx in indices:
        alert = alerts[idx]
        mess_type = rng.choice(["null_threshold", "null_observed", "bad_timestamp_order", "duplicate"])

        if mess_type == "null_threshold" and alert["threshold_value"] is not None:
            alert["threshold_value"] = None
            messy_count += 1
        elif mess_type == "null_observed" and alert["observed_value"] is not None:
            alert["observed_value"] = None
            messy_count += 1
        elif mess_type == "bad_timestamp_order" and alert["closed_at_utc"]:
            opened = datetime.fromisoformat(alert["opened_at_utc"].replace("Z", "+00:00"))
            closed = datetime.fromisoformat(alert["closed_at_utc"].replace("Z", "+00:00"))
            if closed > opened:
                alert["closed_at_utc"] = format_iso(opened - timedelta(minutes=rng.randint(1, 60)))
                messy_count += 1
        elif mess_type == "duplicate":
            pass

    duplicate_indices = rng.sample(range(n), min(4, n))
    for idx in duplicate_indices:
        original = alerts[idx].copy()
        original["violation_id"] = alerts[idx]["violation_id"]
        original["opened_at_utc"] = format_iso(
            datetime.fromisoformat(original["opened_at_utc"].replace("Z", "+00:00")) + timedelta(minutes=rng.randint(1, 30))
        )
        if original["closed_at_utc"]:
            original["closed_at_utc"] = format_iso(
                datetime.fromisoformat(original["closed_at_utc"].replace("Z", "+00:00")) + timedelta(minutes=rng.randint(1, 30))
            )
        alerts.append(original)
        messy_count += 1

    rng.shuffle(alerts)

    return alerts, messy_count


def generate_recurring_noise(rng: random.Random, window_start: datetime, window_end: datetime) -> list:
    alerts = []
    recurring_pairs = rng.sample(
        [(c, a) for c, _ in CONDITIONS for a in ACCOUNT_IDS],
        rng.randint(6, 8)
    )

    for condition, account_id in recurring_pairs:
        entity_type = next(et for c, et in CONDITIONS if c == condition)
        policy = rng.choice(POLICIES)
        occurrences = rng.randint(6, 10)

        for _ in range(occurrences):
            alert = generate_alert(
                rng, window_start, window_end,
                policy=policy, condition=condition, entity_type=entity_type,
                account_id=account_id
            )
            alerts.append(alert)

    return alerts


def generate_correlated_clusters(rng: random.Random, window_start: datetime, window_end: datetime) -> list:
    alerts = []
    cluster_conditions = [
        [("Host CPU Utilization", "Host"), ("Azure Gateway Latency", "Gateway"), ("AWX Job Failure Rate", "AWX Job")],
        [("Host Memory Utilization", "Host"), ("AWS ALB Latency", "Gateway"), ("Jenkins Build Failure Rate", "AWX Job")],
        [("Host Disk Usage", "Host"), ("CloudFront Latency", "Gateway"), ("GitLab Pipeline Failure Rate", "AWX Job")],
    ]

    for cluster in cluster_conditions:
        account_id = rng.choice(ACCOUNT_IDS)
        base_time = window_start + timedelta(seconds=rng.randint(0, int((window_end - window_start).total_seconds())))
        policy = rng.choice(POLICIES)

        for condition, entity_type in cluster:
            offset_minutes = rng.randint(0, 5)
            opened_at = base_time + timedelta(minutes=offset_minutes)
            alert = generate_alert(
                rng, window_start, window_end,
                policy=policy, condition=condition, entity_type=entity_type,
                account_id=account_id, opened_at=opened_at
            )
            alerts.append(alert)

    return alerts


def generate_bad_threshold_alerts(rng: random.Random, window_start: datetime, window_end: datetime) -> list:
    alerts = []
    bad_conditions = rng.sample(
        [c for c, et in CONDITIONS if et in ("APM Service", "Host", "Gateway")],
        2
    )

    for condition in bad_conditions:
        entity_type = next(et for c, et in CONDITIONS if c == condition)
        account_id = rng.choice(ACCOUNT_IDS)
        policy = rng.choice(POLICIES)
        threshold = round(rng.uniform(20, 50), 2)
        occurrences = rng.randint(8, 15)

        for _ in range(occurrences):
            observed = round(threshold * rng.uniform(1.4, 1.8), 2)
            alert = generate_alert(
                rng, window_start, window_end,
                policy=policy, condition=condition, entity_type=entity_type,
                account_id=account_id, threshold_value=threshold, observed_value=observed
            )
            alerts.append(alert)

    return alerts


def generate_alert_storm(rng: random.Random, window_start: datetime, window_end: datetime) -> list:
    alerts = []
    account_id = rng.choice(ACCOUNT_IDS)
    storm_start = window_start + timedelta(days=rng.randint(0, 6), hours=rng.randint(0, 23), minutes=rng.randint(0, 50))
    storm_end = storm_start + timedelta(minutes=10)

    storm_conditions = rng.sample(CONDITIONS, rng.randint(5, 8))
    num_alerts = rng.randint(15, 20)

    for _ in range(num_alerts):
        condition, entity_type = rng.choice(storm_conditions)
        policy = rng.choice(POLICIES)
        opened_at = storm_start + timedelta(seconds=rng.randint(0, 600))
        alert = generate_alert(
            rng, window_start, window_end,
            policy=policy, condition=condition, entity_type=entity_type,
            account_id=account_id, opened_at=opened_at
        )
        alerts.append(alert)

    return alerts


def generate_background_noise(rng: random.Random, window_start: datetime, window_end: datetime, count: int) -> list:
    alerts = []
    for _ in range(count):
        alert = generate_alert(rng, window_start, window_end)
        alerts.append(alert)
    return alerts


def generate_alerts(seed: int = 42) -> tuple:
    rng = random.Random(seed)

    window_end = datetime(2026, 8, 15, 23, 59, 59)
    window_start = window_end - timedelta(days=7)

    all_alerts = []

    recurring = generate_recurring_noise(rng, window_start, window_end)
    all_alerts.extend(recurring)
    recurring_count = len(recurring)

    clusters = generate_correlated_clusters(rng, window_start, window_end)
    all_alerts.extend(clusters)
    cluster_count = len(clusters)

    bad_threshold = generate_bad_threshold_alerts(rng, window_start, window_end)
    all_alerts.extend(bad_threshold)
    bad_threshold_count = len(bad_threshold)

    storm = generate_alert_storm(rng, window_start, window_end)
    all_alerts.extend(storm)
    storm_count = len(storm)

    target_total = rng.randint(400, 600)
    background_count = target_total - len(all_alerts)
    if background_count > 0:
        background = generate_background_noise(rng, window_start, window_end, background_count)
        all_alerts.extend(background)

    all_alerts, messy_count = add_messiness(all_alerts, rng)

    return all_alerts, {
        "recurring": recurring_count,
        "clusters": cluster_count,
        "bad_threshold": bad_threshold_count,
        "storm": storm_count,
        "messy": messy_count,
        "total": len(all_alerts),
    }


def generate_runbooks(alerts: list, seed: int = 42) -> tuple:
    rng = random.Random(seed + 1)

    policies_in_alerts = set(a["policy"] for a in alerts)
    policies_list = list(policies_in_alerts)

    num_with_runbook = int(len(policies_list) * 0.7)
    policies_with_runbook = set(rng.sample(policies_list, num_with_runbook))

    runbooks = []
    for policy in policies_with_runbook:
        runbooks.append({
            "policy": policy,
            "runbook_url": f"https://runbooks.example.com/{policy.lower()}"
        })

    policies_without_runbook = policies_in_alerts - policies_with_runbook

    return runbooks, len(policies_without_runbook)


def write_json(data: list, filepath: str):
    with open(filepath, "w") as f:
        json.dump(data, f, indent=2)


def main():
    parser = argparse.ArgumentParser(description="Generate synthetic alert data for Alert Noise Analyzer")
    parser.add_argument("--seed", type=int, default=42, help="Random seed for reproducibility")
    parser.add_argument("--output-dir", type=str, default="data", help="Output directory for generated files")
    args = parser.parse_args()

    alerts, stats = generate_alerts(args.seed)
    runbooks, missing_runbook_count = generate_runbooks(alerts, args.seed)

    write_json(alerts, f"{args.output_dir}/alerts.json")
    write_json(runbooks, f"{args.output_dir}/runbooks.json")

    print(f"Generated {stats['total']} alerts")
    print(f"  Recurring noise alerts: {stats['recurring']}")
    print(f"  Correlated cluster alerts: {stats['clusters']}")
    print(f"  Bad threshold alerts: {stats['bad_threshold']}")
    print(f"  Alert storm alerts: {stats['storm']}")
    print(f"  Messy/malformed records: {stats['messy']}")
    print(f"  Policies lacking runbooks: {missing_runbook_count}")


if __name__ == "__main__":
    main()