#!/usr/bin/env python3
"""
Tests for the report generator.
"""

import pytest

from report.report_generator import generate_report


def test_all_sections_empty():
    """Test report with all four finding lists empty - all sections present with 'no findings' messages."""
    report = generate_report([], [], [], [])

    assert "# Alert Noise Report" in report
    assert "## Summary" in report
    assert "## Recurring Noise" in report
    assert "## Correlated Clusters" in report
    assert "## Threshold Tuning Candidates" in report
    assert "## Runbook Coverage Gaps" in report

    assert "No recurring noise patterns detected above threshold." in report
    assert "No correlated clusters detected above threshold." in report
    assert "No threshold tuning candidates detected above threshold." in report
    assert "No policies missing runbooks." in report

    assert "- Recurring Noise (N+ in window): 0 condition/account pairs" in report
    assert "- Likely Single-Incident Clusters: 0" in report
    assert "- Threshold Tuning Candidates: 0" in report
    assert "- Policies Missing Runbooks: 0" in report


def test_all_sections_with_findings():
    """Test report with findings in all four categories - confirm each section's content appears."""
    recurring = [
        {
            "condition": "High CPU",
            "account_id": "ACC-001",
            "occurrence_count": 10,
            "first_seen": "2026-08-01T12:00:00Z",
            "last_seen": "2026-08-01T18:00:00Z",
            "violation_ids": ["V-001", "V-002"],
        }
    ]

    correlation = [
        {
            "account_id": "ACC-001",
            "cluster_start": "2026-08-01T12:00:00Z",
            "cluster_end": "2026-08-01T12:10:00Z",
            "alert_count": 3,
            "conditions_involved": ["High CPU", "High Memory", "Disk Full"],
            "violation_ids": ["V-001", "V-002", "V-003"],
        }
    ]

    threshold = [
        {
            "condition": "High CPU",
            "configured_threshold": 80.0,
            "median_observed": 30.0,
            "sample_size": 10,
            "deviation_pct": 62.5,
            "direction": "over-sensitive",
        }
    ]

    runbook = [
        {
            "policy": "POL-001",
            "alert_count": 25,
        }
    ]

    report = generate_report(recurring, correlation, threshold, runbook)

    # Check summary counts
    assert "- Recurring Noise (N+ in window): 1 condition/account pairs" in report
    assert "- Likely Single-Incident Clusters: 1" in report
    assert "- Threshold Tuning Candidates: 1" in report
    assert "- Policies Missing Runbooks: 1" in report

    # Check recurring section content
    assert "High CPU" in report
    assert "ACC-001" in report
    assert "10" in report

    # Check correlation section content
    assert "ACC-001" in report
    assert "3" in report
    assert "High CPU" in report
    assert "High Memory" in report

    # Check threshold section content
    assert "80.0" in report
    assert "30.0" in report
    assert "over-sensitive" in report
    assert "62.5" in report

    # Check runbook section content
    assert "POL-001" in report
    assert "25" in report


def test_section_truncation_with_cap():
    """Test that a section with more items than display cap shows truncation note."""
    # Create 20 recurring findings
    recurring = []
    for i in range(20):
        recurring.append(
            {
                "condition": f"Condition {i}",
                "account_id": f"ACC-{i:03d}",
                "occurrence_count": 5 + i,
                "first_seen": "2026-08-01T12:00:00Z",
                "last_seen": "2026-08-01T18:00:00Z",
                "violation_ids": [f"V-{i:03d}"],
            }
        )

    report = generate_report(recurring, [], [], [], display_cap=10)

    # Should show top 10
    assert "Top 10 findings (of 20 total)" in report
    # Should have truncation note
    assert "... and 10 more" in report
    # Should NOT show items beyond cap
    assert "Condition 15" not in report


def test_truncation_all_sections():
    """Test truncation works for all four section types."""
    recurring = [
        {
            "condition": f"C{i}",
            "account_id": f"A{i}",
            "occurrence_count": 5,
            "first_seen": "2026-08-01T12:00:00Z",
            "last_seen": "2026-08-01T18:00:00Z",
            "violation_ids": [f"V{i}"],
        }
        for i in range(20)
    ]
    correlation = [
        {
            "account_id": f"A{i}",
            "cluster_start": "2026-08-01T12:00:00Z",
            "cluster_end": "2026-08-01T12:10:00Z",
            "alert_count": 3,
            "conditions_involved": ["C1", "C2"],
            "violation_ids": [f"V{i}"],
        }
        for i in range(20)
    ]
    threshold = [
        {
            "condition": f"C{i}",
            "configured_threshold": 80.0,
            "median_observed": 30.0,
            "sample_size": 10,
            "deviation_pct": 62.5,
            "direction": "over-sensitive",
        }
        for i in range(20)
    ]
    runbook = [{"policy": f"POL-{i}", "alert_count": 10} for i in range(20)]

    report = generate_report(recurring, correlation, threshold, runbook, display_cap=5)

    assert "Top 5 findings (of 20 total)" in report
    assert "... and 15 more" in report
    # Should appear in all four sections
    assert report.count("Top 5 findings (of 20 total)") == 1  # only in recurring
    assert report.count("Top 5 clusters (of 20 total)") == 1
    assert report.count("Top 5 candidates (of 20 total)") == 1
    assert report.count("Top 5 gaps (of 20 total)") == 1


def test_markdown_format():
    """Test that output is valid markdown with proper table formatting."""
    recurring = [
        {
            "condition": "High CPU",
            "account_id": "ACC-001",
            "occurrence_count": 10,
            "first_seen": "2026-08-01T12:00:00Z",
            "last_seen": "2026-08-01T18:00:00Z",
            "violation_ids": ["V-001"],
        }
    ]

    report = generate_report(recurring, [], [], [])

    # Check markdown table syntax
    assert "| Condition | Account | Count | First Seen | Last Seen |" in report
    assert "|-----------|---------|-------|------------|-----------|" in report
    assert "| High CPU | ACC-001 | 10 |" in report


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
