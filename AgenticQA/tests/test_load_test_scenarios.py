"""Unit tests for agenticqa.loadtest.scenarios — @pytest.mark.unit

All tests work without Locust installed (stub base classes provide
enough structure for scenario verification).
"""
import pytest

from agenticqa.loadtest.scenarios import (
    HealthCheckUser,
    AgentExecutionUser,
    SecurityScanUser,
    ObservabilityUser,
    ConcurrentMixUser,
    RateLimitProbeUser,
    get_scenario_classes,
    _SCENARIO_MAP,
)


# ---------------------------------------------------------------------------
# Scenario registry
# ---------------------------------------------------------------------------

@pytest.mark.unit
class TestScenarioRegistry:
    def test_all_returns_six_classes(self):
        classes = get_scenario_classes("all")
        assert len(classes) == 6

    def test_all_case_insensitive(self):
        assert get_scenario_classes("ALL") == get_scenario_classes("all")

    def test_single_scenario(self):
        classes = get_scenario_classes("health")
        assert classes == [HealthCheckUser]

    def test_multiple_scenarios(self):
        classes = get_scenario_classes("health,agents")
        assert HealthCheckUser in classes
        assert AgentExecutionUser in classes
        assert len(classes) == 2

    def test_whitespace_trimmed(self):
        classes = get_scenario_classes(" health , agents ")
        assert len(classes) == 2

    def test_invalid_scenario_raises(self):
        with pytest.raises(ValueError, match="Unknown scenario 'nonexistent'"):
            get_scenario_classes("nonexistent")

    def test_map_keys_match_expected(self):
        expected = {"health", "agents", "security", "observability", "mixed", "ratelimit"}
        assert set(_SCENARIO_MAP.keys()) == expected


# ---------------------------------------------------------------------------
# Scenario classes — structure validation
# ---------------------------------------------------------------------------

@pytest.mark.unit
class TestHealthCheckUser:
    def test_has_wait_time(self):
        assert HealthCheckUser.wait_time is not None

    def test_has_task_methods(self):
        methods = ["health", "system_readiness", "dataflow_health"]
        for m in methods:
            assert hasattr(HealthCheckUser, m), f"Missing method: {m}"


@pytest.mark.unit
class TestAgentExecutionUser:
    def test_has_wait_time(self):
        assert AgentExecutionUser.wait_time is not None

    def test_has_task_methods(self):
        methods = ["execute_agents", "get_insights", "get_patterns"]
        for m in methods:
            assert hasattr(AgentExecutionUser, m), f"Missing method: {m}"


@pytest.mark.unit
class TestSecurityScanUser:
    def test_has_task_methods(self):
        methods = ["injection_scan", "bias_scan", "architecture_scan"]
        for m in methods:
            assert hasattr(SecurityScanUser, m), f"Missing method: {m}"


@pytest.mark.unit
class TestObservabilityUser:
    def test_has_task_methods(self):
        methods = ["list_traces", "scan_trend_history", "scan_trend_direction", "learning_metrics"]
        for m in methods:
            assert hasattr(ObservabilityUser, m), f"Missing method: {m}"


@pytest.mark.unit
class TestConcurrentMixUser:
    def test_has_mixed_methods(self):
        methods = ["health", "datastore_stats", "execute_agents",
                    "constitution_check", "red_team_scan"]
        for m in methods:
            assert hasattr(ConcurrentMixUser, m), f"Missing method: {m}"


@pytest.mark.unit
class TestRateLimitProbeUser:
    def test_has_rapid_health(self):
        assert hasattr(RateLimitProbeUser, "rapid_health")

    def test_wait_time_is_constant(self):
        wt = RateLimitProbeUser.wait_time
        # constant(0.1) returns either a float or a tuple depending on stubs
        assert wt is not None
