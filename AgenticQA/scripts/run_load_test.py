#!/usr/bin/env python3
"""AgenticQA Load Test Runner — Locust-based API stress testing.

Runs Locust programmatically in headless mode, collects per-endpoint
stats, persists results to JSONL, and checks for regressions against
the historical baseline.

Usage:
    python scripts/run_load_test.py
    python scripts/run_load_test.py --host http://localhost:8000 --users 50 --duration 60
    python scripts/run_load_test.py --scenarios health,agents --users 10 --duration 30
    python scripts/run_load_test.py --output /tmp/loadtest.json

Requires:  pip install agenticqa[loadtest]   (installs locust>=2.20.0)
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

# Ensure src/ is importable
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from agenticqa.loadtest.results import (
    EndpointStats,
    LoadTestResult,
    LoadTestAnalyzer,
)
from agenticqa.loadtest.scenarios import get_scenario_classes, _LOCUST_AVAILABLE


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="run_load_test",
        description="Run Locust load tests against the AgenticQA API.",
    )
    parser.add_argument(
        "--host",
        default="http://localhost:8000",
        help="Target API host (default: http://localhost:8000)",
    )
    parser.add_argument(
        "--users", "-u",
        type=int,
        default=20,
        help="Number of concurrent simulated users (default: 20)",
    )
    parser.add_argument(
        "--duration", "-d",
        type=int,
        default=60,
        help="Test duration in seconds (default: 60)",
    )
    parser.add_argument(
        "--spawn-rate", "-r",
        type=int,
        default=5,
        help="Users spawned per second (default: 5)",
    )
    parser.add_argument(
        "--scenarios", "-s",
        default="all",
        help="Comma-separated scenarios: health,agents,security,observability,mixed,ratelimit,all (default: all)",
    )
    parser.add_argument(
        "--output", "-o",
        help="JSON output path (default: ~/.agenticqa/benchmarks/loadtest_<timestamp>.json)",
    )
    return parser.parse_args()


def _collect_results(
    env,
    args: argparse.Namespace,
    elapsed_s: float,
) -> LoadTestResult:
    """Extract stats from a completed Locust Environment into a LoadTestResult."""
    total = env.runner.stats.total

    # Per-endpoint breakdown
    endpoints = []
    for entry in env.runner.stats.entries.values():
        percentiles = entry.get_response_time_percentile(0.5) or 0
        p95 = entry.get_response_time_percentile(0.95) or 0
        p99 = entry.get_response_time_percentile(0.99) or 0

        ep = EndpointStats(
            name=f"{entry.method} {entry.name}",
            method=entry.method or "GET",
            num_requests=entry.num_requests,
            num_failures=entry.num_failures,
            avg_response_time_ms=round(entry.avg_response_time, 1),
            min_response_time_ms=round(entry.min_response_time or 0, 1),
            max_response_time_ms=round(entry.max_response_time or 0, 1),
            p50_ms=round(percentiles, 1),
            p95_ms=round(p95, 1),
            p99_ms=round(p99, 1),
            requests_per_sec=round(entry.total_rps, 2),
        )
        endpoints.append(ep)

    # Sort by request count descending
    endpoints.sort(key=lambda e: e.num_requests, reverse=True)

    # Aggregate percentiles
    total_p50 = total.get_response_time_percentile(0.5) or 0
    total_p95 = total.get_response_time_percentile(0.95) or 0
    total_p99 = total.get_response_time_percentile(0.99) or 0

    return LoadTestResult(
        timestamp=datetime.now(timezone.utc).isoformat(),
        host=args.host,
        users=args.users,
        duration_s=args.duration,
        spawn_rate=args.spawn_rate,
        scenarios=args.scenarios.split(","),
        total_requests=total.num_requests,
        total_failures=total.num_failures,
        overall_rps=round(total.total_rps, 2),
        avg_response_time_ms=round(total.avg_response_time, 1),
        p50_ms=round(total_p50, 1),
        p95_ms=round(total_p95, 1),
        p99_ms=round(total_p99, 1),
        endpoints=endpoints,
    )


def _print_markdown_summary(result: LoadTestResult, regression: dict) -> None:
    """Print a markdown-formatted summary to stdout."""
    print("\n# AgenticQA Load Test Report")
    print(f"**Generated:** {result.timestamp}")
    print(f"**Host:** {result.host}")
    print(f"**Users:** {result.users} | **Duration:** {result.duration_s}s | **Spawn rate:** {result.spawn_rate}/s")
    print(f"**Scenarios:** {', '.join(result.scenarios)}")
    print()

    print("## Summary")
    print(f"- **Total Requests:** {result.total_requests:,}")
    print(f"- **Failures:** {result.total_failures:,} ({result.overall_failure_rate:.1%})")
    print(f"- **Throughput:** {result.overall_rps} req/s")
    print(f"- **Rate Limit Hits:** {result.rate_limit_hits}")
    print()

    print("## Latency Percentiles")
    print("| Metric | Value |")
    print("|--------|-------|")
    print(f"| Avg    | {result.avg_response_time_ms}ms |")
    print(f"| p50    | {result.p50_ms}ms |")
    print(f"| p95    | {result.p95_ms}ms |")
    print(f"| p99    | {result.p99_ms}ms |")
    print()

    if result.endpoints:
        print("## Per-Endpoint Breakdown")
        print("| Endpoint | Requests | Failures | Avg (ms) | p50 | p95 | p99 | RPS |")
        print("|----------|----------|----------|----------|-----|-----|-----|-----|")
        for ep in result.endpoints:
            print(
                f"| {ep.name} | {ep.num_requests} | {ep.num_failures} "
                f"| {ep.avg_response_time_ms} | {ep.p50_ms} | {ep.p95_ms} "
                f"| {ep.p99_ms} | {ep.requests_per_sec} |"
            )
        print()

    # Regression check
    status = "REGRESSION DETECTED" if regression["regression"] else "PASS"
    print(f"## Regression Check: {status}")
    print(f"- Baseline p95: {regression['baseline_p95_ms']}ms")
    print(f"- Current p95: {regression['current_p95_ms']}ms")
    print(f"- Threshold: {regression.get('threshold_multiplier', 2.0)}x")
    print()


def main() -> None:
    args = _parse_args()

    if not _LOCUST_AVAILABLE:
        print(
            "ERROR: Locust is not installed. Install with:\n"
            "  pip install locust>=2.20.0\n"
            "  # or: pip install agenticqa[loadtest]",
            file=sys.stderr,
        )
        sys.exit(1)

    # Lazy imports — only when Locust is available
    import gevent
    from locust.env import Environment

    # Resolve scenarios
    try:
        user_classes = get_scenario_classes(args.scenarios)
    except ValueError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        sys.exit(1)

    scenario_names = [cls.__name__ for cls in user_classes]
    print(f"Starting load test: {args.users} users, {args.duration}s, scenarios: {scenario_names}")
    print(f"Target: {args.host}")
    print()

    # Create Locust environment and run
    env = Environment(user_classes=user_classes, host=args.host)
    runner = env.create_local_runner()

    t0 = time.time()
    runner.start(args.users, spawn_rate=args.spawn_rate)
    gevent.spawn_later(args.duration, lambda: runner.quit())
    runner.greenlet.join()
    elapsed = time.time() - t0

    # Collect results
    result = _collect_results(env, args, elapsed)

    # Persist and check regression
    analyzer = LoadTestAnalyzer()
    regression = analyzer.detect_regression(result)
    analyzer.record(result)

    # Output
    _print_markdown_summary(result, regression)

    # Write JSON
    output_path = args.output
    if not output_path:
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_dir = Path.home() / ".agenticqa" / "benchmarks"
        output_dir.mkdir(parents=True, exist_ok=True)
        output_path = str(output_dir / f"loadtest_{ts}.json")

    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    Path(output_path).write_text(
        json.dumps(result.to_dict(), indent=2), encoding="utf-8"
    )
    print(f"Results written to {output_path}", file=sys.stderr)

    # Exit code
    if regression["regression"]:
        print(
            "\nREGRESSION: p95 latency exceeds 2x baseline — exiting with code 1",
            file=sys.stderr,
        )
        sys.exit(1)


if __name__ == "__main__":
    main()
