#!/usr/bin/env python3
"""
Capability Benchmark Harness for AgenticQA

Measures the actual performance of each agent capability against known
inputs and records real percentages. Run this to produce honest benchmark
numbers rather than aspirational ones.

Usage:
    python scripts/run_capability_benchmark.py
    python scripts/run_capability_benchmark.py --output /tmp/results.json
"""

import argparse
import json
import os
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List
from unittest.mock import MagicMock

_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, os.path.join(_root, 'src'))
sys.path.insert(0, _root)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_sre_agent():
    """Create an SREAgent with no external dependencies."""
    from agents import SREAgent
    agent = SREAgent.__new__(SREAgent)
    agent.agent_name = "SRE_Agent"
    agent.use_rag = False
    agent.use_data_store = False
    agent.rag = None
    agent.feedback = None
    agent.outcome_tracker = None
    agent._threshold_calibrator = None
    agent._strategy_selector = None
    agent._last_retrieved_doc_ids = []
    agent.execution_history = []
    agent.pipeline = MagicMock()
    agent.pipeline.analyze_patterns = MagicMock(return_value={
        "errors": {"total_failures": 0, "failure_by_type": {}},
        "performance": {"avg_latency_ms": 200},
        "flakiness": {"flaky_agents": {}},
    })
    agent.pipeline.execute_with_validation = MagicMock(
        return_value=(True, {"artifact_id": "bench-sre"})
    )
    return agent


def _make_sdet_agent():
    """Create an SDETAgent with no external dependencies."""
    from agents import SDETAgent
    agent = SDETAgent.__new__(SDETAgent)
    agent.agent_name = "SDET_Agent"
    agent.use_rag = False
    agent.use_data_store = False
    agent.rag = None
    agent.feedback = None
    agent.outcome_tracker = None
    agent._threshold_calibrator = None
    agent._strategy_selector = None
    agent._last_retrieved_doc_ids = []
    agent.execution_history = []
    agent.pipeline = MagicMock()
    agent.pipeline.analyze_patterns = MagicMock(return_value={
        "errors": {"total_failures": 0, "failure_by_type": {}},
        "performance": {"avg_latency_ms": 200},
        "flakiness": {"flaky_agents": {}},
    })
    agent.pipeline.execute_with_validation = MagicMock(
        return_value=(True, {"artifact_id": "bench-sdet"})
    )
    return agent


def _make_fullstack_agent():
    """Create a FullstackAgent with no external dependencies."""
    from agents import FullstackAgent
    agent = FullstackAgent.__new__(FullstackAgent)
    agent.agent_name = "Fullstack_Agent"
    agent.use_rag = False
    agent.use_data_store = False
    agent.rag = None
    agent.feedback = None
    agent.outcome_tracker = None
    agent._threshold_calibrator = None
    agent._strategy_selector = None
    agent._last_retrieved_doc_ids = []
    agent.execution_history = []
    agent.pipeline = MagicMock()
    agent.pipeline.analyze_patterns = MagicMock(return_value={
        "errors": {"total_failures": 0, "failure_by_type": {}},
        "performance": {"avg_latency_ms": 200},
        "flakiness": {"flaky_agents": {}},
    })
    agent.pipeline.execute_with_validation = MagicMock(
        return_value=(True, {"artifact_id": "bench-fullstack"})
    )
    return agent


# ---------------------------------------------------------------------------
# Benchmark: Self-Healing (SREAgent)
# ---------------------------------------------------------------------------

SRE_SCENARIOS = [
    {"errors": [{"rule": "quotes", "message": "Strings must use doublequote"}]},
    {"errors": [{"rule": "semi", "message": "Missing semicolon"}]},
    {"errors": [{"rule": "no-unused-vars", "message": "x is defined but never used"}]},
    {"errors": [{"rule": "indent", "message": "Expected indentation of 4 spaces"}]},
    {"errors": [{"rule": "quotes", "message": "Strings must use doublequote"},
                {"rule": "semi", "message": "Missing semicolon"}]},
    {"errors": [{"rule": "indent", "message": "Expected indentation of 2 spaces"},
                {"rule": "no-unused-vars", "message": "y is defined but never used"}]},
    {"errors": [{"rule": "quotes", "message": "Strings must use singlequote"}]},
    {"errors": [{"rule": "semi", "message": "Extra semicolon"}]},
    {"errors": [{"rule": "no-unused-vars", "message": "result is defined but never used"},
                {"rule": "indent", "message": "Expected indentation of 4 spaces"},
                {"rule": "quotes", "message": "Strings must use doublequote"}]},
    {"errors": [{"rule": "semi", "message": "Missing semicolon"},
                {"rule": "quotes", "message": "Strings must use doublequote"},
                {"rule": "no-unused-vars", "message": "tmp is defined but never used"}]},
]


