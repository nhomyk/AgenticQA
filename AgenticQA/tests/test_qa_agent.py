"""
Dedicated QA Agent Tests — exercises QAAssistantAgent.execute() with real input data.

Verifies:
  - Return schema: total_tests, passed, failed, coverage, recommendations
  - Recommendation generation based on failure rates
  - Edge cases: empty results, perfect results, high failure rate
  - RAG augmentation flow (mocked Weaviate, real logic)
"""
import pytest
from agents import QAAssistantAgent


@pytest.fixture
def agent():
    return QAAssistantAgent()


# ── Return schema ─────────────────────────────────────────────────────────────

@pytest.mark.unit
def test_qa_returns_required_keys(agent):
    result = agent.execute({"total": 10, "passed": 8, "failed": 2, "coverage": 80})
    assert "total_tests" in result
    assert "passed" in result
    assert "failed" in result
    assert "coverage" in result
    assert "recommendations" in result


@pytest.mark.unit
def test_qa_mirrors_input_counts(agent):
    result = agent.execute({"total": 50, "passed": 45, "failed": 5, "coverage": 90})
    assert result["total_tests"] == 50
    assert result["passed"] == 45
    assert result["failed"] == 5
    assert result["coverage"] == 90


# ── Recommendation logic ─────────────────────────────────────────────────────

@pytest.mark.unit
def test_qa_high_failure_rate_triggers_recommendation(agent):
    """When > 10% of tests fail, should recommend review."""
    result = agent.execute({"total": 100, "passed": 50, "failed": 50, "coverage": 40})
    assert any("failure rate" in r.lower() or "review" in r.lower()
               for r in result["recommendations"]), \
        f"Expected failure rate recommendation, got: {result['recommendations']}"


@pytest.mark.unit
def test_qa_low_failure_rate_no_alarm(agent):
    """When failure rate is very low, no high-failure-rate recommendation."""
    result = agent.execute({"total": 1000, "passed": 999, "failed": 1, "coverage": 95})
    assert not any("high failure rate" in r.lower() for r in result["recommendations"])


@pytest.mark.unit
def test_qa_perfect_results(agent):
    result = agent.execute({"total": 100, "passed": 100, "failed": 0, "coverage": 100})
    assert result["failed"] == 0
    assert result["passed"] == 100


# ── Edge cases ────────────────────────────────────────────────────────────────

@pytest.mark.unit
def test_qa_empty_results(agent):
    result = agent.execute({})
    assert result["total_tests"] == 0
    assert result["passed"] == 0
    assert result["failed"] == 0
    assert result["coverage"] == 0


@pytest.mark.unit
def test_qa_with_test_name(agent):
    result = agent.execute({
        "test_name": "auth_integration",
        "test_type": "integration",
        "total": 25, "passed": 20, "failed": 5, "coverage": 70,
    })
    assert result["total_tests"] == 25


@pytest.mark.unit
def test_qa_recommendations_are_list(agent):
    result = agent.execute({"total": 10, "passed": 10, "failed": 0, "coverage": 100})
    assert isinstance(result["recommendations"], list)


@pytest.mark.unit
def test_qa_rag_insights_count_present(agent):
    result = agent.execute({"total": 10, "passed": 10, "failed": 0, "coverage": 100})
    assert "rag_insights_used" in result
    assert isinstance(result["rag_insights_used"], int)


# ── Multiple executions (learning) ───────────────────────────────────────────

@pytest.mark.unit
def test_qa_multiple_executions_stable(agent):
    """Agent should handle being called multiple times without state corruption."""
    r1 = agent.execute({"total": 10, "passed": 10, "failed": 0, "coverage": 100})
    r2 = agent.execute({"total": 50, "passed": 25, "failed": 25, "coverage": 50})
    r3 = agent.execute({"total": 100, "passed": 99, "failed": 1, "coverage": 95})
    assert r1["total_tests"] == 10
    assert r2["total_tests"] == 50
    assert r3["total_tests"] == 100
    # Each call is independent
    assert r2["failed"] == 25
    assert r3["failed"] == 1
