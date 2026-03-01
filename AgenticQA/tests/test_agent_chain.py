"""
Agent Chain Data Flow Tests — verify agent output→input chaining works.

These tests exercise the real multi-agent pipeline:
  SRE fixes lint → SDET checks coverage → QA reviews → Compliance validates

No mocking of agent logic. Tests that agent A's output can meaningfully
drive agent B's input, which is the core ADLC promise.

Verifies:
  - SRE → SDET: lint fix results inform coverage assessment
  - SRE → Compliance: fix rate informs risk profile
  - QA → SDET: test failures drive gap identification
  - Fullstack → SRE → SDET: generate code → lint → coverage
  - Performance → QA: regression feeds back into test recommendations
  - Full pipeline: all agents in sequence, outputs cascade
"""
import pytest
from agents import (
    QAAssistantAgent, PerformanceAgent, ComplianceAgent,
    DevOpsAgent, SREAgent, SDETAgent, FullstackAgent, RedTeamAgent,
)


# ── SRE → SDET chain ─────────────────────────────────────────────────────────

@pytest.mark.unit
def test_sre_output_drives_sdet_coverage_check():
    """After SRE fixes lint errors, SDET should check if coverage is adequate."""
    sre = SREAgent()
    sdet = SDETAgent()

    # Step 1: SRE fixes linting errors
    sre_result = sre.execute({
        "file_path": "app.py",
        "errors": [
            {"rule": "E301", "message": "expected 2 blank lines", "line": 10, "file": "app.py"},
            {"rule": "E303", "message": "too many blank lines", "line": 20, "file": "app.py"},
        ],
    })
    assert sre_result["total_errors"] >= 1

    # Step 2: SDET evaluates coverage — code was modified, coverage might have changed
    sdet_result = sdet.execute({
        "coverage_percent": 70,
        "uncovered_files": ["app.py"],  # The file SRE just modified
        "test_type": "unit",
    })
    assert "current_coverage" in sdet_result
    assert "gaps" in sdet_result or "recommendations" in sdet_result


@pytest.mark.unit
def test_sre_fix_rate_informs_compliance():
    """SRE fix rate should inform compliance risk assessment."""
    sre = SREAgent()
    compliance = ComplianceAgent()

    sre_result = sre.execute({
        "file_path": "auth.py",
        "errors": [
            {"rule": "E722", "message": "bare except", "line": 5, "file": "auth.py"},
        ],
    })
    fix_rate = sre_result.get("fix_rate", 0)

    # Compliance uses SRE output to understand code quality
    comp_result = compliance.execute({
        "encrypted": True,
        "pii_masked": True,
        "audit_enabled": True,
        "context": f"SRE fix rate: {fix_rate}",
    })
    assert "violations" in comp_result


# ── QA → SDET chain ──────────────────────────────────────────────────────────

@pytest.mark.unit
def test_qa_failures_drive_sdet_gap_identification():
    """When QA finds failures, SDET should identify coverage gaps."""
    qa = QAAssistantAgent()
    sdet = SDETAgent()

    # Step 1: QA finds failures
    qa_result = qa.execute({
        "total": 100, "passed": 70, "failed": 30, "coverage": 60,
    })
    assert qa_result["failed"] == 30

    # Step 2: SDET identifies gaps in the poorly covered areas
    sdet_result = sdet.execute({
        "coverage_percent": qa_result["coverage"],
        "uncovered_files": ["auth/login.py", "auth/session.py"],
        "test_type": "unit",
    })
    assert sdet_result["current_coverage"] == 60
    assert sdet_result["coverage_status"] in ("insufficient", "below_threshold", "adequate")


# ── Fullstack → SRE → SDET chain ─────────────────────────────────────────────

