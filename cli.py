#!/usr/bin/env python3
"""
Top-level CLI for Alert Noise Analyzer.
Runs all four analyzers and generates a consolidated report.
"""

import argparse
import json
import sys
from pathlib import Path

from analyzers.correlation import detect_correlated_clusters
from analyzers.recurring import detect_recurring_patterns
from analyzers.runbook_coverage import detect_runbook_gaps
from analyzers.runbook_coverage import load_json as load_runbooks
from analyzers.threshold import detect_threshold_issues
from report.report_generator import generate_report


def load_alerts(filepath: str) -> list[dict]:
    """Load alerts from a JSON file."""
    with open(filepath) as f:
        data: list[dict] = json.load(f)
    return data


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Alert Noise Analyzer - detect noise patterns in alert data",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python cli.py --input data/alerts.json --runbooks data/runbooks.json
  python cli.py --input data/alerts.json --runbooks data/runbooks.json --markdown-out report.md
  python cli.py --input data/alerts.json --runbooks data/runbooks.json --window-days 14 --min-occurrences 10
        """,
    )

    parser.add_argument(
        "--input", type=str, required=True, help="Path to alerts JSON file"
    )
    parser.add_argument(
        "--runbooks", type=str, required=True, help="Path to runbooks JSON file"
    )
    parser.add_argument(
        "--markdown-out", type=str, help="Write report to this markdown file"
    )
    parser.add_argument(
        "--display-cap",
        type=int,
        default=15,
        help="Max findings to show per section (default: 15)",
    )

    # Recurring detector options
    parser.add_argument(
        "--window-days",
        type=int,
        default=7,
        help="Rolling window in days for recurring detector (default: 7)",
    )
    parser.add_argument(
        "--min-occurrences",
        type=int,
        default=5,
        help="Minimum occurrences to flag for recurring detector (default: 5)",
    )

    # Correlation detector options
    parser.add_argument(
        "--cluster-window-minutes",
        type=int,
        default=5,
        help="Cluster window in minutes for correlation detector (default: 5)",
    )
    parser.add_argument(
        "--min-cluster-size",
        type=int,
        default=2,
        help="Minimum cluster size for correlation detector (default: 2)",
    )

    # Threshold detector options
    parser.add_argument(
        "--deviation-ratio",
        type=float,
        default=0.3,
        help="Deviation ratio for threshold detector (default: 0.3 = 30%%)",
    )

    args = parser.parse_args()

    # Load input files with clear error messages
    input_path = Path(args.input)
    runbooks_path = Path(args.runbooks)

    if not input_path.exists():
        print(f"Error: Alerts file not found: {args.input}", file=sys.stderr)
        sys.exit(1)

    if not runbooks_path.exists():
        print(f"Error: Runbooks file not found: {args.runbooks}", file=sys.stderr)
        sys.exit(1)

    try:
        alerts = load_alerts(args.input)
    except json.JSONDecodeError as e:
        print(f"Error: Failed to parse alerts JSON: {e}", file=sys.stderr)
        sys.exit(1)

    try:
        runbooks = load_runbooks(args.runbooks)
    except json.JSONDecodeError as e:
        print(f"Error: Failed to parse runbooks JSON: {e}", file=sys.stderr)
        sys.exit(1)

    # Run all four analyzers
    recurring_findings = detect_recurring_patterns(
        alerts,
        window_days=args.window_days,
        min_occurrences=args.min_occurrences,
    )

    correlation_findings = detect_correlated_clusters(
        alerts,
        cluster_window_minutes=args.cluster_window_minutes,
        min_cluster_size=args.min_cluster_size,
    )

    threshold_findings = detect_threshold_issues(
        alerts,
        deviation_ratio=args.deviation_ratio,
    )

    runbook_findings = detect_runbook_gaps(alerts, runbooks)

    # Generate report
    report = generate_report(
        recurring_findings,
        correlation_findings,
        threshold_findings,
        runbook_findings,
        display_cap=args.display_cap,
    )

    # Print to stdout
    print(report)

    # Write to file if requested
    if args.markdown_out:
        try:
            with open(args.markdown_out, "w") as f:
                f.write(report)
            print(f"\nReport written to {args.markdown_out}")
        except OSError as e:
            print(
                f"Error: Failed to write report to {args.markdown_out}: {e}",
                file=sys.stderr,
            )
            sys.exit(1)


if __name__ == "__main__":
    main()
