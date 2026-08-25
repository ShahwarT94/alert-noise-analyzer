#!/usr/bin/env python3
"""
Tests for the recurring pattern detector.
"""

import pytest
from datetime import datetime, timedelta
from analyzers.recurring import detect_recurring_patterns


def make_alert(
    violation_id: str,
    condition: str,
    account_id: str,
    opened_at: datetime,
    **kwargs
) -> dict:
    return {
        "violation_id": violation_id,
        "condition": condition,
        "account_id": account_id,
        "opened_at_utc": opened_at.strftime("%Y-%m-%dT%H:%M:%SZ"),
        **kwargs
    }


def test_detect_recurring_patterns_basic():
    """Test with a small hand-built list where we know exactly which pairs should be flagged."""
    base_time = datetime(2026, 8, 1, 12, 0, 0)

    alerts = [
        make_alert("V-001", "High CPU", "ACC-001", base_time),
        make_alert("V-002", "High CPU", "ACC-001", base_time + timedelta(hours=1)),
        make_alert("V-003", "High CPU", "ACC-001", base_time + timedelta(hours=2)),
        make_alert("V-004", "High CPU", "ACC-001", base_time + timedelta(hours=3)),
        make_alert("V-005", "High CPU", "ACC-001", base_time + timedelta(hours=4)),
        make_alert("V-006", "High CPU", "ACC-001", base_time + timedelta(hours=5)),
        make_alert("V-007", "High Memory", "ACC-001", base_time),
        make_alert("V-008", "High Memory", "ACC-001", base_time + timedelta(hours=1)),
        make_alert("V-009", "High Memory", "ACC-001", base_time + timedelta(hours=2)),
        make_alert("V-010", "High CPU", "ACC-002", base_time),
        make_alert("V-011", "High CPU", "ACC-002", base_time + timedelta(hours=1)),
    ]

    findings = detect_recurring_patterns(alerts, window_days=7, min_occurrences=5)

    assert len(findings) == 1
    assert findings[0]["condition"] == "High CPU"
    assert findings[0]["account_id"] == "ACC-001"
    assert findings[0]["occurrence_count"] == 6
    assert findings[0]["violation_ids"] == ["V-001", "V-002", "V-003", "V-004", "V-005", "V-006"]


def test_duplicate_violation_ids_not_double_counted():
    """Test that duplicate violation_ids are not double-counted."""
    base_time = datetime(2026, 8, 1, 12, 0, 0)

    alerts = [
        make_alert("V-001", "High CPU", "ACC-001", base_time),
        make_alert("V-001", "High CPU", "ACC-001", base_time + timedelta(hours=1)),
        make_alert("V-002", "High CPU", "ACC-001", base_time + timedelta(hours=2)),
        make_alert("V-003", "High CPU", "ACC-001", base_time + timedelta(hours=3)),
        make_alert("V-004", "High CPU", "ACC-001", base_time + timedelta(hours=4)),
        make_alert("V-005", "High CPU", "ACC-001", base_time + timedelta(hours=5)),
    ]

    findings = detect_recurring_patterns(alerts, window_days=7, min_occurrences=5)

    assert len(findings) == 1
    assert findings[0]["occurrence_count"] == 5
    assert findings[0]["violation_ids"] == ["V-001", "V-002", "V-003", "V-004", "V-005"]


def test_missing_condition_skipped():
    """Test that a record missing 'condition' is skipped without crashing."""
    base_time = datetime(2026, 8, 1, 12, 0, 0)

    alerts = [
        {"violation_id": "V-001", "account_id": "ACC-001", "opened_at_utc": base_time.strftime("%Y-%m-%dT%H:%M:%SZ")},
        make_alert("V-002", "High CPU", "ACC-001", base_time + timedelta(hours=1)),
        make_alert("V-003", "High CPU", "ACC-001", base_time + timedelta(hours=2)),
        make_alert("V-004", "High CPU", "ACC-001", base_time + timedelta(hours=3)),
        make_alert("V-005", "High CPU", "ACC-001", base_time + timedelta(hours=4)),
        make_alert("V-006", "High CPU", "ACC-001", base_time + timedelta(hours=5)),
    ]

    findings = detect_recurring_patterns(alerts, window_days=7, min_occurrences=5)

    assert len(findings) == 1
    assert findings[0]["occurrence_count"] == 5


def test_zero_matching_alerts_returns_empty_list():
    """Test with zero matching alerts, confirming it returns an empty list, not an error."""
    base_time = datetime(2026, 8, 1, 12, 0, 0)

    alerts = [
        make_alert("V-001", "High CPU", "ACC-001", base_time),
        make_alert("V-002", "High Memory", "ACC-001", base_time + timedelta(hours=1)),
        make_alert("V-003", "High Disk", "ACC-002", base_time + timedelta(hours=2)),
    ]

    findings = detect_recurring_patterns(alerts, window_days=7, min_occurrences=5)

    assert findings == []