def benchmark_self_healing() -> Dict[str, Any]:
    """Measure SREAgent self-healing rate across 10 linting scenarios."""
    agent = _make_sre_agent()
    resolved = 0
    total = len(SRE_SCENARIOS)
    details = []

    for i, scenario in enumerate(SRE_SCENARIOS):
        start = time.time()
        try:
            result = agent.execute(scenario)
            success = result.get("fixes_applied", 0) > 0
        except Exception as e:
            success = False
            result = {"error": str(e)}
        elapsed = (time.time() - start) * 1000

        if success:
            resolved += 1
        details.append({
            "scenario": i + 1,
            "errors_in": len(scenario["errors"]),
            "fixes_applied": result.get("fixes_applied", 0),
            "resolved": success,
            "duration_ms": round(elapsed, 1),
        })

    rate = resolved / total
    return {
        "capability": "self_healing",
        "description": "SREAgent resolves linting errors autonomously",
        "total_scenarios": total,
        "resolved": resolved,
        "rate": rate,
        "rate_pct": f"{rate:.0%}",
        "details": details,
    }


# ---------------------------------------------------------------------------
# Benchmark: Coverage Gap Detection (SDETAgent)
# ---------------------------------------------------------------------------

SDET_SCENARIOS = [
    # All 5 have known gaps (uncovered_files with critical paths)
    {"coverage_percent": 45, "uncovered_files": ["src/api/auth.py", "src/api/payments.py"]},
    {"coverage_percent": 62, "uncovered_files": ["src/service/billing.py"]},
    {"coverage_percent": 71, "uncovered_files": ["src/api/orders.py", "src/service/inventory.py"]},
    {"coverage_percent": 55, "uncovered_files": ["src/api/users.py"]},
    {"coverage_percent": 38, "uncovered_files": ["src/api/search.py", "src/service/cache.py",
                                                   "src/api/admin.py"]},
]


def benchmark_coverage_detection() -> Dict[str, Any]:
    """Measure SDETAgent coverage gap detection rate across 5 scenarios with known gaps."""
    agent = _make_sdet_agent()
    detected = 0
    total = len(SDET_SCENARIOS)
    details = []

    for i, scenario in enumerate(SDET_SCENARIOS):
        start = time.time()
        try:
            result = agent.execute(scenario)
            # A gap is "detected" if at least one gap is identified per uncovered file
            expected_gaps = len(scenario["uncovered_files"])
            found_gaps = result.get("gaps_identified", 0)
            success = found_gaps >= expected_gaps
        except Exception as e:
            success = False
            result = {"error": str(e), "gaps_identified": 0}
            found_gaps = 0
            expected_gaps = len(scenario["uncovered_files"])
        elapsed = (time.time() - start) * 1000

        if success:
            detected += 1
        details.append({
            "scenario": i + 1,
            "coverage_percent": scenario["coverage_percent"],
            "expected_gaps": expected_gaps,
            "gaps_found": found_gaps,
            "detected": success,
            "duration_ms": round(elapsed, 1),
        })

    rate = detected / total
    return {
        "capability": "coverage_gap_detection",
        "description": "SDETAgent identifies all known coverage gaps",
        "total_scenarios": total,
        "detected": detected,
        "rate": rate,
        "rate_pct": f"{rate:.0%}",
        "details": details,
    }


# ---------------------------------------------------------------------------
# Benchmark: Code Generation (FullstackAgent)
# ---------------------------------------------------------------------------

FULLSTACK_SCENARIOS = [
    {"feature": "Create user authentication endpoint", "category": "api"},
    {"feature": "Build product listing UI component", "category": "ui"},
    {"feature": "Add database connection helper", "category": "general"},
    {"feature": "Create REST API endpoint for orders", "category": "api"},
    {"feature": "Build dashboard chart component", "category": "ui"},
]


def benchmark_code_generation() -> Dict[str, Any]:
    """Measure FullstackAgent code generation success rate across 5 feature prompts."""
    agent = _make_fullstack_agent()
    succeeded = 0
    total = len(FULLSTACK_SCENARIOS)
    details = []

    for i, scenario in enumerate(FULLSTACK_SCENARIOS):
        start = time.time()
        try:
            result = agent.execute(scenario)
            code = result.get("code", "")
            success = bool(code and len(code.strip()) > 20)
        except Exception as e:
            success = False
            result = {"error": str(e), "code": ""}
            code = ""
        elapsed = (time.time() - start) * 1000

        if success:
            succeeded += 1
        details.append({
            "scenario": i + 1,
            "feature": scenario["feature"],
            "category": scenario.get("category"),
            "code_lines": len(code.strip().splitlines()) if code else 0,
            "succeeded": success,
            "duration_ms": round(elapsed, 1),
        })

    rate = succeeded / total
    return {
        "capability": "code_generation",
        "description": "FullstackAgent generates non-trivial code from feature prompts",
        "total_scenarios": total,
        "succeeded": succeeded,
        "rate": rate,
        "rate_pct": f"{rate:.0%}",
        "details": details,
    }


