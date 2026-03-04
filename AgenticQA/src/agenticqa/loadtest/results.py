"""Load test result data structures and JSONL-based trend analysis.

No external dependencies — Locust is only needed to *run* tests, not to
analyse or persist results.  Follows the same patterns as
``ScanTrendAggregator`` (scan_trend.py) and ``LearningMetricsSnapshot``.

Storage: ``~/.agenticqa/loadtest_history.jsonl`` (one JSON object per line).
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional


_HISTORY_DIR = Path(os.path.expanduser("~/.agenticqa"))
_LOADTEST_HISTORY_FILE = _HISTORY_DIR / "loadtest_history.jsonl"


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

@dataclass
class EndpointStats:
    """Per-endpoint latency and throughput statistics."""

    name: str                        # e.g. "GET /health"
    method: str                      # "GET" | "POST"
    num_requests: int = 0
    num_failures: int = 0
    avg_response_time_ms: float = 0.0
    min_response_time_ms: float = 0.0
    max_response_time_ms: float = 0.0
    p50_ms: float = 0.0
    p95_ms: float = 0.0
    p99_ms: float = 0.0
    requests_per_sec: float = 0.0

    @property
    def failure_rate(self) -> float:
        if self.num_requests == 0:
            return 0.0
        return round(self.num_failures / self.num_requests, 4)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "method": self.method,
            "num_requests": self.num_requests,
            "num_failures": self.num_failures,
            "avg_response_time_ms": self.avg_response_time_ms,
            "min_response_time_ms": self.min_response_time_ms,
            "max_response_time_ms": self.max_response_time_ms,
            "p50_ms": self.p50_ms,
            "p95_ms": self.p95_ms,
            "p99_ms": self.p99_ms,
            "requests_per_sec": self.requests_per_sec,
            "failure_rate": self.failure_rate,
        }


@dataclass
class LoadTestResult:
    """Complete result from a single load test run."""

    timestamp: str
    host: str
    users: int
    duration_s: int
    spawn_rate: int = 5
    scenarios: List[str] = field(default_factory=list)

    # Aggregate stats
    total_requests: int = 0
    total_failures: int = 0
    overall_rps: float = 0.0
    avg_response_time_ms: float = 0.0
    p50_ms: float = 0.0
    p95_ms: float = 0.0
    p99_ms: float = 0.0

    # Per-endpoint breakdown
    endpoints: List[EndpointStats] = field(default_factory=list)

    # Rate limiter tracking
    rate_limit_hits: int = 0

    @property
    def overall_failure_rate(self) -> float:
        if self.total_requests == 0:
            return 0.0
        return round(self.total_failures / self.total_requests, 4)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "timestamp": self.timestamp,
            "host": self.host,
            "users": self.users,
            "duration_s": self.duration_s,
            "spawn_rate": self.spawn_rate,
            "scenarios": self.scenarios,
            "total_requests": self.total_requests,
            "total_failures": self.total_failures,
            "overall_rps": self.overall_rps,
            "overall_failure_rate": self.overall_failure_rate,
            "avg_response_time_ms": self.avg_response_time_ms,
            "p50_ms": self.p50_ms,
            "p95_ms": self.p95_ms,
            "p99_ms": self.p99_ms,
            "rate_limit_hits": self.rate_limit_hits,
            "endpoints": [e.to_dict() for e in self.endpoints],
        }


# ---------------------------------------------------------------------------
# Analyzer — JSONL persistence + trend detection
# ---------------------------------------------------------------------------

class LoadTestAnalyzer:
    """Persist load test results and detect performance regressions.

    Mirrors ``ScanTrendAggregator`` — append-only JSONL, split-half trend
    detection, and a 2× regression threshold matching ``PerformanceAgent``.
    """

    def __init__(self, history_file: Optional[str] = None):
        self._file = Path(history_file) if history_file else _LOADTEST_HISTORY_FILE

    # ── Write ──────────────────────────────────────────────────────────

    def record(self, result: LoadTestResult) -> None:
        """Append a load test result to JSONL history."""
        try:
            self._file.parent.mkdir(parents=True, exist_ok=True)
            with open(self._file, "a") as f:
                f.write(json.dumps(result.to_dict()) + "\n")
        except OSError:
            pass

    # ── Read ───────────────────────────────────────────────────────────

    def history(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Load recent load test history."""
        if not self._file.exists():
            return []

        records: List[Dict[str, Any]] = []
        try:
            with open(self._file) as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        records.append(json.loads(line))
                    except json.JSONDecodeError:
                        continue
        except OSError:
            return []

        return records[-limit:]

    # ── Trend detection ────────────────────────────────────────────────

    def trend(self, window: int = 10) -> Dict[str, Any]:
        """Calculate trend direction from recent p95 latency.

        Splits history into early/recent halves and compares averages.
        Returns ``improving``, ``stable``, or ``degrading``.
        """
        records = self.history(limit=window * 2)
        if len(records) < 2:
            return {
                "direction": "insufficient_data",
                "records": len(records),
                "current_p95_ms": records[-1]["p95_ms"] if records else 0,
            }

        mid = len(records) // 2
        early = records[:mid]
        recent = records[mid:]

        early_p95 = sum(r.get("p95_ms", 0) for r in early) / len(early)
        recent_p95 = sum(r.get("p95_ms", 0) for r in recent) / len(recent)

        early_rps = sum(r.get("overall_rps", 0) for r in early) / len(early)
        recent_rps = sum(r.get("overall_rps", 0) for r in recent) / len(recent)

        # 10% change threshold (same formula as ScanTrendAggregator)
        delta = recent_p95 - early_p95
        threshold = max(1.0, early_p95 * 0.1)

        if delta > threshold:
            direction = "degrading"
        elif delta < -threshold:
            direction = "improving"
        else:
            direction = "stable"

        return {
            "direction": direction,
            "records": len(records),
            "early_avg_p95_ms": round(early_p95, 1),
            "recent_avg_p95_ms": round(recent_p95, 1),
            "early_avg_rps": round(early_rps, 1),
            "recent_avg_rps": round(recent_rps, 1),
            "delta_p95_ms": round(delta, 1),
            "current_p95_ms": records[-1].get("p95_ms", 0),
            "current_rps": records[-1].get("overall_rps", 0),
        }

    # ── Regression detection ──────────────────────────────────────────

    def detect_regression(
        self,
        result: LoadTestResult,
        threshold: float = 2.0,
    ) -> Dict[str, Any]:
        """Check if *result* is a regression vs the historical baseline.

        Uses the same 2× multiplier as ``PerformanceAgent`` (agents.py:1098).
        Baseline is the average p95 from the last 5 recorded runs.
        """
        records = self.history(limit=5)
        if not records:
            return {
                "regression": False,
                "reason": "no_baseline",
                "baseline_p95_ms": 0,
                "current_p95_ms": result.p95_ms,
            }

        baseline_p95 = sum(r.get("p95_ms", 0) for r in records) / len(records)
        is_regression = baseline_p95 > 0 and result.p95_ms > baseline_p95 * threshold

        return {
            "regression": is_regression,
            "reason": "p95_exceeds_2x_baseline" if is_regression else "within_threshold",
            "baseline_p95_ms": round(baseline_p95, 1),
            "current_p95_ms": result.p95_ms,
            "threshold_multiplier": threshold,
        }
