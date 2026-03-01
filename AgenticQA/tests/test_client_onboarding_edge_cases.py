"""Tests for client onboarding edge cases.

Validates:
  - Safe file iteration (size/count limits)
  - SRE JS auto-detection via package.json
  - EU AI Act false positive prevention (AI-detection pre-check)
  - Ontology coverage for all scanner types
  - Scan result ingestion endpoint
"""
import os
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock

# ── Safe file iteration ──────────────────────────────────────────────────────

@pytest.mark.unit
def test_safe_iter_respects_max_files(tmp_path):
    """iter_source_files stops at max_files limit."""
    from agenticqa.security.safe_file_iter import iter_source_files
    for i in range(20):
        (tmp_path / f"file{i}.py").write_text(f"x = {i}")
    files = list(iter_source_files(tmp_path, max_files=5))
    assert len(files) == 5


@pytest.mark.unit
def test_safe_iter_skips_large_files(tmp_path):
    """iter_source_files skips files exceeding max_file_size."""
    from agenticqa.security.safe_file_iter import iter_source_files
    (tmp_path / "small.py").write_text("x = 1")
    (tmp_path / "large.py").write_text("x" * 200)
    files = list(iter_source_files(tmp_path, max_file_size=100))
    assert len(files) == 1
    assert files[0].name == "small.py"


@pytest.mark.unit
def test_safe_iter_skips_blacklisted_dirs(tmp_path):
    """iter_source_files skips node_modules, .git, etc."""
    from agenticqa.security.safe_file_iter import iter_source_files
    (tmp_path / "app.py").write_text("x = 1")
    nm = tmp_path / "node_modules"
    nm.mkdir()
    (nm / "dep.py").write_text("x = 2")
    files = list(iter_source_files(tmp_path))
    assert all("node_modules" not in str(f) for f in files)


@pytest.mark.unit
def test_safe_iter_filters_extensions(tmp_path):
    """iter_source_files only yields matching extensions."""
    from agenticqa.security.safe_file_iter import iter_source_files
    (tmp_path / "app.py").write_text("x = 1")
    (tmp_path / "data.csv").write_text("a,b,c")
    (tmp_path / "image.png").write_bytes(b"\x89PNG")
    files = list(iter_source_files(tmp_path, extensions={".py"}))
    assert len(files) == 1
    assert files[0].name == "app.py"


@pytest.mark.unit
def test_safe_read_text_returns_none_for_large_file(tmp_path):
    """safe_read_text returns None for files exceeding max_size."""
    from agenticqa.security.safe_file_iter import safe_read_text
    (tmp_path / "big.py").write_text("x" * 200)
    assert safe_read_text(tmp_path / "big.py", max_size=100) is None
    assert safe_read_text(tmp_path / "big.py", max_size=500) is not None


@pytest.mark.unit
def test_safe_read_text_handles_missing_file(tmp_path):
    """safe_read_text returns None for nonexistent files."""
    from agenticqa.security.safe_file_iter import safe_read_text
    assert safe_read_text(tmp_path / "nonexistent.py") is None


# ── SRE JS auto-detection ────────────────────────────────────────────────────

@pytest.mark.unit
def test_sre_autodetects_js_from_package_json(tmp_path):
    """SRE execute() auto-detects JS repos from package.json."""
    from agents import SREAgent
    agent = SREAgent.__new__(SREAgent)
    agent.agent_name = "SRE_Agent"
    agent._strategy_selector = None
    agent._outcome_tracker = None
    agent._threshold_calibrator = None
    agent._rag_system = None
    agent.use_rag = False
    agent.rag = None
    agent.use_data_store = False
    agent.data_store = None
    agent._record_execution = MagicMock()

    (tmp_path / "package.json").write_text('{"name": "test"}')

    with patch.object(agent, "_run_typescript_linter", return_value=[]) as mock_lint:
        result = agent.execute({
            "repo_path": str(tmp_path),
            "errors": [],
        })
    mock_lint.assert_called_once_with(str(tmp_path))


# ── EU AI Act false positive prevention ──────────────────────────────────────

@pytest.mark.unit
def test_ai_act_non_ai_repo_not_high_risk(tmp_path):
    """Non-AI repos with business keywords should NOT be high_risk."""
    from agenticqa.compliance.ai_act import AIActComplianceChecker
    # Create a repo that mentions "financial" but has no AI/ML
    (tmp_path / "README.md").write_text("# Financial Utils\nA library for financial calculations.\n")
    (tmp_path / "setup.py").write_text("from setuptools import setup\nsetup(name='financial-utils')")
    checker = AIActComplianceChecker()
    result = checker.check(str(tmp_path))
    assert result.risk_category != "high_risk", \
        f"Non-AI repo should not be high_risk, got {result.risk_category}"


