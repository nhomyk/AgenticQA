"""
Unit tests for SystemIntegrityChecker.

Tests run fully offline (no network, no Docker). Each check is exercised
directly or via the checker's check_category() shortcut.
"""
import json
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock


from agenticqa.monitoring.integrity_checker import (
    SystemIntegrityChecker,
    IntegrityReport,
    CheckResult,
    _run,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _category(category: str) -> IntegrityReport:
    return SystemIntegrityChecker().check_category(category)


def _find(report: IntegrityReport, name: str) -> CheckResult:
    for c in report.checks:
        if c.name == name:
            return c
    raise KeyError(name)


# ---------------------------------------------------------------------------
# CheckResult / IntegrityReport data model
# ---------------------------------------------------------------------------

@pytest.mark.unit
def test_check_result_str_pass():
    c = CheckResult(name="x", category="cat", passed=True, message="ok")
    assert "[PASS]" in str(c)


@pytest.mark.unit
def test_check_result_str_fail_shows_detail():
    c = CheckResult(name="x", category="cat", passed=False,
                    message="oops", detail="line1\nline2")
    s = str(c)
    assert "[FAIL]" in s
    assert "line1" in s


@pytest.mark.unit
def test_integrity_report_failures_property():
    report = IntegrityReport(
        timestamp="now",
        passed=False,
        checks=[
            CheckResult("a", "cat", True, "ok"),
            CheckResult("b", "cat", False, "bad"),
        ],
    )
    assert len(report.failures) == 1
    assert report.failures[0].name == "b"


@pytest.mark.unit
def test_integrity_report_to_dict():
    report = IntegrityReport(
        timestamp="ts",
        passed=True,
        checks=[CheckResult("x", "cat", True, "ok", latency_ms=1.5)],
    )
    d = report.to_dict()
    assert d["passed"] is True
    assert d["total"] == 1
    assert d["checks"][0]["name"] == "x"
    assert d["checks"][0]["latency_ms"] == 1.5


# ---------------------------------------------------------------------------
# _run helper
# ---------------------------------------------------------------------------

@pytest.mark.unit
def test_run_captures_exception():
    def bad():
        raise RuntimeError("boom")

    result = _run("bad_check", "test", bad)
    assert result.passed is False
    assert "RuntimeError" in result.message
    assert result.detail is not None


@pytest.mark.unit
def test_run_records_latency():
    result = _run("fast", "test", lambda: (True, "ok"))
    assert result.latency_ms >= 0.0


# ---------------------------------------------------------------------------
# Ontology checks
# ---------------------------------------------------------------------------

@pytest.mark.unit
def test_ontology_task_types_registered():
    report = _category("ontology")
    r = _find(report, "task_types_registered")
    assert r.passed, r.message


@pytest.mark.unit
def test_ontology_agents_all_known():
    report = _category("ontology")
    r = _find(report, "agents_all_known")
    assert r.passed, r.message


@pytest.mark.unit
def test_ontology_get_allowed_agents_works():
    report = _category("ontology")
    r = _find(report, "get_allowed_agents_works")
    assert r.passed, r.message


@pytest.mark.unit
def test_ontology_no_empty_lists():
    report = _category("ontology")
    r = _find(report, "no_empty_agent_lists")
    assert r.passed, r.message


@pytest.mark.unit
def test_ontology_detects_unknown_agent(monkeypatch):
    """Inject an unknown agent name into the map and confirm detection."""
    from agenticqa.delegation import guardrails as gr
    original = dict(gr.DelegationGuardrails.TASK_AGENT_MAP)
    patched = dict(original)
    patched["_test_task"] = ["GhostAgent"]
    monkeypatch.setattr(gr.DelegationGuardrails, "TASK_AGENT_MAP", patched)

    from agenticqa.monitoring.integrity_checker import _check_ontology_agents_known
    ok, msg = _check_ontology_agents_known()
    assert not ok
    assert "GhostAgent" in msg


# ---------------------------------------------------------------------------
# Constitutional Gate checks
# ---------------------------------------------------------------------------

@pytest.mark.unit
def test_gate_safe_action_allows():
    report = _category("gate")
    r = _find(report, "safe_action_allows")
    assert r.passed, r.message


@pytest.mark.unit
def test_gate_destructive_denies():
    report = _category("gate")
    r = _find(report, "destructive_denies")
    assert r.passed, r.message


@pytest.mark.unit
def test_gate_result_has_verdict():
    report = _category("gate")
    r = _find(report, "result_has_verdict")
    assert r.passed, r.message


# ---------------------------------------------------------------------------
# Scanner checks
# ---------------------------------------------------------------------------

@pytest.mark.unit
def test_scanner_clean_agent_passes():
    report = _category("scanners")
    r = _find(report, "skill_clean_agent")
    assert r.passed, r.message


@pytest.mark.unit
def test_scanner_evil_agent_blocked():
    report = _category("scanners")
    r = _find(report, "skill_evil_agent")
    assert r.passed, r.message


@pytest.mark.unit
def test_scanner_syntax_error_handled():
    report = _category("scanners")
    r = _find(report, "skill_syntax_error")
    assert r.passed, r.message


@pytest.mark.unit
def test_scanner_mcp_importable():
    report = _category("scanners")
    r = _find(report, "mcp_scanner")
    assert r.passed, r.message


@pytest.mark.unit
def test_scanner_dataflow_importable():
    report = _category("scanners")
    r = _find(report, "dataflow_tracer")
    assert r.passed, r.message


# ---------------------------------------------------------------------------
# Artifact store checks
# ---------------------------------------------------------------------------

@pytest.mark.unit
def test_store_write_read_roundtrip():
    report = _category("store")
    r = _find(report, "write_read_roundtrip")
    assert r.passed, r.message


@pytest.mark.unit
def test_store_index_consistent_no_store(tmp_path, monkeypatch):
    """When no production store exists the check passes gracefully."""
    monkeypatch.chdir(tmp_path)
    from agenticqa.monitoring.integrity_checker import _check_store_index_consistent
    ok, msg = _check_store_index_consistent()
    assert ok


# ---------------------------------------------------------------------------
# Provenance checks
# ---------------------------------------------------------------------------

@pytest.mark.unit
def test_provenance_sign_verify():
    report = _category("provenance")
    r = _find(report, "sign_verify_roundtrip")
    assert r.passed, r.message


# ---------------------------------------------------------------------------
# Ingest pipeline checks
# ---------------------------------------------------------------------------

@pytest.mark.unit
def test_ingest_skill_scan():
    report = _category("ingest")
    r = _find(report, "ingest_skill_scan")
    assert r.passed, r.message


@pytest.mark.unit
def test_ingest_mcp_scan():
    report = _category("ingest")
    r = _find(report, "ingest_mcp_scan")
    assert r.passed, r.message


# ---------------------------------------------------------------------------
# Full check_all()
# ---------------------------------------------------------------------------

@pytest.mark.unit
def test_check_all_returns_report():
    report = SystemIntegrityChecker().check_all()
    assert isinstance(report, IntegrityReport)
    assert len(report.checks) == 17  # update if checks are added


@pytest.mark.unit
def test_check_all_to_dict_shape():
    report = SystemIntegrityChecker().check_all()
    d = report.to_dict()
    assert "timestamp" in d
    assert "passed" in d
    assert "checks" in d
    assert isinstance(d["checks"], list)
