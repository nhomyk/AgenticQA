"""Reliability and evidence helpers for control-plane endpoints."""

from __future__ import annotations

import json
import socket
from pathlib import Path
from typing import Any, Dict, Optional


def check_tcp(host: str, port: int, timeout: float = 0.6) -> bool:
    """Return True when a TCP service is reachable."""
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except Exception:
        return False


def read_latest_jsonl(path: Path) -> Optional[Dict[str, Any]]:
    """Read last valid JSON object from a JSONL file."""
    if not path.exists():
        return None
    latest: Optional[Dict[str, Any]] = None
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line:
            continue
        try:
            latest = json.loads(line)
        except json.JSONDecodeError:
            continue
    return latest


def build_evidence_summary(
    metrics: Dict[str, Any],
    latest_benchmark: Optional[Dict[str, Any]],
    trace_count: int,
) -> Dict[str, Any]:
    """Convert raw system metrics into client-facing evidence summary."""
    workflow_pass_rate = float(metrics.get("pass_rate") or 0.0)
    mttr = metrics.get("mttr_minutes")

    benchmark_uplift = None
    baseline_pass_rate = None
    treatment_pass_rate = None

    if latest_benchmark:
        benchmark_uplift = latest_benchmark.get("pass_rate_uplift")
        baseline_pass_rate = ((latest_benchmark.get("baseline_no_autofix") or {}).get("pass_rate"))
        treatment_pass_rate = ((latest_benchmark.get("treatment_autofix") or {}).get("pass_rate"))

    claims = {
        "workflow_execution_reliability": {
            "metric": "pass_rate",
            "value": workflow_pass_rate,
            "status": "strong" if workflow_pass_rate >= 0.8 else "watch",
        },
        "incident_recovery_speed": {
            "metric": "mttr_minutes",
            "value": mttr,
            "status": "strong" if (isinstance(mttr, (int, float)) and mttr <= 15) else "watch",
        },
        "sdet_autofix_effectiveness": {
            "metric": "pass_rate_uplift",
            "value": benchmark_uplift,
            "baseline": baseline_pass_rate,
            "treatment": treatment_pass_rate,
            "status": "strong" if (isinstance(benchmark_uplift, (int, float)) and benchmark_uplift > 0) else "watch",
        },
        "observability_coverage": {
            "metric": "trace_count",
            "value": trace_count,
            "status": "strong" if trace_count > 0 else "watch",
        },
    }

    return {
        "claims": claims,
        "inputs": {
            "metrics": metrics,
            "latest_benchmark": latest_benchmark,
            "trace_count": trace_count,
        },
    }
