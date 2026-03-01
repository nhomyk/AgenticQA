"""
Dedicated DevOps Agent Tests — exercises DevOpsAgent.execute() with real input data.

Verifies:
  - Return schema: deployment_status, version, environment, health_checks
  - Health check defaults (api_health, database_connection, cache_available)
  - Version and environment passthrough
  - Edge cases: empty input, missing fields
"""
import pytest
from agents import DevOpsAgent


@pytest.fixture
def agent():
    return DevOpsAgent()


# ── Return schema ─────────────────────────────────────────────────────────────

@pytest.mark.unit
def test_devops_returns_required_keys(agent):
    result = agent.execute({
        "version": "v2.0.0",
        "environment": "production",
    })
    assert "deployment_status" in result
    assert "version" in result
    assert "environment" in result
    assert "health_checks" in result


# ── Deployment status ─────────────────────────────────────────────────────────

@pytest.mark.unit
def test_devops_deployment_succeeds(agent):
    result = agent.execute({"version": "v1.0.0", "environment": "staging"})
    assert result["deployment_status"] == "success"


# ── Version and environment passthrough ───────────────────────────────────────

@pytest.mark.unit
def test_devops_version_passthrough(agent):
    result = agent.execute({"version": "v3.2.1", "environment": "production"})
    assert result["version"] == "v3.2.1"


@pytest.mark.unit
def test_devops_environment_passthrough(agent):
    result = agent.execute({"version": "v1.0.0", "environment": "staging"})
    assert result["environment"] == "staging"


# ── Health checks ─────────────────────────────────────────────────────────────

@pytest.mark.unit
def test_devops_default_health_checks(agent):
    """Without health_check_urls, defaults to all-healthy."""
    result = agent.execute({"version": "v1.0.0", "environment": "production"})
    checks = result["health_checks"]
    assert checks.get("api_health") is True
    assert checks.get("database_connection") is True
    assert checks.get("cache_available") is True


@pytest.mark.unit
def test_devops_health_checks_are_dict(agent):
    result = agent.execute({"version": "v1.0.0"})
    assert isinstance(result["health_checks"], dict)


# ── Edge cases ────────────────────────────────────────────────────────────────

@pytest.mark.unit
def test_devops_empty_input(agent):
    result = agent.execute({})
    assert result["deployment_status"] == "success"
    assert result["version"] is None
    assert result["environment"] is None


@pytest.mark.unit
def test_devops_rag_insights_count(agent):
    result = agent.execute({"version": "v1.0.0"})
    assert "rag_insights_used" in result


@pytest.mark.unit
def test_devops_multiple_deployments(agent):
    r1 = agent.execute({"version": "v1.0.0", "environment": "staging"})
    r2 = agent.execute({"version": "v2.0.0", "environment": "production"})
    assert r1["version"] == "v1.0.0"
    assert r2["version"] == "v2.0.0"
    assert r1["environment"] == "staging"
    assert r2["environment"] == "production"
