#!/usr/bin/env python3
"""
CLI entry point for AgenticQA report generation.

Usage:
    python -m agenticqa.report /path/to/repo1 /path/to/repo2
    python -m agenticqa.report /path/to/repo --output report.md
    python -m agenticqa.report /path/to/repo --format json --output report.json
    python -m agenticqa.report /path/to/repo --fail-on-critical
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

# Ensure src/ is importable when run from the project root
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent.parent))

from agenticqa.report.generator import ReportGenerator


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="agenticqa.report",
        description="Generate AgenticQA security scan reports for one or more repositories.",
    )
    parser.add_argument(
        "repos",
        nargs="+",
        help="Paths to repositories to scan",
    )
    parser.add_argument(
        "--output", "-o",
        help="Output file path (default: stdout)",
    )
    parser.add_argument(
        "--format", "-f",
        choices=["markdown", "json"],
        default="markdown",
        help="Output format (default: markdown)",
    )
    parser.add_argument(
        "--fail-on-critical",
        action="store_true",
        help="Exit 1 if any scanner finds critical issues",
    )
    args = parser.parse_args()

    # Validate paths
    for rp in args.repos:
        if not Path(rp).exists():
            print(f"Warning: {rp} does not exist", file=sys.stderr)

    gen = ReportGenerator()
    report = gen.scan_repos(args.repos)

    if args.format == "json":
        content = report.to_json()
    else:
        content = report.to_markdown()

    if args.output:
        Path(args.output).write_text(content, encoding="utf-8")
        print(f"Report written to {args.output}", file=sys.stderr)
    else:
        print(content)

    # Exit code
    if args.fail_on_critical:
        total_critical = sum(r.total_critical for r in report.repos)
        if total_critical > 0:
            print(
                f"\n{total_critical} critical finding(s) detected — exiting with code 1",
                file=sys.stderr,
            )
            sys.exit(1)


if __name__ == "__main__":
    main()
