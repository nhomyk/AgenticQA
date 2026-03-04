"""Locust load test scenarios for AgenticQA API endpoints.

Each ``HttpUser`` subclass represents a user persona — health checks,
agent execution, security scans, observability queries, and a realistic
mixed-workload scenario.

**Graceful fallback:** When Locust is not installed the module still
imports cleanly (stub base classes are defined) so that tests and the
``get_scenario_classes()`` helper work without the optional dependency.

Usage (via Locust CLI):
    locust -f src/agenticqa/loadtest/scenarios.py --host http://localhost:8000

Usage (programmatic — see scripts/run_load_test.py):
    from agenticqa.loadtest.scenarios import get_scenario_classes
    classes = get_scenario_classes("health,agents")
"""
from __future__ import annotations

from typing import Dict, List, Type

# ---------------------------------------------------------------------------
# Graceful fallback when Locust is not installed
# ---------------------------------------------------------------------------

_LOCUST_AVAILABLE = False

try:
    from locust import HttpUser, task, between, constant

    _LOCUST_AVAILABLE = True
except ImportError:

    class HttpUser:  # type: ignore[no-redef]
        """Stub for when Locust is not installed."""

        wait_time = None
        host = ""
        abstract = True

    def task(weight=1):  # type: ignore[no-redef]
        """Stub decorator."""
        def decorator(fn):
            fn._locust_task_weight = weight
            return fn
        return decorator

    def between(a, b):  # type: ignore[no-redef]
        return (a, b)

    def constant(val):  # type: ignore[no-redef]
        return val


# ---------------------------------------------------------------------------
# Scenario 1 — Health checks (lightweight, high-frequency)
# ---------------------------------------------------------------------------

class HealthCheckUser(HttpUser):
    """Simulates monitoring / readiness probes under load."""

    wait_time = between(0.5, 1.5)

    @task(3)
    def health(self):
        self.client.get("/health")

    @task(1)
    def system_readiness(self):
        self.client.get("/api/system/readiness")

    @task(1)
    def dataflow_health(self):
        self.client.get("/api/health/dataflow")


# ---------------------------------------------------------------------------
# Scenario 2 — Agent execution (core product path)
# ---------------------------------------------------------------------------

class AgentExecutionUser(HttpUser):
    """Simulates data scientists triggering agent runs."""

    wait_time = between(1, 3)

    @task(2)
    def execute_agents(self):
        self.client.post("/api/agents/execute", json={
            "test_results": {"total": 10, "passed": 9, "failed": 1},
            "execution_data": {"duration_ms": 1200, "memory_mb": 256},
            "compliance_data": {"violations": 0},
            "deployment_config": {"target": "staging"},
        })

    @task(1)
    def get_insights(self):
        self.client.get("/api/agents/insights")

    @task(1)
    def get_patterns(self):
        self.client.get("/api/datastore/patterns")


# ---------------------------------------------------------------------------
# Scenario 3 — Security scanning endpoints
# ---------------------------------------------------------------------------

class SecurityScanUser(HttpUser):
    """Simulates security-focused API usage."""

    wait_time = between(2, 5)

    @task(2)
    def injection_scan(self):
        self.client.post("/api/security/injection-scan", json={
            "text": "Please summarize the document about quarterly results."
        })

    @task(1)
    def bias_scan(self):
        self.client.post("/api/security/bias-scan", json={
            "text": "The system recommends hiring candidates from top universities."
        })

    @task(1)
    def architecture_scan(self):
        self.client.get("/api/security/architecture-scan", params={"repo_path": "."})


# ---------------------------------------------------------------------------
# Scenario 4 — Observability / trend queries
# ---------------------------------------------------------------------------

class ObservabilityUser(HttpUser):
    """Simulates dashboard reads and trend queries."""

    wait_time = between(1, 3)

    @task(2)
    def list_traces(self):
        self.client.get("/api/observability/traces", params={"limit": 10})

    @task(1)
    def scan_trend_history(self):
        self.client.get("/api/scan-trend/history", params={"limit": 20})

    @task(1)
    def scan_trend_direction(self):
        self.client.get("/api/scan-trend/trend")

    @task(1)
    def learning_metrics(self):
        self.client.get("/api/learning-metrics", params={"limit": 10})


# ---------------------------------------------------------------------------
# Scenario 5 — Realistic mixed workload
# ---------------------------------------------------------------------------

class ConcurrentMixUser(HttpUser):
    """Simulates a realistic mix of API operations."""

    wait_time = between(0.5, 2)

    @task(5)
    def health(self):
        self.client.get("/health")

    @task(3)
    def datastore_stats(self):
        self.client.get("/api/datastore/stats")

    @task(2)
    def execute_agents(self):
        self.client.post("/api/agents/execute", json={
            "test_results": {"total": 5, "passed": 5, "failed": 0},
            "execution_data": {"duration_ms": 800, "memory_mb": 128},
        })

    @task(1)
    def constitution_check(self):
        self.client.post("/api/system/constitution/check", json={
            "action_type": "deploy",
            "context": {"environment": "staging", "ci_status": "PASSED"},
        })

    @task(1)
    def red_team_scan(self):
        self.client.post("/api/red-team/scan", json={
            "mode": "fast",
            "target": "scanner",
            "auto_patch": False,
        })


# ---------------------------------------------------------------------------
# Scenario 6 — Rate limiter probe
# ---------------------------------------------------------------------------

class RateLimitProbeUser(HttpUser):
    """Fires rapid requests to verify rate limiter behaviour.

    Expects 429 responses once the limit (default 60 rpm) is exceeded.
    429s are recorded as *successes* to avoid inflating failure stats.
    """

    wait_time = constant(0.1)  # ~10 req/s per user

    @task
    def rapid_health(self):
        if _LOCUST_AVAILABLE:
            with self.client.get("/health", catch_response=True) as response:
                if response.status_code == 429:
                    response.success()
        else:
            pass  # stub — no client available


# ---------------------------------------------------------------------------
# Scenario registry
# ---------------------------------------------------------------------------

_SCENARIO_MAP: Dict[str, Type[HttpUser]] = {
    "health": HealthCheckUser,
    "agents": AgentExecutionUser,
    "security": SecurityScanUser,
    "observability": ObservabilityUser,
    "mixed": ConcurrentMixUser,
    "ratelimit": RateLimitProbeUser,
}


def get_scenario_classes(names: str = "all") -> List[Type[HttpUser]]:
    """Return Locust user classes for the given comma-separated scenario names.

    Args:
        names: ``"all"`` or a comma-separated string like ``"health,agents"``.

    Returns:
        List of ``HttpUser`` subclasses.

    Raises:
        ValueError: If an unknown scenario name is provided.
    """
    if names.strip().lower() == "all":
        return list(_SCENARIO_MAP.values())

    classes: List[Type[HttpUser]] = []
    for name in names.split(","):
        name = name.strip().lower()
        if name not in _SCENARIO_MAP:
            valid = ", ".join(sorted(_SCENARIO_MAP.keys()))
            raise ValueError(f"Unknown scenario '{name}'. Valid: {valid}")
        classes.append(_SCENARIO_MAP[name])
    return classes
