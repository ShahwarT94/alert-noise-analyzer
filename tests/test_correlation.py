#!/usr/bin/env python3
"""
Tests for the correlation detector.
"""

from datetime import datetime, timedelta

import pytest

from analyzers.correlation import detect_correlated_clusters


def make_alert(
    violation_id: str, condition: str, account_id: str, opened_at: datetime, **kwargs
) -> dict:
    return {
        "violation_id": violation_id,
        "condition": condition,
        "account_id": account_id,
        "opened_at_utc": opened_at.strftime("%Y-%m-%dT%H:%M:%SZ"),
        **kwargs,
    }


def test_three_alert_cascading_cluster():
    """Test a clear 3-alert cascading cluster (different conditions, same account, a few minutes apart)."""
    base_time = datetime(2026, 8, 1, 12, 0, 0)

    alerts = [
        make_alert("V-001", "Host Down", "ACC-001", base_time),
        make_alert(
            "V-002",
            "Azure Gateway Latency",
            "ACC-001",
            base_time + timedelta(minutes=2),
        ),
        make_alert(
            "V-003", "AWX Job Failure", "ACC-001", base_time + timedelta(minutes=4)
        ),
    ]

    findings = detect_correlated_clusters(
        alerts, cluster_window_minutes=5, min_cluster_size=2
    )

    assert len(findings) == 1
    assert findings[0]["account_id"] == "ACC-001"
    assert findings[0]["alert_count"] == 3
    assert set(findings[0]["conditions_involved"]) == {
        "Host Down",
        "Azure Gateway Latency",
        "AWX Job Failure",
    }
    assert findings[0]["violation_ids"] == ["V-001", "V-002", "V-003"]
    assert findings[0]["cluster_start"] == "2026-08-01T12:00:00Z"
    assert findings[0]["cluster_end"] == "2026-08-01T12:04:00Z"


def test_different_accounts_not_clustered():
    """Test that alerts on different accounts at same timestamp are NOT clustered together."""
    base_time = datetime(2026, 8, 1, 12, 0, 0)

    alerts = [
        make_alert("V-001", "Host Down", "ACC-001", base_time),
        make_alert("V-002", "Azure Gateway Latency", "ACC-002", base_time),
        make_alert(
            "V-003", "AWX Job Failure", "ACC-001", base_time + timedelta(minutes=2)
        ),
    ]

    findings = detect_correlated_clusters(
        alerts, cluster_window_minutes=5, min_cluster_size=2
    )

    assert len(findings) == 1
    assert findings[0]["account_id"] == "ACC-001"
    assert findings[0]["alert_count"] == 2
    assert set(findings[0]["conditions_involved"]) == {"Host Down", "AWX Job Failure"}


def test_alerts_outside_window_not_clustered():
    """Test that alerts far apart in time (outside window) on same account are NOT clustered."""
    base_time = datetime(2026, 8, 1, 12, 0, 0)

    alerts = [
        make_alert("V-001", "Host Down", "ACC-001", base_time),
        make_alert(
            "V-002",
            "Azure Gateway Latency",
            "ACC-001",
            base_time + timedelta(minutes=10),
        ),
        make_alert(
            "V-003", "AWX Job Failure", "ACC-001", base_time + timedelta(minutes=20)
        ),
    ]

    findings = detect_correlated_clusters(
        alerts, cluster_window_minutes=5, min_cluster_size=2
    )

    assert findings == []


def test_duplicate_violation_id_in_cluster():
    """Test that duplicate violation_id within a cluster doesn't appear twice in output."""
    base_time = datetime(2026, 8, 1, 12, 0, 0)

    alerts = [
        make_alert("V-001", "Host Down", "ACC-001", base_time),
        make_alert("V-001", "Host Down", "ACC-001", base_time + timedelta(minutes=1)),
        make_alert(
            "V-002",
            "Azure Gateway Latency",
            "ACC-001",
            base_time + timedelta(minutes=2),
        ),
        make_alert(
            "V-003", "AWX Job Failure", "ACC-001", base_time + timedelta(minutes=3)
        ),
    ]

    findings = detect_correlated_clusters(
        alerts, cluster_window_minutes=5, min_cluster_size=2
    )

    assert len(findings) == 1
    assert findings[0]["alert_count"] == 4
    assert findings[0]["violation_ids"] == ["V-001", "V-002", "V-003"]


def test_chain_of_alerts_extends_window():
    """
    Test edge case: chain of alerts each within window of previous,
    but first and last are further apart than window.

    This implementation treats it as ONE cluster because each new alert
    extends the window from itself (greedy clustering). This is the
    expected behavior - it captures cascading incidents where each
    alert triggers the next within the window.
    """
    base_time = datetime(2026, 8, 1, 12, 0, 0)

    alerts = [
        make_alert("V-001", "Alert 1", "ACC-001", base_time),
        make_alert("V-002", "Alert 2", "ACC-001", base_time + timedelta(minutes=3)),
        make_alert("V-003", "Alert 3", "ACC-001", base_time + timedelta(minutes=6)),
        make_alert("V-004", "Alert 4", "ACC-001", base_time + timedelta(minutes=9)),
    ]

    findings = detect_correlated_clusters(
        alerts, cluster_window_minutes=5, min_cluster_size=2
    )

    assert len(findings) == 1
    assert findings[0]["alert_count"] == 4
    assert findings[0]["cluster_start"] == "2026-08-01T12:00:00Z"
    assert findings[0]["cluster_end"] == "2026-08-01T12:09:00Z"