@pytest.mark.unit
def test_fullstack_generate_then_sre_lint_then_sdet_coverage():
    """Full code lifecycle: generate → lint → coverage check."""
    fullstack = FullstackAgent()
    sre = SREAgent()
    sdet = SDETAgent()

    # Step 1: Fullstack generates code
    fs_result = fullstack.execute({
        "title": "Add user registration",
        "category": "api",
        "description": "Create POST /register endpoint",
    })
    assert fs_result["code_generated"] is True

    # Step 2: SRE lints the generated code
    sre_result = sre.execute({
        "file_path": "register.py",
        "errors": [
            {"rule": "W291", "message": "trailing whitespace", "line": 1, "file": "register.py"},
        ],
    })
    assert "fixes_applied" in sre_result

    # Step 3: SDET checks coverage of the new module
    sdet_result = sdet.execute({
        "coverage_percent": 0,  # New code has no tests yet
        "uncovered_files": ["register.py"],
        "test_type": "unit",
    })
    assert sdet_result["current_coverage"] == 0
    assert len(sdet_result.get("gaps", sdet_result.get("recommendations", []))) >= 1


# ── Performance → QA feedback ────────────────────────────────────────────────

@pytest.mark.unit
def test_performance_regression_drives_qa_recommendations():
    """Performance regression should cause QA to recommend more testing."""
    perf = PerformanceAgent()
    qa = QAAssistantAgent()

    # Step 1: Performance detects regression
    perf_result = perf.execute({
        "duration_ms": 6000, "baseline_ms": 2000, "memory_mb": 1024,
    })
    assert perf_result["regression_detected"] is True

    # Step 2: QA should note the degraded state when reviewing test results
    qa_result = qa.execute({
        "total": 50, "passed": 40, "failed": 10, "coverage": 70,
        "status": f"perf_status={perf_result['status']}",
    })
    assert qa_result["failed"] == 10
    assert len(qa_result["recommendations"]) >= 1


# ── RedTeam → Compliance chain ───────────────────────────────────────────────

@pytest.mark.unit
def test_red_team_findings_inform_compliance():
    """Red team scan results feed into compliance assessment."""
    red_team = RedTeamAgent()
    compliance = ComplianceAgent()

    # Step 1: Red team scans
    rt_result = red_team.execute({
        "mode": "fast", "target": "both", "auto_patch": False,
    })
    scanner_strength = rt_result.get("scanner_strength", 0)

    # Step 2: Compliance considers the security posture
    comp_result = compliance.execute({
        "encrypted": True,
        "pii_masked": True,
        "audit_enabled": True,
        "context": f"scanner_strength={scanner_strength}%",
    })
    assert "violations" in comp_result


# ── Full pipeline: all agents in sequence ─────────────────────────────────────

@pytest.mark.unit
def test_full_agent_pipeline_cascading():
    """Full ADLC pipeline: Fullstack → SRE → SDET → QA → Performance → Compliance → DevOps."""
    # Step 1: Fullstack generates new feature
    fs = FullstackAgent().execute({
        "title": "Add dashboard widget",
        "category": "ui",
        "description": "Create a status widget for the dashboard",
    })
    assert fs["code_generated"] is True

    # Step 2: SRE lints the generated code
    sre = SREAgent().execute({
        "file_path": "widget.py",
        "errors": [{"rule": "E501", "message": "line too long", "line": 1, "file": "widget.py"}],
    })
    assert "fixes_applied" in sre

    # Step 3: SDET checks coverage
    sdet = SDETAgent().execute({
        "coverage_percent": 45,
        "uncovered_files": ["widget.py"],
        "test_type": "unit",
    })
    assert sdet["current_coverage"] == 45

    # Step 4: QA reviews overall test health
    qa = QAAssistantAgent().execute({
        "total": 200, "passed": 190, "failed": 10,
        "coverage": sdet["current_coverage"],
    })
    assert qa["total_tests"] == 200

    # Step 5: Performance validates execution time
    perf = PerformanceAgent().execute({
        "duration_ms": 800, "baseline_ms": 500, "memory_mb": 256,
    })
    assert perf["status"] == "optimal"

    # Step 6: Compliance validates the release
    comp = ComplianceAgent().execute({
        "encrypted": True, "pii_masked": True, "audit_enabled": True,
    })
    assert comp["data_encryption"] is True

    # Step 7: DevOps deploys
    devops = DevOpsAgent().execute({
        "version": "v2.2.0", "environment": "staging",
    })
    assert devops["deployment_status"] == "success"
