#!/usr/bin/env python3
"""
Tests for the runbook coverage checker.
"""

import pytest

from analyzers.runbook_coverage import detect_runbook_gaps


def make_alert(policy: str, **kwargs) -> dict:
    return {"policy": policy, **kwargs}


def test_policy_in_alerts_missing_from_runbooks_flagged():
    """Test policy present in alerts but missing from runbooks - flagged."""
    alerts = [
        make_alert("POL-001"),
        make_alert("POL-001"),
        make_alert("POL-002"),
    ]
    runbooks = [
        {"policy": "POL-002", "runbook_url": "https://runbooks.example.com/pol-002"},
    ]

    findings = detect_runbook_gaps(alerts, runbooks)

    assert len(findings) == 1
    assert findings[0]["policy"] == "POL-001"
    assert findings[0]["alert_count"] == 2


def test_policy_in_both_not_flagged():
    """Test policy present in both alerts and runbooks - NOT flagged."""
    alerts = [
        make_alert("POL-001"),
        make_alert("POL-002"),
    ]
    runbooks = [
        {"policy": "POL-001", "runbook_url": "https://runbooks.example.com/pol-001"},
        {"policy": "POL-002", "runbook_url": "https://runbooks.example.com/pol-002"},
    ]

    findings = detect_runbook_gaps(alerts, runbooks)

    assert findings == []


def test_missing_policy_field_in_alerts_skipped():
    """Test alerts with missing policy field - skipped without crashing."""
    alerts = [
        make_alert("POL-001"),
        {"violation_id": "V-001", "condition": "High CPU"},
        make_alert("POL-002"),
    ]
    runbooks = [
        {"policy": "POL-001", "runbook_url": "https://runbooks.example.com/pol-001"},
    ]

    findings = detect_runbook_gaps(alerts, runbooks)

    assert len(findings) == 1
    assert findings[0]["policy"] == "POL-002"
    assert findings[0]["alert_count"] == 1


def test_empty_runbooks_list_all_policies_flagged():
    """Test empty runbooks list - all policies in alerts flagged."""
    alerts = [
        make_alert("POL-001"),
        make_alert("POL-002"),
        make_alert("POL-002"),
    ]
    runbooks = []

    findings = detect_runbook_gaps(alerts, runbooks)

    assert len(findings) == 2
    policies = {f["policy"] for f in findings}
    assert policies == {"POL-001", "POL-002"}


def test_sorting_by_alert_count_descending():
    """Test that findings are sorted by alert_count descending."""
    alerts = [
        make_alert("POL-001"),
        make_alert("POL-002"),
        make_alert("POL-002"),
        make_alert("POL-002"),
        make_alert("POL-003"),
        make_alert("POL-003"),
    ]
    runbooks = [
        {"policy": "POL-001", "runbook_url": "https://runbooks.example.com/pol-001"},
    ]

    findings = detect_runbook_gaps(alerts, runbooks)

    assert len(findings) == 2
    assert findings[0]["policy"] == "POL-002"
    assert findings[0]["alert_count"] == 3
    assert findings[1]["policy"] == "POL-003"
    assert findings[1]["alert_count"] == 2


def test_malformed_runbook_entries_skipped():
    """Test runbooks list with malformed entries - skipped, don't crash."""
    alerts = [
        make_alert("POL-001"),
        make_alert("POL-002"),
    ]
    runbooks = [
        {"policy": "POL-001", "runbook_url": "https://runbooks.example.com/pol-001"},
        {"runbook_url": "https://runbooks.example.com/broken"},
        {"policy": None, "runbook_url": "https://runbooks.example.com/also-broken"},
        "not-a-dict",
    ]

    findings = detect_runbook_gaps(alerts, runbooks)

    assert len(findings) == 1
    assert findings[0]["policy"] == "POL-002"


def test_no_alerts_returns_empty():
    """Test with no alerts returns empty list."""
    findings = detect_runbook_gaps(
        [],
        [{"policy": "POL-001", "runbook_url": "https://runbooks.example.com/pol-001"}],
    )
    assert findings == []


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