def test_zero_alerts_returns_empty():
    """Test that zero alerts returns empty list, not error."""
    findings = detect_correlated_clusters(
        [], cluster_window_minutes=5, min_cluster_size=2
    )
    assert findings == []


def test_no_clusters_found_returns_empty():
    """Test that alerts exist but no clusters meet min_size returns empty list."""
    base_time = datetime(2026, 8, 1, 12, 0, 0)

    alerts = [
        make_alert("V-001", "Host Down", "ACC-001", base_time),
        make_alert(
            "V-002",
            "Azure Gateway Latency",
            "ACC-001",
            base_time + timedelta(minutes=10),
        ),
    ]

    findings = detect_correlated_clusters(
        alerts, cluster_window_minutes=5, min_cluster_size=3
    )

    assert findings == []


def test_missing_account_id_skipped():
    """Test that records missing account_id are skipped without crashing."""
    base_time = datetime(2026, 8, 1, 12, 0, 0)

    alerts = [
        make_alert("V-001", "Host Down", "ACC-001", base_time),
        {
            "violation_id": "V-002",
            "condition": "Azure Gateway Latency",
            "opened_at_utc": (base_time + timedelta(minutes=1)).strftime(
                "%Y-%m-%dT%H:%M:%SZ"
            ),
        },
        make_alert(
            "V-003", "AWX Job Failure", "ACC-001", base_time + timedelta(minutes=2)
        ),
    ]

    findings = detect_correlated_clusters(
        alerts, cluster_window_minutes=5, min_cluster_size=2
    )

    assert len(findings) == 1
    assert findings[0]["alert_count"] == 2


def test_missing_opened_at_utc_skipped():
    """Test that records missing opened_at_utc are skipped without crashing."""
    base_time = datetime(2026, 8, 1, 12, 0, 0)

    alerts = [
        make_alert("V-001", "Host Down", "ACC-001", base_time),
        {
            "violation_id": "V-002",
            "condition": "Azure Gateway Latency",
            "account_id": "ACC-001",
        },
        make_alert(
            "V-003", "AWX Job Failure", "ACC-001", base_time + timedelta(minutes=2)
        ),
    ]

    findings = detect_correlated_clusters(
        alerts, cluster_window_minutes=5, min_cluster_size=2
    )

    assert len(findings) == 1
    assert findings[0]["alert_count"] == 2


def test_bad_timestamp_format_skipped():
    """Test that records with unparseable timestamps are skipped without crashing."""
    base_time = datetime(2026, 8, 1, 12, 0, 0)

    alerts = [
        make_alert("V-001", "Host Down", "ACC-001", base_time),
        {
            "violation_id": "V-002",
            "condition": "Azure Gateway Latency",
            "account_id": "ACC-001",
            "opened_at_utc": "not-a-date",
        },
        make_alert(
            "V-003", "AWX Job Failure", "ACC-001", base_time + timedelta(minutes=2)
        ),
    ]

    findings = detect_correlated_clusters(
        alerts, cluster_window_minutes=5, min_cluster_size=2
    )

    assert len(findings) == 1
    assert findings[0]["alert_count"] == 2


def test_findings_sorted_by_alert_count_desc_then_start_asc():
    """Test that findings are sorted by alert_count descending, then cluster_start ascending."""
    base_time = datetime(2026, 8, 1, 12, 0, 0)

    alerts = []
    for i in range(3):
        alerts.append(
            make_alert(
                f"V-{i:03d}",
                f"Alert {i}",
                "ACC-001",
                base_time + timedelta(minutes=i * 2),
            )
        )
    for i in range(5):
        alerts.append(
            make_alert(
                f"V-{i+3:03d}",
                f"Alert {i+3}",
                "ACC-002",
                base_time + timedelta(minutes=i * 2),
            )
        )
    for i in range(4):
        alerts.append(
            make_alert(
                f"V-{i+8:03d}",
                f"Alert {i+8}",
                "ACC-003",
                base_time + timedelta(hours=1, minutes=i * 2),
            )
        )

    findings = detect_correlated_clusters(
        alerts, cluster_window_minutes=5, min_cluster_size=2
    )

    assert len(findings) == 3
    assert findings[0]["account_id"] == "ACC-002"
    assert findings[0]["alert_count"] == 5
    assert findings[1]["account_id"] == "ACC-003"
    assert findings[1]["alert_count"] == 4
    assert findings[2]["account_id"] == "ACC-001"
    assert findings[2]["alert_count"] == 3


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