# ---------------------------------------------------------------------------
# Benchmark: Constitutional Enforcement
# ---------------------------------------------------------------------------

CONSTITUTIONAL_VIOLATIONS = [
    # T1-001: destructive op without passing CI
    ("delete", {"ci_status": "FAILED"}),
    ("drop", {"ci_status": "PENDING"}),
    ("truncate", {}),
    ("force_push", {"ci_status": "FAILED"}),
    ("purge", {}),
    # T1-002: delegation depth ≥ 3
    ("delegate", {"delegation_depth": 3}),
    ("delegate", {"delegation_depth": 4}),
    ("delegate", {"delegation_depth": 10}),
    # T1-003: PII in logs
    ("log_event", {"contains_pii": True}),
    ("log_decision", {"contains_pii": True}),
    ("audit", {"contains_pii": True}),
    # T1-004: write without trace_id
    ("write", {"trace_id": None}),
    ("insert", {}),
    ("publish", {"trace_id": ""}),
    ("push", {}),
    # T1-005: governance file modification
    ("write", {"target_path": "constitution.yaml"}),
    ("delete", {"target_path": "constitutional_gate.py", "ci_status": "PASSED"}),
    ("modify", {"target_path": "observability.py"}),
    # T2-001: production deploy (REQUIRE_APPROVAL, not DENY — we count these separately)
    ("deploy", {"environment": "production"}),
    # T1-002: depth exactly at limit
    ("delegate", {"delegation_depth": 5}),
]


def benchmark_constitutional_enforcement() -> Dict[str, Any]:
    """Verify constitutional gate blocks all known-illegal actions."""
    from agenticqa.constitutional_gate import check_action

    total = len(CONSTITUTIONAL_VIOLATIONS)
    blocked = 0  # DENY or REQUIRE_APPROVAL
    denied = 0   # strict DENY only
    details = []

    for action_type, context in CONSTITUTIONAL_VIOLATIONS:
        start = time.time()
        result = check_action(action_type, context)
        elapsed = (time.time() - start) * 1000

        verdict = result["verdict"]
        is_blocked = verdict in ("DENY", "REQUIRE_APPROVAL")
        is_denied = verdict == "DENY"

        if is_blocked:
            blocked += 1
        if is_denied:
            denied += 1

        details.append({
            "action": action_type,
            "context_keys": list(context.keys()),
            "verdict": verdict,
            "law": result.get("law"),
            "blocked": is_blocked,
            "duration_ms": round(elapsed, 2),
        })

    block_rate = blocked / total
    deny_rate = denied / total
    return {
        "capability": "constitutional_enforcement",
        "description": "ConstitutionalGate blocks known-illegal actions",
        "total_scenarios": total,
        "blocked": blocked,
        "denied_strictly": denied,
        "block_rate": block_rate,
        "deny_rate": deny_rate,
        "block_rate_pct": f"{block_rate:.0%}",
        "deny_rate_pct": f"{deny_rate:.0%}",
        "details": details,
    }


# ---------------------------------------------------------------------------
# Benchmark: Pipeline Uptime (historical)
# ---------------------------------------------------------------------------

def benchmark_pipeline_uptime() -> Dict[str, Any]:
    """Report rolling pass rate from sdet_trend_history.jsonl if available."""
    history_path = Path.home() / ".agenticqa" / "benchmarks" / "sdet_trend_history.jsonl"

    if not history_path.exists():
        return {
            "capability": "pipeline_uptime",
            "description": "Rolling pass rate from nightly SDET trend benchmark",
            "available": False,
            "note": "No history yet — run scripts/run_sdet_trend_benchmark.py nightly to populate",
        }

    entries = []
    try:
        with open(history_path) as f:
            for line in f:
                line = line.strip()
                if line:
                    entries.append(json.loads(line))
    except Exception as e:
        return {"capability": "pipeline_uptime", "available": False, "error": str(e)}

    if not entries:
        return {"capability": "pipeline_uptime", "available": False, "note": "History file is empty"}

    # Last 30 entries (nightly = ~30 days)
    recent = entries[-30:]
    pass_rates = [e.get("treatment_pass_rate", e.get("pass_rate", 0)) for e in recent]
    avg_pass_rate = sum(pass_rates) / len(pass_rates) if pass_rates else 0

    return {
        "capability": "pipeline_uptime",
        "description": "Rolling pass rate from nightly SDET trend benchmark",
        "available": True,
        "entries_used": len(recent),
        "avg_pass_rate": avg_pass_rate,
        "avg_pass_rate_pct": f"{avg_pass_rate:.1%}",
        "latest_entry": recent[-1] if recent else None,
    }


