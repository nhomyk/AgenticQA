"""Pattern analysis for compiled agent execution data"""

import json
from collections import defaultdict
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Dict, List, Any, Optional


class PatternAnalyzer:
    """Analyze patterns in compiled agent execution data"""

    def __init__(self, artifact_store):
        self.store = artifact_store
        self.patterns_dir = artifact_store.patterns_dir

    def analyze_failure_patterns(self) -> Dict[str, Any]:
        """Identify recurring failure patterns"""
        failures = self.store.search_artifacts(artifact_type="error")

        failure_map = defaultdict(int)
        error_types = defaultdict(list)

        for artifact_meta in failures:
            artifact = self.store.get_artifact(artifact_meta["artifact_id"])
            error_type = artifact.get("error_type", "unknown")
            failure_map[error_type] += 1
            error_types[error_type].append(
                {
                    "timestamp": artifact_meta["timestamp"],
                    "message": artifact.get("message"),
                    "agent": artifact_meta.get("source"),
                }
            )

        pattern_data = {
            "analyzed_at": datetime.now(timezone.utc).isoformat(),
            "total_failures": len(failures),
            "failure_by_type": dict(failure_map),
            "error_details": dict(error_types),
        }

        with open(self.patterns_dir / "error-patterns.json", "w") as f:
            json.dump(pattern_data, f, indent=2)

        return pattern_data

    def analyze_performance_patterns(self) -> Dict[str, Any]:
        """Identify performance trends"""
        executions = self.store.search_artifacts(artifact_type="execution")

        latencies = []
        agent_performance = defaultdict(list)

        for artifact_meta in executions:
            artifact = self.store.get_artifact(artifact_meta["artifact_id"])
            duration = artifact.get("duration_ms", 0)
            latencies.append(duration)
            agent_performance[artifact_meta["source"]].append(duration)

        pattern_data = {
            "analyzed_at": datetime.now(timezone.utc).isoformat(),
            "total_executions": len(executions),
            "avg_latency_ms": sum(latencies) / len(latencies) if latencies else 0,
            "p95_latency_ms": (sorted(latencies)[int(len(latencies) * 0.95)] if latencies else 0),
            "agent_performance": {
                agent: {"avg_ms": sum(times) / len(times), "executions": len(times)}
                for agent, times in agent_performance.items()
            },
        }

        with open(self.patterns_dir / "performance.json", "w") as f:
            json.dump(pattern_data, f, indent=2)

        return pattern_data

    def analyze_flakiness(self, window_days: int = 7) -> Dict[str, Any]:
        """Detect flaky agents with EWMA trend (accelerating/stable/recovering)."""
        cutoff = datetime.now(timezone.utc) - timedelta(days=window_days)
        all_artifacts = self.store.search_artifacts()

        recent = []
        for artifact_meta in all_artifacts:
            ts = self._parse_timestamp_utc(artifact_meta.get("timestamp"))
            if ts and ts > cutoff:
                recent.append(artifact_meta)

        agent_results = defaultdict(lambda: {"pass": 0, "fail": 0})
        # (agent, YYYY-MM-DD) → pass/fail counts for EWMA
        agent_daily: Dict[str, Dict[str, Dict[str, int]]] = defaultdict(lambda: defaultdict(lambda: {"pass": 0, "fail": 0}))

        for artifact_meta in recent:
            artifact = self.store.get_artifact(artifact_meta["artifact_id"])
            status = artifact.get("status", "unknown")
            source = artifact_meta["source"]
            day = artifact_meta["timestamp"][:10]

            if status == "success":
                agent_results[source]["pass"] += 1
                agent_daily[source][day]["pass"] += 1
            else:
                agent_results[source]["fail"] += 1
                agent_daily[source][day]["fail"] += 1

        flaky_agents = {}
        for agent, results in agent_results.items():
            total = results["pass"] + results["fail"]
            if total > 0:
                fail_rate = results["fail"] / total
                if 0.1 < fail_rate < 0.9:  # Flaky if 10-90% failure rate
                    daily = agent_daily[agent]
                    sorted_days = sorted(daily.keys())
                    daily_rates = [
                        daily[d]["fail"] / max(daily[d]["pass"] + daily[d]["fail"], 1)
                        for d in sorted_days
                    ]
                    ewma = self._compute_ewma(daily_rates)
                    last_rate = daily_rates[-1] if daily_rates else fail_rate
                    if last_rate > ewma * 1.1:
                        trend = "accelerating"
                    elif last_rate < ewma * 0.9:
                        trend = "recovering"
                    else:
                        trend = "stable"

                    flaky_agents[agent] = {
                        "fail_rate": fail_rate,
                        "pass": results["pass"],
                        "fail": results["fail"],
                        "ewma_fail_rate": ewma,
                        "trend": trend,
                    }

        pattern_data = {
            "analyzed_at": datetime.now(timezone.utc).isoformat(),
            "window_days": window_days,
            "flaky_agents": flaky_agents,
        }

        with open(self.patterns_dir / "flakiness.json", "w") as f:
            json.dump(pattern_data, f, indent=2)

        return pattern_data

    @staticmethod
    def _parse_timestamp_utc(value: Any) -> Optional[datetime]:
        """Parse ISO timestamp and normalize it to timezone-aware UTC."""
        if not value:
            return None
        try:
            ts = datetime.fromisoformat(str(value))
        except Exception:
            return None

        if ts.tzinfo is None:
            return ts.replace(tzinfo=timezone.utc)
        return ts.astimezone(timezone.utc)

    @staticmethod
    def _compute_ewma(daily_rates: List[float], alpha: float = 0.3) -> float:
        """Exponentially weighted moving average over daily fail rates."""
        if not daily_rates:
            return 0.0
        ewma = daily_rates[0]
        for rate in daily_rates[1:]:
            ewma = alpha * rate + (1 - alpha) * ewma
        return round(ewma, 4)

    def get_error_signatures(self, agent_name: str, window_days: int = 14) -> List[Dict[str, Any]]:
        """Return top recurring error signatures for an agent, ranked by frequency.

        Each signature is ``error_type:location_hint`` — a stable fingerprint that
        survives message-text variation and is safe to store in execution strategy.
        """
        cutoff = datetime.now(timezone.utc) - timedelta(days=window_days)
        failures = self.store.search_artifacts(artifact_type="error")

        sig_counts: Dict[str, Dict[str, Any]] = defaultdict(lambda: {"count": 0, "last_seen": None})

        for meta in failures:
            if meta.get("source") != agent_name:
                continue
            ts = self._parse_timestamp_utc(meta.get("timestamp"))
            if not ts:
                continue
            if ts < cutoff:
                continue

            artifact = self.store.get_artifact(meta["artifact_id"])
            error_type = str(artifact.get("error_type") or "UNKNOWN")
            message = str(artifact.get("message") or "")
            location_hint = self._extract_location_hint(message)
            signature = f"{error_type}:{location_hint}"

            entry = sig_counts[signature]
            entry["count"] += 1
            ts_str = meta["timestamp"]
            if entry["last_seen"] is None or ts_str > entry["last_seen"]:
                entry["last_seen"] = ts_str

        results = [
            {"signature": sig, "count": data["count"], "last_seen": data["last_seen"]}
            for sig, data in sig_counts.items()
        ]
        return sorted(results, key=lambda r: r["count"], reverse=True)[:10]

    @staticmethod
    def _extract_location_hint(message: str) -> str:
        """Extract a short stable location hint from an error message."""
        if not message:
            return "unknown"
        for word in message.split():
            clean = word.strip(".,;:()[]\"'")
            if "." in clean and len(clean) > 3:
                return clean[:40]
        return message[:40].strip() or "unknown"

    def sync_delegation_outcomes(self) -> Dict[str, Any]:
        """Read delegation outcomes from outcomes.db and merge into performance.json.

        Bridges the gap between OutcomeTracker (write path) and PatternAnalyzer
        (read path) so that real delegation success rates flow into the pattern
        files that agents consult during strategy selection.
        """
        import sqlite3

        outcomes_db = Path.home() / ".agenticqa" / "outcomes.db"
        if not outcomes_db.exists():
            return {"synced_pairs": 0, "skipped": "outcomes.db not found"}

        try:
            conn = sqlite3.connect(str(outcomes_db))
            cur = conn.cursor()
            cur.execute("""
                SELECT from_agent, to_agent,
                       COUNT(*) as total,
                       AVG(actual_success) as success_rate,
                       AVG(duration_ms) as avg_ms,
                       MAX(timestamp) as last_seen
                FROM delegation_outcomes
                WHERE actual_success IS NOT NULL
                GROUP BY from_agent, to_agent
                ORDER BY total DESC
            """)
            rows = [
                dict(zip(["from_agent", "to_agent", "total", "success_rate", "avg_ms", "last_seen"], r))
                for r in cur.fetchall()
            ]
            conn.close()
        except Exception as e:
            return {"synced_pairs": 0, "error": str(e)}

        perf_file = self.patterns_dir / "performance.json"
        perf_data: Dict[str, Any] = {}
        if perf_file.exists():
            try:
                with open(perf_file) as f:
                    perf_data = json.load(f)
            except Exception:
                pass

        perf_data["delegation_stats"] = rows
        perf_data["delegation_synced_at"] = datetime.now(timezone.utc).isoformat()

        with open(perf_file, "w") as f:
            json.dump(perf_data, f, indent=2)

        return {"synced_pairs": len(rows)}

    def get_agent_failure_rate(self, agent_name: str, window_days: int = 7) -> float:
        """Get failure rate for a specific agent over the given window."""
        flakiness = self.analyze_flakiness(window_days)
        flaky_agents = flakiness.get("flaky_agents", {})
        if agent_name in flaky_agents:
            return flaky_agents[agent_name]["fail_rate"]
        return 0.0
