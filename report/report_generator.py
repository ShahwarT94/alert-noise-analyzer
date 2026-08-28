#!/usr/bin/env python3
"""
Report generator for Alert Noise Analyzer.
Consolidates all four detectors' findings into a readable markdown report.
"""

DEFAULT_DISPLAY_CAP = 15


def _format_recurring_section(
    findings: list[dict], cap: int = DEFAULT_DISPLAY_CAP
) -> str:
    """Format the recurring noise section."""
    lines = []
    if not findings:
        lines.append("No recurring noise patterns detected above threshold.")
        return "\n".join(lines)

    lines.append(f"Top {min(len(findings), cap)} findings (of {len(findings)} total):")
    lines.append("")
    lines.append("| Condition | Account | Count | First Seen | Last Seen |")
    lines.append("|-----------|---------|-------|------------|-----------|")

    for f in findings[:cap]:
        condition = f["condition"][:45]
        account = f["account_id"]
        count = f["occurrence_count"]
        first = f["first_seen"][:19]
        last = f["last_seen"][:19]
        lines.append(f"| {condition} | {account} | {count} | {first} | {last} |")

    if len(findings) > cap:
        lines.append(f"\n... and {len(findings) - cap} more")

    return "\n".join(lines)


def _format_correlation_section(
    findings: list[dict], cap: int = DEFAULT_DISPLAY_CAP
) -> str:
    """Format the correlated clusters section."""
    lines = []
    if not findings:
        lines.append("No correlated clusters detected above threshold.")
        return "\n".join(lines)

    lines.append(f"Top {min(len(findings), cap)} clusters (of {len(findings)} total):")
    lines.append("")
    lines.append(
        "| Account | Cluster Start | Cluster End | Alert Count | Conditions Involved |"
    )
    lines.append(
        "|---------|---------------|-------------|-------------|---------------------|"
    )

    for f in findings[:cap]:
        account = f["account_id"]
        start = f["cluster_start"][:19]
        end = f["cluster_end"][:19]
        count = f["alert_count"]
        conditions = ", ".join(f["conditions_involved"][:3])
        if len(f["conditions_involved"]) > 3:
            conditions += f" (+{len(f['conditions_involved']) - 3} more)"
        lines.append(f"| {account} | {start} | {end} | {count} | {conditions} |")

    if len(findings) > cap:
        lines.append(f"\n... and {len(findings) - cap} more")

    return "\n".join(lines)


def _format_threshold_section(
    findings: list[dict], cap: int = DEFAULT_DISPLAY_CAP
) -> str:
    """Format the threshold tuning candidates section."""
    lines = []
    if not findings:
        lines.append("No threshold tuning candidates detected above threshold.")
        return "\n".join(lines)

    lines.append(
        f"Top {min(len(findings), cap)} candidates (of {len(findings)} total):"
    )
    lines.append("")
    lines.append(
        "| Condition | Configured Threshold | Median Observed | Direction | Deviation % |"
    )
    lines.append(
        "|-----------|----------------------|-----------------|-----------|-------------|"
    )

    for f in findings[:cap]:
        condition = f["condition"][:40]
        threshold = f["configured_threshold"]
        median_obs = f["median_observed"]
        direction = f["direction"]
        dev_pct = f["deviation_pct"]
        lines.append(
            f"| {condition} | {threshold:.2f} | {median_obs:.2f} | {direction} | {dev_pct:.2f}% |"
        )

    if len(findings) > cap:
        lines.append(f"\n... and {len(findings) - cap} more")

    return "\n".join(lines)


def _format_runbook_section(
    findings: list[dict], cap: int = DEFAULT_DISPLAY_CAP
) -> str:
    """Format the runbook coverage gaps section."""
    lines = []
    if not findings:
        lines.append("No policies missing runbooks.")
        return "\n".join(lines)

    lines.append(f"Top {min(len(findings), cap)} gaps (of {len(findings)} total):")
    lines.append("")
    lines.append("| Policy | Alert Count |")
    lines.append("|--------|-------------|")

    for f in findings[:cap]:
        policy = f["policy"]
        count = f["alert_count"]
        lines.append(f"| {policy} | {count} |")

    if len(findings) > cap:
        lines.append(f"\n... and {len(findings) - cap} more")

    return "\n".join(lines)


def generate_report(
    recurring_findings: list[dict],
    correlation_findings: list[dict],
    threshold_findings: list[dict],
    runbook_findings: list[dict],
    display_cap: int = DEFAULT_DISPLAY_CAP,
) -> str:
    """
    Consolidates all four detectors' findings into one readable report
    string. Returns markdown-formatted text (so it works equally well
    printed to terminal or written to a .md file).
    """
    sections = []

    sections.append("# Alert Noise Report")
    sections.append("")

    # Summary
    sections.append("## Summary")
    sections.append(
        f"- Recurring Noise (N+ in window): {len(recurring_findings)} condition/account pairs"
    )
    sections.append(f"- Likely Single-Incident Clusters: {len(correlation_findings)}")
    sections.append(f"- Threshold Tuning Candidates: {len(threshold_findings)}")
    sections.append(f"- Policies Missing Runbooks: {len(runbook_findings)}")
    sections.append("")

    # Recurring Noise
    sections.append("## Recurring Noise")
    sections.append(_format_recurring_section(recurring_findings, display_cap))
    sections.append("")

    # Correlated Clusters
    sections.append("## Correlated Clusters")
    sections.append(_format_correlation_section(correlation_findings, display_cap))
    sections.append("")

    # Threshold Tuning Candidates
    sections.append("## Threshold Tuning Candidates")
    sections.append(_format_threshold_section(threshold_findings, display_cap))
    sections.append("")

    # Runbook Coverage Gaps
    sections.append("## Runbook Coverage Gaps")
    sections.append(_format_runbook_section(runbook_findings, display_cap))
    sections.append("")

    return "\n".join(sections)