def test_unsorted_input():
    """Test that unsorted input is handled correctly."""
    base_time = datetime(2026, 8, 1, 12, 0, 0)

    alerts = [
        make_alert("V-003", "High CPU", "ACC-001", base_time + timedelta(hours=2)),
        make_alert("V-001", "High CPU", "ACC-001", base_time),
        make_alert("V-005", "High CPU", "ACC-001", base_time + timedelta(hours=4)),
        make_alert("V-002", "High CPU", "ACC-001", base_time + timedelta(hours=1)),
        make_alert("V-006", "High CPU", "ACC-001", base_time + timedelta(hours=5)),
        make_alert("V-004", "High CPU", "ACC-001", base_time + timedelta(hours=3)),
    ]

    findings = detect_recurring_patterns(alerts, window_days=7, min_occurrences=5)

    assert len(findings) == 1
    assert findings[0]["occurrence_count"] == 6


def test_bad_timestamp_format_skipped():
    """Test that bad timestamp format is skipped without crashing."""
    base_time = datetime(2026, 8, 1, 12, 0, 0)

    alerts = [
        make_alert("V-001", "High CPU", "ACC-001", base_time),
        {"violation_id": "V-002", "condition": "High CPU", "account_id": "ACC-001", "opened_at_utc": "not-a-date"},
        make_alert("V-003", "High CPU", "ACC-001", base_time + timedelta(hours=1)),
        make_alert("V-004", "High CPU", "ACC-001", base_time + timedelta(hours=2)),
        make_alert("V-005", "High CPU", "ACC-001", base_time + timedelta(hours=3)),
        make_alert("V-006", "High CPU", "ACC-001", base_time + timedelta(hours=4)),
    ]

    findings = detect_recurring_patterns(alerts, window_days=7, min_occurrences=5)

    assert len(findings) == 1
    assert findings[0]["occurrence_count"] == 5


def test_missing_account_id_skipped():
    """Test that a record missing 'account_id' is skipped without crashing."""
    base_time = datetime(2026, 8, 1, 12, 0, 0)

    alerts = [
        make_alert("V-001", "High CPU", "ACC-001", base_time),
        {"violation_id": "V-002", "condition": "High CPU", "opened_at_utc": (base_time + timedelta(hours=1)).strftime("%Y-%m-%dT%H:%M:%SZ")},
        make_alert("V-003", "High CPU", "ACC-001", base_time + timedelta(hours=2)),
        make_alert("V-004", "High CPU", "ACC-001", base_time + timedelta(hours=3)),
        make_alert("V-005", "High CPU", "ACC-001", base_time + timedelta(hours=4)),
        make_alert("V-006", "High CPU", "ACC-001", base_time + timedelta(hours=5)),
    ]

    findings = detect_recurring_patterns(alerts, window_days=7, min_occurrences=5)

    assert len(findings) == 1
    assert findings[0]["occurrence_count"] == 5


def test_missing_opened_at_utc_skipped():
    """Test that a record missing 'opened_at_utc' is skipped without crashing."""
    base_time = datetime(2026, 8, 1, 12, 0, 0)

    alerts = [
        make_alert("V-001", "High CPU", "ACC-001", base_time),
        {"violation_id": "V-002", "condition": "High CPU", "account_id": "ACC-001"},
        make_alert("V-003", "High CPU", "ACC-001", base_time + timedelta(hours=1)),
        make_alert("V-004", "High CPU", "ACC-001", base_time + timedelta(hours=2)),
        make_alert("V-005", "High CPU", "ACC-001", base_time + timedelta(hours=3)),
        make_alert("V-006", "High CPU", "ACC-001", base_time + timedelta(hours=4)),
    ]

    findings = detect_recurring_patterns(alerts, window_days=7, min_occurrences=5)

    assert len(findings) == 1
    assert findings[0]["occurrence_count"] == 5


def test_findings_sorted_by_occurrence_count_descending():
    """Test that findings are sorted by occurrence_count descending."""
    base_time = datetime(2026, 8, 1, 12, 0, 0)

    alerts = []
    for i in range(5):
        alerts.append(make_alert(f"V-{i:03d}", "Medium CPU", "ACC-001", base_time + timedelta(hours=i)))
    for i in range(8):
        alerts.append(make_alert(f"V-{i+5:03d}", "High CPU", "ACC-001", base_time + timedelta(hours=i)))
    for i in range(3):
        alerts.append(make_alert(f"V-{i+13:03d}", "Low CPU", "ACC-001", base_time + timedelta(hours=i)))

    findings = detect_recurring_patterns(alerts, window_days=7, min_occurrences=3)

    assert len(findings) == 3
    assert findings[0]["condition"] == "High CPU"
    assert findings[0]["occurrence_count"] == 8
    assert findings[1]["condition"] == "Medium CPU"
    assert findings[1]["occurrence_count"] == 5
    assert findings[2]["condition"] == "Low CPU"
    assert findings[2]["occurrence_count"] == 3


if __name__ == "__main__":
    pytest.main([__file__, "-v"])