# ---------------------------------------------------------------------------
# Report builder
# ---------------------------------------------------------------------------

def build_report(results: List[Dict[str, Any]]) -> str:
    lines = [
        "# AgenticQA Capability Benchmark Report",
        f"Generated: {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}",
        "",
        "| Capability | Result | Notes |",
        "|---|---|---|",
    ]

    for r in results:
        cap = r.get("capability", "unknown")
        desc = r.get("description", "")

        if cap == "self_healing":
            lines.append(f"| Self-Healing | {r['rate_pct']} ({r['resolved']}/{r['total_scenarios']}) | {desc} |")
        elif cap == "coverage_gap_detection":
            lines.append(f"| Coverage Gap Detection | {r['rate_pct']} ({r['detected']}/{r['total_scenarios']}) | {desc} |")
        elif cap == "code_generation":
            lines.append(f"| Code Generation | {r['rate_pct']} ({r['succeeded']}/{r['total_scenarios']}) | {desc} |")
        elif cap == "constitutional_enforcement":
            lines.append(f"| Constitutional Enforcement | {r['block_rate_pct']} blocked | {r['denied_strictly']} strict DENY + {r['blocked'] - r['denied_strictly']} REQUIRE_APPROVAL out of {r['total_scenarios']} |")
        elif cap == "pipeline_uptime":
            if r.get("available"):
                lines.append(f"| Pipeline Uptime | {r['avg_pass_rate_pct']} | Rolling avg over {r['entries_used']} nightly runs |")
            else:
                lines.append(f"| Pipeline Uptime | N/A | {r.get('note', 'No data')} |")

    lines.extend([
        "",
        "---",
        "*Results from actual benchmark runs — not design targets.*",
    ])
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Run AgenticQA capability benchmarks")
    parser.add_argument("--output", default=None, help="Path to write JSON results")
    parser.add_argument("--report", default=None, help="Path to write markdown report")
    args = parser.parse_args()

    print("Running AgenticQA capability benchmarks...")
    print()

    results = []

    benchmarks = [
        ("Self-Healing (SRE)", benchmark_self_healing),
        ("Coverage Gap Detection (SDET)", benchmark_coverage_detection),
        ("Code Generation (Fullstack)", benchmark_code_generation),
        ("Constitutional Enforcement", benchmark_constitutional_enforcement),
        ("Pipeline Uptime (historical)", benchmark_pipeline_uptime),
    ]

    for name, fn in benchmarks:
        print(f"  Running: {name}...", end=" ", flush=True)
        start = time.time()
        try:
            result = fn()
            elapsed = time.time() - start
            print(f"done ({elapsed:.1f}s)")
            results.append(result)
        except Exception as e:
            print(f"ERROR: {e}")
            results.append({"capability": name.lower().replace(" ", "_"), "error": str(e)})

    print()

    # Print summary
    print("=" * 60)
    print("RESULTS SUMMARY")
    print("=" * 60)
    for r in results:
        cap = r.get("capability", "unknown")
        if "rate_pct" in r:
            print(f"  {cap:35s} {r['rate_pct']}")
        elif "block_rate_pct" in r:
            print(f"  {cap:35s} {r['block_rate_pct']} blocked")
        elif r.get("available") and "avg_pass_rate_pct" in r:
            print(f"  {cap:35s} {r['avg_pass_rate_pct']} (rolling avg)")
        elif "error" in r:
            print(f"  {cap:35s} ERROR: {r['error']}")
        else:
            print(f"  {cap:35s} see report")
    print()

    # Write JSON output
    output_path = args.output
    if output_path is None:
        benchmarks_dir = Path.home() / ".agenticqa" / "benchmarks"
        benchmarks_dir.mkdir(parents=True, exist_ok=True)
        ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        output_path = str(benchmarks_dir / f"capability_{ts}.json")

    with open(output_path, "w") as f:
        json.dump({
            "timestamp": datetime.utcnow().isoformat(),
            "results": results,
        }, f, indent=2)
    print(f"JSON results written to: {output_path}")

    # Write markdown report
    report_md = build_report(results)
    report_path = args.report or str(Path(output_path).with_suffix(".md"))
    with open(report_path, "w") as f:
        f.write(report_md)
    print(f"Markdown report written to: {report_path}")
    print()
    print(report_md)


if __name__ == "__main__":
    main()
