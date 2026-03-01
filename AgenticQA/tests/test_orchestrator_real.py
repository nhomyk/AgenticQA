"""
Orchestrator Integration Tests — all 8 agents execute together with real data.

No mocking of agent.execute(). The orchestrator dispatches real input to real
agents and gets real output. Only Weaviate/Neo4j are absent (RAG returns empty,
which is fine — agents degrade gracefully).

Verifies:
  - All 8 agents return results (no crashes)
  - Each agent's result has the expected keys
  - execute_all_agents() aggregates correctly
  - _route maps request fields to the correct agent
  - get_agent_insights() works after execution
"""
import pytest
from agents import AgentOrchestrator


@pytest.fixture
def orchestrator():
    return AgentOrchestrator()


@pytest.fixture
def full_data():
    """Realistic orchestration payload with data for all 8 agents."""
    return {
        "test_results": {
            "total": 100, "passed": 95, "failed": 5,
            "coverage": 85, "test_type": "unit",
        },
        "execution_data": {
            "duration_ms": 1200, "baseline_ms": 1000,
            "memory_mb": 512, "operation": "api_call",
        },
        "compliance_data": {
            "encrypted": True, "pii_masked": True,
            "audit_enabled": True, "context": "database, user data",
        },
        "deployment_config": {
            "version": "v2.1.0", "environment": "staging",
        },
        "linting_data": {
            "file_path": "app.py",
            "errors": [
                {"rule": "E301", "message": "expected 2 blank lines", "line": 10, "file": "app.py"},
            ],
        },
        "coverage_data": {
            "coverage_percent": 78,
            "uncovered_files": ["utils/helpers.py"],
            "test_type": "unit",
        },
        "feature_request": {
            "title": "Add health check endpoint",
            "category": "api",
            "description": "Create GET /health that returns 200",
        },
        "red_team_config": {
            "mode": "fast", "target": "both", "auto_patch": False,
        },
    }


# ── All 8 agents execute ─────────────────────────────────────────────────────

@pytest.mark.unit
def test_all_agents_return_results(orchestrator, full_data):
    """All 8 agents must return a result dict (not crash)."""
    results = orchestrator.execute_all_agents(full_data)
    expected_agents = {"qa", "performance", "compliance", "devops", "sre", "sdet", "fullstack", "red_team"}
    assert set(results.keys()) == expected_agents, \
        f"Missing agents: {expected_agents - set(results.keys())}"


@pytest.mark.unit
def test_no_agent_errors(orchestrator, full_data):
    """No agent should return an error status."""
    results = orchestrator.execute_all_agents(full_data)
    for name, result in results.items():
        assert "error" not in result, f"Agent {name} returned error: {result.get('error')}"


# ── Individual agent result shapes ───────────────────────────────────────────

@pytest.mark.unit
def test_qa_result_shape(orchestrator, full_data):
    results = orchestrator.execute_all_agents(full_data)
    qa = results["qa"]
    assert "total_tests" in qa
    assert "passed" in qa
    assert "failed" in qa
    assert "recommendations" in qa


@pytest.mark.unit
def test_performance_result_shape(orchestrator, full_data):
    results = orchestrator.execute_all_agents(full_data)
    perf = results["performance"]
    assert "duration_ms" in perf
    assert "status" in perf
    assert "regression_detected" in perf
    assert "optimizations" in perf


@pytest.mark.unit
def test_compliance_result_shape(orchestrator, full_data):
    results = orchestrator.execute_all_agents(full_data)
    comp = results["compliance"]
    assert "data_encryption" in comp
    assert "pii_protection" in comp
    assert "violations" in comp


@pytest.mark.unit
def test_devops_result_shape(orchestrator, full_data):
    results = orchestrator.execute_all_agents(full_data)
    devops = results["devops"]
    assert "deployment_status" in devops
    assert "version" in devops
    assert "health_checks" in devops


@pytest.mark.unit
def test_sre_result_shape(orchestrator, full_data):
    results = orchestrator.execute_all_agents(full_data)
    sre = results["sre"]
    assert "total_errors" in sre
    assert "fixes_applied" in sre


@pytest.mark.unit
def test_sdet_result_shape(orchestrator, full_data):
    results = orchestrator.execute_all_agents(full_data)
    sdet = results["sdet"]
    assert "current_coverage" in sdet
    assert "coverage_status" in sdet


@pytest.mark.unit
def test_fullstack_result_shape(orchestrator, full_data):
    results = orchestrator.execute_all_agents(full_data)
    fs = results["fullstack"]
    assert "code_generated" in fs
    assert "status" in fs


@pytest.mark.unit
def test_red_team_result_shape(orchestrator, full_data):
    results = orchestrator.execute_all_agents(full_data)
    rt = results["red_team"]
    assert "bypass_attempts" in rt
    assert "scanner_strength" in rt


# ── Routing correctness ──────────────────────────────────────────────────────

@pytest.mark.unit
def test_qa_receives_test_results(orchestrator):
    """QA agent should receive test_results, not compliance_data."""
    data = {
        "test_results": {"total": 42, "passed": 42, "failed": 0, "coverage": 100},
    }
    results = orchestrator.execute_all_agents(data)
    assert results["qa"]["total_tests"] == 42


@pytest.mark.unit
def test_performance_receives_execution_data(orchestrator):
    data = {
        "execution_data": {"duration_ms": 999, "baseline_ms": 500, "memory_mb": 128},
    }
    results = orchestrator.execute_all_agents(data)
    assert results["performance"]["duration_ms"] == 999


@pytest.mark.unit
def test_devops_receives_deployment_config(orchestrator):
    data = {
        "deployment_config": {"version": "v9.9.9", "environment": "canary"},
    }
    results = orchestrator.execute_all_agents(data)
    assert results["devops"]["version"] == "v9.9.9"


# ── Partial data (missing keys for some agents) ──────────────────────────────

@pytest.mark.unit
def test_partial_data_agents_get_empty_dicts(orchestrator):
    """Agents whose data key is missing should get {} and handle gracefully."""
    results = orchestrator.execute_all_agents({"test_results": {"total": 1, "passed": 1}})
    # All 8 agents must still return results
    assert len(results) == 8
    for name, result in results.items():
        assert "error" not in result, f"Agent {name} crashed on missing data: {result}"


# ── get_agent_insights() ─────────────────────────────────────────────────────

@pytest.mark.unit
def test_get_agent_insights_after_execution(orchestrator, full_data):
    orchestrator.execute_all_agents(full_data)
    insights = orchestrator.get_agent_insights()
    assert isinstance(insights, dict)
    assert "qa" in insights
    assert "sre" in insights


@pytest.mark.unit
def test_get_agent_insights_without_execution(orchestrator):
    """Insights should work even without prior execution."""
    insights = orchestrator.get_agent_insights()
    assert isinstance(insights, dict)
    assert len(insights) == 8
