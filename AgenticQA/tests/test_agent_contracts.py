"""Agent Output Contract Tests — verify Pydantic models enforce return schemas.

Tests:
  - All 8 agents produce outputs that pass contract validation
  - Invalid outputs are rejected (missing keys, wrong types, constraint violations)
  - validate_agent_output() works for all registered agents
  - AGENT_CONTRACTS registry has exactly 8 entries
"""
import pytest
from pydantic import ValidationError

from agenticqa.contracts.agent_outputs import (
    QAOutput,
    PerformanceOutput,
    ComplianceOutput,
    DevOpsOutput,
    SREOutput,
    SDETOutput,
    FullstackOutput,
    RedTeamOutput,
    validate_agent_output,
    AGENT_CONTRACTS,
)


# ── Registry ────────────────────────────────────────────────────────────────────

@pytest.mark.unit
def test_contracts_registry_has_8_agents():
    assert len(AGENT_CONTRACTS) == 8


@pytest.mark.unit
def test_contracts_registry_keys():
    expected = {"QA_Assistant", "Performance", "Compliance", "DevOps",
                "SRE", "SDET", "Fullstack", "RedTeam_Agent"}
    assert set(AGENT_CONTRACTS.keys()) == expected


# ── QA Output ───────────────────────────────────────────────────────────────────

@pytest.mark.unit
def test_qa_output_valid():
    out = QAOutput(total_tests=100, passed=95, failed=5, coverage=85,
                   recommendations=["Fix flaky tests"], rag_insights_used=2)
    assert out.total_tests == 100


@pytest.mark.unit
def test_qa_output_passed_plus_failed_exceeds_total():
    with pytest.raises(ValidationError, match="passed.*failed.*total"):
        QAOutput(total_tests=10, passed=8, failed=5, coverage=50)


@pytest.mark.unit
def test_qa_output_negative_tests():
    with pytest.raises(ValidationError):
        QAOutput(total_tests=-1, passed=0, failed=0, coverage=0)


@pytest.mark.unit
def test_qa_output_missing_required_field():
    with pytest.raises(ValidationError):
        QAOutput(total_tests=10, passed=10)  # missing failed, coverage


# ── Performance Output ──────────────────────────────────────────────────────────

@pytest.mark.unit
def test_performance_output_valid():
    out = PerformanceOutput(
        duration_ms=1200, baseline_ms=1000, memory_mb=512,
        status="optimal", regression_detected=False, optimizations=[],
    )
    assert out.status == "optimal"


@pytest.mark.unit
def test_performance_output_negative_duration():
    with pytest.raises(ValidationError):
        PerformanceOutput(
            duration_ms=-1, baseline_ms=0, memory_mb=0,
            status="optimal", regression_detected=False,
        )


# ── Compliance Output ──────────────────────────────────────────────────────────

@pytest.mark.unit
def test_compliance_output_valid():
    out = ComplianceOutput(
        data_encryption=True, pii_protection=True,
        audit_logs=True, violations=[],
    )
    assert out.data_encryption is True


@pytest.mark.unit
def test_compliance_output_with_extensions():
    out = ComplianceOutput(
        data_encryption=True, pii_protection=False,
        violations=["Missing PII masking"],
        cve_risk_score=0.3, reachable_cves=2,
        hipaa_risk_score=0.1,
    )
    assert out.cve_risk_score == 0.3
    assert out.hipaa_risk_score == 0.1


# ── DevOps Output ──────────────────────────────────────────────────────────────

@pytest.mark.unit
def test_devops_output_valid():
    out = DevOpsOutput(
        deployment_status="success", version="v1.0.0",
        environment="staging",
        health_checks={"api_health": True, "database_connection": True},
    )
    assert out.deployment_status == "success"


@pytest.mark.unit
def test_devops_output_none_version():
    out = DevOpsOutput(deployment_status="success")
    assert out.version is None


# ── SRE Output ──────────────────────────────────────────────────────────────────

@pytest.mark.unit
def test_sre_output_valid():
    out = SREOutput(
        total_errors=5, fixable_errors=4, fixes_applied=3,
        fix_rate=0.75, architectural_violations=1,
        status="partial",
    )
    assert out.fix_rate == 0.75


@pytest.mark.unit
def test_sre_output_fix_rate_exceeds_1():
    with pytest.raises(ValidationError):
        SREOutput(
            total_errors=1, fixable_errors=1, fixes_applied=1,
            fix_rate=1.5, architectural_violations=0, status="success",
        )


# ── SDET Output ─────────────────────────────────────────────────────────────────