@pytest.mark.unit
def test_ai_act_ai_repo_correctly_classified(tmp_path):
    """AI repos with Annex III keywords should be high_risk."""
    from agenticqa.compliance.ai_act import AIActComplianceChecker
    (tmp_path / "README.md").write_text(
        "# AI Credit Scorer\nUses deep learning for financial risk assessment.\n"
    )
    (tmp_path / "requirements.txt").write_text("torch\ntransformers\n")
    checker = AIActComplianceChecker()
    result = checker.check(str(tmp_path))
    assert result.risk_category == "high_risk"


@pytest.mark.unit
def test_ai_act_detect_ai_system_from_deps(tmp_path):
    """_detect_ai_system returns True when AI deps are found."""
    from agenticqa.compliance.ai_act import AIActComplianceChecker
    checker = AIActComplianceChecker()
    (tmp_path / "requirements.txt").write_text("flask\nopenai\n")
    assert checker._detect_ai_system(tmp_path, "") is True


@pytest.mark.unit
def test_ai_act_detect_ai_system_no_ai(tmp_path):
    """_detect_ai_system returns False for non-AI repos."""
    from agenticqa.compliance.ai_act import AIActComplianceChecker
    checker = AIActComplianceChecker()
    (tmp_path / "requirements.txt").write_text("flask\nrequests\n")
    assert checker._detect_ai_system(tmp_path, "") is False


@pytest.mark.unit
def test_ai_act_detect_ai_from_readme_text(tmp_path):
    """_detect_ai_system returns True from README AI keywords."""
    from agenticqa.compliance.ai_act import AIActComplianceChecker
    checker = AIActComplianceChecker()
    combined = "this project uses machine learning for prediction"
    assert checker._detect_ai_system(tmp_path, combined) is True


# ── Ontology coverage ────────────────────────────────────────────────────────

@pytest.mark.unit
def test_ontology_covers_all_scanner_types():
    """TASK_AGENT_MAP must include entries for all scanner types."""
    from agenticqa.delegation.guardrails import DelegationGuardrails
    task_map = DelegationGuardrails.TASK_AGENT_MAP
    required_tasks = [
        "architecture_scan", "secrets_scan", "ci_yaml_scan",
        "container_scan", "owasp_scan", "prompt_injection_scan",
        "hipaa_scan", "ai_act_check", "legal_risk_scan",
        "lint", "security_scan", "mcp_security_scan",
        "trust_graph_analysis", "data_flow_trace", "ai_sbom",
    ]
    missing = [t for t in required_tasks if t not in task_map]
    assert not missing, f"Missing task types in ontology: {missing}"


@pytest.mark.unit
def test_ontology_has_at_least_30_task_types():
    """TASK_AGENT_MAP should have 30+ entries after additions."""
    from agenticqa.delegation.guardrails import DelegationGuardrails
    count = len(DelegationGuardrails.TASK_AGENT_MAP)
    assert count >= 30, f"Expected 30+ task types, got {count}"


# ── Scan ingestion endpoint ──────────────────────────────────────────────────

@pytest.mark.unit
def test_full_scan_endpoint_exists():
    """POST /api/security/full-scan endpoint must exist."""
    os.environ["AGENTICQA_AUTH_DISABLE"] = "1"
    os.environ["AGENTICQA_PATH_SANITIZE_DISABLE"] = "1"
    from fastapi.testclient import TestClient
    import agent_api
    client = TestClient(agent_api.app)
    resp = client.post("/api/security/full-scan", params={"repo_path": "."})
    assert resp.status_code == 200
    data = resp.json()
    assert data.get("success") is True
    assert "summary" in data
    assert "scanners" in data


@pytest.mark.unit
def test_ingest_scan_result_endpoint():
    """POST /api/ingest/scan-result stores artifacts."""
    os.environ["AGENTICQA_AUTH_DISABLE"] = "1"
    os.environ["AGENTICQA_PATH_SANITIZE_DISABLE"] = "1"
    from fastapi.testclient import TestClient
    import agent_api
    client = TestClient(agent_api.app)
    body = {
        "summary": {"repo_path": "/tmp/test"},
        "scanners": {
            "test_scanner": {
                "status": "ok",
                "result": {"total_findings": 3},
            }
        },
    }
    resp = client.post("/api/ingest/scan-result", json=body)
    assert resp.status_code == 200
    data = resp.json()
    assert data.get("success") is True
    assert data.get("ingested") == 1


# ── Architecture scanner uses safe iterator ──────────────────────────────────

@pytest.mark.unit
def test_architecture_scanner_uses_safe_limits(tmp_path):
    """ArchitectureScanner must not crash on empty repos."""
    from agenticqa.security.architecture_scanner import ArchitectureScanner
    result = ArchitectureScanner().scan(str(tmp_path))
    assert result.scan_error is None
    assert result.files_scanned == 0
