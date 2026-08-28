#!/usr/bin/env python3
"""
Tests for the threshold sanity checker.
"""

import pytest

from analyzers.threshold import detect_threshold_issues


def make_alert(
    condition: str, threshold_value: float, observed_value: float, **kwargs
) -> dict:
    return {
        "condition": condition,
        "threshold_value": threshold_value,
        "observed_value": observed_value,
        **kwargs,
    }


def test_condition_observed_below_threshold_flagged():
    """Test condition with observed values clearly and consistently below threshold - flagged as over-sensitive."""
    alerts = [
        make_alert("High CPU", 80.0, 30.0),
        make_alert("High CPU", 80.0, 35.0),
        make_alert("High CPU", 80.0, 28.0),
        make_alert("High CPU", 80.0, 32.0),
        make_alert("High CPU", 80.0, 31.0),
    ]

    findings = detect_threshold_issues(alerts, deviation_ratio=0.3)

    assert len(findings) == 1
    assert findings[0]["condition"] == "High CPU"
    assert findings[0]["configured_threshold"] == 80.0
    assert findings[0]["median_observed"] == 31.0
    assert findings[0]["direction"] == "over-sensitive"
    assert findings[0]["deviation_pct"] > 30


def test_condition_observed_above_threshold_flagged():
    """Test condition with observed values clearly above threshold - flagged as under-sensitive."""
    alerts = [
        make_alert("High Memory", 50.0, 90.0),
        make_alert("High Memory", 50.0, 95.0),
        make_alert("High Memory", 50.0, 88.0),
        make_alert("High Memory", 50.0, 92.0),
    ]

    findings = detect_threshold_issues(alerts, deviation_ratio=0.3)

    assert len(findings) == 1
    assert findings[0]["condition"] == "High Memory"
    assert findings[0]["configured_threshold"] == 50.0
    assert findings[0]["median_observed"] == 91.0
    assert findings[0]["direction"] == "under-sensitive"
    assert findings[0]["deviation_pct"] > 30


def test_condition_close_to_threshold_not_flagged():
    """Test condition with observed values close to threshold - NOT flagged."""
    alerts = [
        make_alert("Normal CPU", 80.0, 75.0),
        make_alert("Normal CPU", 80.0, 82.0),
        make_alert("Normal CPU", 80.0, 78.0),
        make_alert("Normal CPU", 80.0, 81.0),
    ]

    findings = detect_threshold_issues(alerts, deviation_ratio=0.3)

    assert findings == []


def test_condition_fewer_than_three_samples_not_reported():
    """Test condition with fewer than 3 valid samples - NOT reported at all."""
    alerts = [
        make_alert("Sparse CPU", 80.0, 30.0),
        make_alert("Sparse CPU", 80.0, 35.0),
    ]

    findings = detect_threshold_issues(alerts, deviation_ratio=0.3)

    assert findings == []


def test_mixed_null_values_excluded_no_crash():
    """Test mixed null/missing threshold_value or observed_value - excluded from calc, doesn't crash."""
    alerts = [
        make_alert("Mixed CPU", 80.0, 30.0),
        make_alert("Mixed CPU", 80.0, 32.0),
        make_alert("Mixed CPU", 80.0, 28.0),
        make_alert("Mixed CPU", 80.0, 31.0),
        make_alert("Mixed CPU", None, 35.0),
        make_alert("Mixed CPU", 80.0, None),
        {"condition": "Mixed CPU", "threshold_value": 80.0, "observed_value": 33.0},
        {"condition": "Mixed CPU", "threshold_value": None, "observed_value": None},
    ]

    findings = detect_threshold_issues(alerts, deviation_ratio=0.3)

    assert len(findings) == 1
    assert findings[0]["condition"] == "Mixed CPU"
    assert findings[0]["sample_size"] == 5


def test_varying_thresholds_uses_most_common():
    """Test condition with varying threshold_values uses the most common one."""
    alerts = [
        make_alert("Varying CPU", 80.0, 30.0),
        make_alert("Varying CPU", 80.0, 32.0),
        make_alert("Varying CPU", 80.0, 28.0),
        make_alert("Varying CPU", 90.0, 31.0),
        make_alert("Varying CPU", 90.0, 33.0),
    ]

    findings = detect_threshold_issues(alerts, deviation_ratio=0.3)

    assert len(findings) == 1
    assert findings[0]["configured_threshold"] == 80.0


def test_invalid_numeric_values_skipped():
    """Test that non-numeric threshold/observed values are skipped without crashing."""
    alerts = [
        make_alert("Bad Values", 80.0, 30.0),
        make_alert("Bad Values", 80.0, 32.0),
        make_alert("Bad Values", 80.0, 28.0),
        {
            "condition": "Bad Values",
            "threshold_value": "not-a-number",
            "observed_value": 30.0,
        },
        {
            "condition": "Bad Values",
            "threshold_value": 80.0,
            "observed_value": "also-bad",
        },
    ]

    findings = detect_threshold_issues(alerts, deviation_ratio=0.3)

    assert len(findings) == 1
    assert findings[0]["sample_size"] == 3


def test_zero_threshold_skipped():
    """Test that zero threshold is skipped to avoid division by zero."""
    alerts = [
        make_alert("Zero Threshold", 0.0, 30.0),
        make_alert("Zero Threshold", 0.0, 35.0),
        make_alert("Zero Threshold", 0.0, 28.0),
    ]

    findings = detect_threshold_issues(alerts, deviation_ratio=0.3)

    assert findings == []


def test_findings_sorted_by_deviation_pct_descending():
    """Test that findings are sorted by deviation_pct descending."""
    alerts = []
    for i in range(5):
        alerts.append(make_alert("Small Dev", 100.0, 85.0 + i))
    for i in range(5):
        alerts.append(make_alert("Large Dev", 100.0, 30.0 + i))
    for i in range(5):
        alerts.append(make_alert("Medium Dev", 100.0, 60.0 + i))

    findings = detect_threshold_issues(alerts, deviation_ratio=0.1)

    assert len(findings) == 3
    assert findings[0]["condition"] == "Large Dev"
    assert findings[1]["condition"] == "Medium Dev"
    assert findings[2]["condition"] == "Small Dev"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
