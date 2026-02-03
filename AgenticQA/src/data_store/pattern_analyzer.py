"""Pattern analysis for compiled agent execution data"""

import json
from collections import defaultdict
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Any


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
            "analyzed_at": datetime.utcnow().isoformat(),
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
            "analyzed_at": datetime.utcnow().isoformat(),
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
        """Detect flaky tests/agents"""
        cutoff = datetime.utcnow() - timedelta(days=window_days)
        all_artifacts = self.store.search_artifacts()

        recent = [a for a in all_artifacts if datetime.fromisoformat(a["timestamp"]) > cutoff]

        agent_results = defaultdict(lambda: {"pass": 0, "fail": 0})

        for artifact_meta in recent:
            artifact = self.store.get_artifact(artifact_meta["artifact_id"])
            status = artifact.get("status", "unknown")
            source = artifact_meta["source"]

            if status == "success":
                agent_results[source]["pass"] += 1
            else:
                agent_results[source]["fail"] += 1

        flaky_agents = {}
        for agent, results in agent_results.items():
            total = results["pass"] + results["fail"]
            if total > 0:
                fail_rate = results["fail"] / total
                if 0.1 < fail_rate < 0.9:  # Flaky if 10-90% failure rate
                    flaky_agents[agent] = {
                        "fail_rate": fail_rate,
                        "pass": results["pass"],
                        "fail": results["fail"],
                    }

        pattern_data = {
            "analyzed_at": datetime.utcnow().isoformat(),
            "window_days": window_days,
            "flaky_agents": flaky_agents,
        }

        with open(self.patterns_dir / "flakiness.json", "w") as f:
            json.dump(pattern_data, f, indent=2)

        return pattern_data
