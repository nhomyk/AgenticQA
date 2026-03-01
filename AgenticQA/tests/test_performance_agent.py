"""
Dedicated Performance Agent Tests — exercises PerformanceAgent.execute() with real input data.

Verifies:
  - Return schema: duration_ms, baseline_ms, memory_mb, status, regression_detected, optimizations
  - Regression detection (duration > 2x baseline)
  - Status thresholds (>= 5000ms → degraded)
  - Optimization suggestions
  - Edge cases: zero baseline, high memory, empty input
"""
import pytest
from agents import PerformanceAgent


@pytest.fixture
def agent():
    return PerformanceAgent()


# ── Return schema ─────────────────────────────────────────────────────────────

@pytest.mark.unit
def test_perf_returns_required_keys(agent):
    result = agent.execute({"duration_ms": 100, "baseline_ms": 50, "memory_mb": 256})
    assert "duration_ms" in result
    assert "baseline_ms" in result
    assert "memory_mb" in result
    assert "status" in result
    assert "regression_detected" in result
    assert "optimizations" in result


# ── Regression detection ─────────────────────────────────────────────────────

@pytest.mark.unit
def test_perf_detects_regression_over_2x_baseline(agent):
    """Duration > 2x baseline must be flagged as regression."""
    result = agent.execute({"duration_ms": 5000, "baseline_ms": 2000, "memory_mb": 128})
    assert result["regression_detected"] is True


@pytest.mark.unit
def test_perf_no_regression_within_2x(agent):
    """Duration within 2x baseline must not be flagged."""
    result = agent.execute({"duration_ms": 300, "baseline_ms": 200, "memory_mb": 128})
    assert result["regression_detected"] is False


@pytest.mark.unit
def test_perf_no_regression_zero_baseline(agent):
    """Zero baseline means no regression possible."""
    result = agent.execute({"duration_ms": 10000, "baseline_ms": 0, "memory_mb": 128})
    assert result["regression_detected"] is False


# ── Status thresholds ─────────────────────────────────────────────────────────

@pytest.mark.unit
def test_perf_optimal_under_5000ms(agent):
    result = agent.execute({"duration_ms": 500, "baseline_ms": 400, "memory_mb": 64})
    assert result["status"] == "optimal"


@pytest.mark.unit
def test_perf_degraded_over_5000ms(agent):
    result = agent.execute({"duration_ms": 6000, "baseline_ms": 0, "memory_mb": 64})
    assert result["status"] == "degraded"


@pytest.mark.unit
def test_perf_degraded_from_regression(agent):
    """Regression alone (without > 5000ms) should trigger degraded."""
    result = agent.execute({"duration_ms": 3000, "baseline_ms": 1000, "memory_mb": 64})
    assert result["regression_detected"] is True
    assert result["status"] == "degraded"


# ── Optimization suggestions ─────────────────────────────────────────────────

@pytest.mark.unit
def test_perf_suggests_optimization_for_high_latency(agent):
    result = agent.execute({"duration_ms": 8000, "baseline_ms": 0, "memory_mb": 1024})
    assert len(result["optimizations"]) >= 1
    assert any("latency" in opt.lower() or "profile" in opt.lower()
               for opt in result["optimizations"])


@pytest.mark.unit
def test_perf_suggests_optimization_for_regression(agent):
    result = agent.execute({"duration_ms": 5000, "baseline_ms": 2000, "memory_mb": 256})
    assert any("baseline" in opt.lower() or "regression" in opt.lower()
               for opt in result["optimizations"])


# ── Edge cases ────────────────────────────────────────────────────────────────

@pytest.mark.unit
def test_perf_empty_input(agent):
    result = agent.execute({})
    assert result["duration_ms"] == 0
    assert result["status"] == "optimal"
    assert result["regression_detected"] is False


@pytest.mark.unit
def test_perf_mirrors_input_values(agent):
    result = agent.execute({"duration_ms": 1234, "baseline_ms": 567, "memory_mb": 890})
    assert result["duration_ms"] == 1234
    assert result["baseline_ms"] == 567
    assert result["memory_mb"] == 890


@pytest.mark.unit
def test_perf_rag_insights_count(agent):
    result = agent.execute({"duration_ms": 100})
    assert "rag_insights_used" in result


@pytest.mark.unit
def test_perf_optimizations_are_list(agent):
    result = agent.execute({"duration_ms": 100})
    assert isinstance(result["optimizations"], list)


@pytest.mark.unit
def test_perf_multiple_executions_independent(agent):
    r1 = agent.execute({"duration_ms": 100, "baseline_ms": 50})
    r2 = agent.execute({"duration_ms": 8000, "baseline_ms": 50})
    assert r1["status"] == "optimal"
    assert r2["status"] == "degraded"