@pytest.mark.unit
def test_sdet_output_valid():
    out = SDETOutput(
        current_coverage=78, coverage_status="insufficient",
        coverage_threshold_used=80, gaps_identified=3,
        gaps=[{"file": "utils.py"}], recommendations=["Add unit tests"],
    )
    assert out.coverage_status == "insufficient"


# ── Fullstack Output ────────────────────────────────────────────────────────────

@pytest.mark.unit
def test_fullstack_output_valid():
    out = FullstackOutput(
        feature_title="Add health check", category="api",
        code_generated=True, code="def health(): return 200",
        files_created=["health.py"], status="success",
    )
    assert out.code_generated is True


@pytest.mark.unit
def test_fullstack_output_missing_title():
    with pytest.raises(ValidationError):
        FullstackOutput(category="api", code_generated=True, status="success")


# ── Red Team Output ─────────────────────────────────────────────────────────────

@pytest.mark.unit
def test_redteam_output_valid():
    out = RedTeamOutput(
        bypass_attempts=20, successful_bypasses=1,
        patches_applied=1, proposals_generated=0,
        scanner_strength=0.95, gate_strength=1.0,
        vulnerabilities=[], constitutional_proposals=[],
        status="patched",
    )
    assert out.scanner_strength == 0.95


@pytest.mark.unit
def test_redteam_output_strength_exceeds_1():
    with pytest.raises(ValidationError):
        RedTeamOutput(
            bypass_attempts=10, successful_bypasses=0,
            patches_applied=0, proposals_generated=0,
            scanner_strength=1.5, gate_strength=1.0,
            status="clean",
        )


# ── validate_agent_output() ─────────────────────────────────────────────────────

@pytest.mark.unit
def test_validate_qa_output():
    data = {"total_tests": 10, "passed": 10, "failed": 0, "coverage": 100,
            "recommendations": [], "rag_insights_used": 0}
    result = validate_agent_output("QA_Assistant", data)
    assert isinstance(result, QAOutput)


@pytest.mark.unit
def test_validate_unknown_agent_raises():
    with pytest.raises(KeyError, match="No contract"):
        validate_agent_output("UnknownAgent", {})


@pytest.mark.unit
def test_validate_invalid_output_raises():
    with pytest.raises(ValidationError):
        validate_agent_output("QA_Assistant", {"total_tests": "not_a_number"})


# ── Real agent execution passes contract ─────────────────────────────────────

@pytest.mark.unit
def test_qa_agent_output_passes_contract():
    from agents import QAAssistantAgent
    agent = QAAssistantAgent()
    result = agent.execute({"total": 50, "passed": 45, "failed": 5, "coverage": 80})
    validated = validate_agent_output("QA_Assistant", result)
    assert validated.total_tests == 50


@pytest.mark.unit
def test_performance_agent_output_passes_contract():
    from agents import PerformanceAgent
    agent = PerformanceAgent()
    result = agent.execute({"duration_ms": 500, "baseline_ms": 400, "memory_mb": 128})
    validated = validate_agent_output("Performance", result)
    assert validated.status == "optimal"


@pytest.mark.unit
def test_compliance_agent_output_passes_contract():
    from agents import ComplianceAgent
    agent = ComplianceAgent()
    result = agent.execute({"encrypted": True, "pii_masked": True, "audit_enabled": True})
    validated = validate_agent_output("Compliance", result)
    assert validated.data_encryption is True


@pytest.mark.unit
def test_devops_agent_output_passes_contract():
    from agents import DevOpsAgent
    agent = DevOpsAgent()
    result = agent.execute({"version": "v1.0.0", "environment": "staging"})
    validated = validate_agent_output("DevOps", result)
    assert validated.deployment_status == "success"


@pytest.mark.unit
def test_sre_agent_output_passes_contract():
    from agents import SREAgent
    agent = SREAgent()
    result = agent.execute({
        "file_path": "app.py",
        "errors": [{"rule": "E301", "message": "expected 2 blank lines", "line": 1, "file": "app.py"}],
    })
    validated = validate_agent_output("SRE", result)
    assert validated.total_errors >= 1


@pytest.mark.unit
def test_sdet_agent_output_passes_contract():
    from agents import SDETAgent
    agent = SDETAgent()
    result = agent.execute({
        "coverage_percent": 70, "uncovered_files": ["app.py"], "test_type": "unit",
    })
    validated = validate_agent_output("SDET", result)
    assert validated.current_coverage == 70


@pytest.mark.unit
def test_fullstack_agent_output_passes_contract():
    from agents import FullstackAgent
    agent = FullstackAgent()
    result = agent.execute({
        "title": "Add endpoint", "category": "api", "description": "GET /health returns 200",
    })
    validated = validate_agent_output("Fullstack", result)
    assert validated.code_generated is True
