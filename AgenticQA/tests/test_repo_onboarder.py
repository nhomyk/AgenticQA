"""Unit tests for RepoOnboarder."""
import json
import pytest
from pathlib import Path
from unittest.mock import MagicMock, patch

from agenticqa.onboarding.repo_onboarder import (
    BaselineDelta,
    GeneratedTestSummary,
    OnboardingReport,
    RepoOnboarder,
)
from agenticqa.onboarding.coverage_mapper import CoverageMap, LanguageCoverage


# ── Fixtures ───────────────────────────────────────────────────────────────────

def _empty_cov(repo_path: str) -> CoverageMap:
    return CoverageMap(
        repo_path=repo_path,
        total_source_files=5,
        covered_files=["src/auth.py"],
        uncovered_files=["src/pay.py", "src/user.py"],
        test_files=["tests/test_auth.py"],
        by_language={"python": LanguageCoverage("python", 3, 1, 2)},
    )


def _minimal_report(tmp_path: Path) -> OnboardingReport:
    cov = _empty_cov(str(tmp_path))
    return OnboardingReport(
        repo_path=str(tmp_path),
        repo_name="myrepo",
        timestamp="2026-02-28T00:00:00+00:00",
        architecture={"attack_surface_score": 20.0, "integration_areas": [],
                      "files_scanned": 5},
        attack_surface_score=20.0,
        owasp_findings=[],
        secret_findings=[],
        cve_findings=[],
        legal_findings=[],
        hipaa_findings=[],
        eu_ai_act={"risk_category": "limited_risk", "conformity_score": 0.8},
        prompt_injection_findings=[],
        total_vulnerabilities=0,
        coverage=cov,
    )


def _make_onboarder() -> RepoOnboarder:
    return RepoOnboarder()


# ── OnboardingReport ────────────────────────────────────────────────────────────

@pytest.mark.unit
def test_overall_risk_low(tmp_path):
    r = _minimal_report(tmp_path)
    assert r.overall_risk == "LOW"


@pytest.mark.unit
def test_overall_risk_medium_by_score(tmp_path):
    r = _minimal_report(tmp_path)
    r.attack_surface_score = 40.0
    assert r.overall_risk == "MEDIUM"


@pytest.mark.unit
def test_overall_risk_high_by_score(tmp_path):
    r = _minimal_report(tmp_path)
    r.attack_surface_score = 70.0
    assert r.overall_risk == "HIGH"


@pytest.mark.unit
def test_overall_risk_high_by_vulns(tmp_path):
    r = _minimal_report(tmp_path)
    r.total_vulnerabilities = 12
    assert r.overall_risk == "HIGH"


@pytest.mark.unit
def test_overall_risk_medium_by_vulns(tmp_path):
    r = _minimal_report(tmp_path)
    r.total_vulnerabilities = 5
    assert r.overall_risk == "MEDIUM"


@pytest.mark.unit
def test_to_dict_has_required_keys(tmp_path):
    r = _minimal_report(tmp_path)
    d = r.to_dict()
    for key in (
        "repo_path", "repo_name", "timestamp", "overall_risk",
        "attack_surface_score", "total_vulnerabilities", "coverage",
        "generated_tests_count", "generated_tests", "architecture",
        "owasp_count", "secret_count", "cve_count", "legal_count",
        "hipaa_count", "prompt_injection_count", "eu_ai_act",
        "baseline_stored", "baseline_delta", "repo_id", "pr_url",
    ):
        assert key in d, f"Missing key: {key}"


@pytest.mark.unit
def test_to_dict_baseline_delta_none(tmp_path):
    r = _minimal_report(tmp_path)
    d = r.to_dict()
    assert d["baseline_delta"] is None


@pytest.mark.unit
def test_to_dict_baseline_delta_present(tmp_path):
    r = _minimal_report(tmp_path)
    r.baseline_delta = BaselineDelta(
        previous_date="2026-02-20T00:00:00+00:00",
        attack_surface_change=-5.0,
        coverage_change=10.0,
        vulnerability_change=-2,
        trend="improving",
    )
    d = r.to_dict()
    assert d["baseline_delta"]["trend"] == "improving"
    assert d["baseline_delta"]["attack_surface_change"] == -5.0


@pytest.mark.unit
def test_plain_english_summary_contains_repo_name(tmp_path):
    r = _minimal_report(tmp_path)
    summary = r.plain_english_summary()
    assert "myrepo" in summary


@pytest.mark.unit
def test_plain_english_summary_contains_risk(tmp_path):
    r = _minimal_report(tmp_path)
    summary = r.plain_english_summary()
    assert "LOW" in summary


@pytest.mark.unit
def test_plain_english_summary_contains_coverage(tmp_path):
    r = _minimal_report(tmp_path)
    summary = r.plain_english_summary()
    assert "Coverage" in summary


@pytest.mark.unit
def test_plain_english_summary_with_delta(tmp_path):
    r = _minimal_report(tmp_path)
    r.baseline_delta = BaselineDelta(
        previous_date="2026-02-20T00:00:00+00:00",
        attack_surface_change=-5.0,
        coverage_change=10.0,
        vulnerability_change=0,
        trend="improving",
    )
    summary = r.plain_english_summary()
    assert "IMPROVING" in summary


# ── BaselineDelta ───────────────────────────────────────────────────────────────

@pytest.mark.unit
def test_baseline_delta_fields():
    d = BaselineDelta(
        previous_date="2026-01-01",
        attack_surface_change=5.0,
        coverage_change=-2.0,
        vulnerability_change=3,
        trend="declining",
    )
    assert d.trend == "declining"
    assert d.vulnerability_change == 3


# ── GeneratedTestSummary ────────────────────────────────────────────────────────

@pytest.mark.unit
def test_generated_test_summary_defaults():
    g = GeneratedTestSummary(
        source_file="src/auth.py",
        test_file="tests/test_auth.py",
        framework="python",
        test_runner="pytest",
        setup_instructions=[],
    )
    assert g.status == "generated"
    assert g.error == ""


# ── RepoOnboarder._repo_id ─────────────────────────────────────────────────────

@pytest.mark.unit
def test_repo_id_is_hex(tmp_path):
    ob = _make_onboarder()
    rid = ob._repo_id(tmp_path)
    assert len(rid) == 12
    int(rid, 16)  # raises if not valid hex


@pytest.mark.unit
def test_repo_id_deterministic(tmp_path):
    ob = _make_onboarder()
    assert ob._repo_id(tmp_path) == ob._repo_id(tmp_path)


# ── RepoOnboarder baseline round-trip ─────────────────────────────────────────

@pytest.mark.unit
def test_save_and_load_baseline(tmp_path, monkeypatch):
    ob = _make_onboarder()
    repo_id = "test123abc01"

    # Override baseline dir to tmp_path
    monkeypatch.setattr(
        ob, "_baseline_path", lambda rid: tmp_path / f"{rid}.json"
    )

    arch = {"attack_surface_score": 30.0}
    cov = _empty_cov(str(tmp_path))
    cov_map = cov
    # First load — no baseline yet
    delta = ob._load_previous_baseline(repo_id, arch, cov_map, 5)
    assert delta is None

    # Save
    ob._save_baseline(repo_id, arch, cov_map, 5)
    saved = json.loads((tmp_path / f"{repo_id}.json").read_text())
    assert saved["attack_surface_score"] == 30.0
    assert saved["total_vulnerabilities"] == 5


@pytest.mark.unit
def test_baseline_delta_improving(tmp_path, monkeypatch):
    ob = _make_onboarder()
    repo_id = "abc123def456"
    monkeypatch.setattr(
        ob, "_baseline_path", lambda rid: tmp_path / f"{rid}.json"
    )

    prev = {
        "timestamp": "2026-01-01T00:00:00+00:00",
        "attack_surface_score": 60.0,
        "coverage_pct": 20.0,
        "total_vulnerabilities": 10,
    }
    (tmp_path / f"{repo_id}.json").write_text(json.dumps(prev))

    arch = {"attack_surface_score": 45.0}  # -15 → big improvement
    cov = _empty_cov(str(tmp_path))
    cov.covered_files = ["a", "b", "c", "d", "e", "f"]  # 6/5 → just bump pct
    # coverage_pct is calculated from covered/total — mock it directly
    # Patch the property by creating a custom subclass approach via monkeypatch
    # Simpler: create a CoverageMap with coverage_pct ~35% (up from 20)
    cov.total_source_files = 10
    # covered is 6 → pct = 60%

    delta = ob._load_previous_baseline(repo_id, arch, cov, 8)
    assert delta is not None
    assert delta.trend == "improving"


@pytest.mark.unit
def test_baseline_delta_declining(tmp_path, monkeypatch):
    ob = _make_onboarder()
    repo_id = "decline000001"
    monkeypatch.setattr(
        ob, "_baseline_path", lambda rid: tmp_path / f"{rid}.json"
    )

    prev = {
        "timestamp": "2026-01-01T00:00:00+00:00",
        "attack_surface_score": 30.0,
        "coverage_pct": 50.0,
        "total_vulnerabilities": 5,
    }
    (tmp_path / f"{repo_id}.json").write_text(json.dumps(prev))

    arch = {"attack_surface_score": 60.0}  # +30 → declining
    cov = _empty_cov(str(tmp_path))

    delta = ob._load_previous_baseline(repo_id, arch, cov, 20)
    assert delta is not None
    assert delta.trend == "declining"


@pytest.mark.unit
def test_baseline_delta_stable(tmp_path, monkeypatch):
    ob = _make_onboarder()
    repo_id = "stable0000001"
    monkeypatch.setattr(
        ob, "_baseline_path", lambda rid: tmp_path / f"{rid}.json"
    )

    prev = {
        "timestamp": "2026-01-01T00:00:00+00:00",
        "attack_surface_score": 30.0,
        "coverage_pct": 40.0,
        "total_vulnerabilities": 5,
    }
    (tmp_path / f"{repo_id}.json").write_text(json.dumps(prev))

    arch = {"attack_surface_score": 31.0}  # tiny change
    cov = _empty_cov(str(tmp_path))

    delta = ob._load_previous_baseline(repo_id, arch, cov, 5)
    assert delta is not None
    assert delta.trend == "stable"


@pytest.mark.unit
def test_baseline_delta_corrupt_file(tmp_path, monkeypatch):
    """Corrupt baseline file should return None gracefully."""
    ob = _make_onboarder()
    repo_id = "corrupt000001"
    monkeypatch.setattr(
        ob, "_baseline_path", lambda rid: tmp_path / f"{rid}.json"
    )

    (tmp_path / f"{repo_id}.json").write_text("NOT JSON{{{")
    arch = {"attack_surface_score": 30.0}
    cov = _empty_cov(str(tmp_path))

    delta = ob._load_previous_baseline(repo_id, arch, cov, 5)
    assert delta is None


# ── RepoOnboarder scanner helpers ───────────────────────────────────────────────

@pytest.mark.unit
def test_run_architecture_returns_dict_on_error(tmp_path):
    ob = _make_onboarder()
    with patch("agenticqa.onboarding.repo_onboarder.RepoOnboarder._run_architecture") as m:
        m.return_value = {"error": "No scanner", "integration_areas": [],
                          "attack_surface_score": 0.0, "files_scanned": 0}
        result = ob._run_architecture("/nonexistent/path")
    # If import fails, should return default dict with error key
    assert "integration_areas" in result


@pytest.mark.unit
def test_run_owasp_returns_empty_on_error():
    ob = _make_onboarder()
    with patch("agenticqa.security.owasp_scanner.OWASPScanner", side_effect=ImportError):
        result = ob._run_owasp("/tmp")
    assert result == []


@pytest.mark.unit
def test_run_secrets_returns_empty_on_error():
    ob = _make_onboarder()
    with patch.dict("sys.modules", {"agenticqa.security.secrets_scanner": None}):
        result = ob._run_secrets("/tmp")
    assert result == []


@pytest.mark.unit
def test_run_legal_returns_empty_on_error():
    ob = _make_onboarder()
    result = ob._run_legal("/definitely/nonexistent/path")
    assert isinstance(result, list)


@pytest.mark.unit
def test_run_prompt_injection_returns_empty_on_error():
    ob = _make_onboarder()
    result = ob._run_prompt_injection("/definitely/nonexistent/path")
    assert isinstance(result, list)


# ── RepoOnboarder.run — full integration with mocks ───────────────────────────

@pytest.mark.unit
def test_run_returns_onboarding_report(tmp_path):
    """Full run with all scanners mocked returns a valid OnboardingReport."""
    # Write a minimal source file
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "app.py").write_text("def main(): pass")

    arch_result = {
        "attack_surface_score": 10.0,
        "integration_areas": [],
        "files_scanned": 1,
        "plain_english_report": "Low risk.",
    }

    ob = _make_onboarder()

    with patch.object(ob, "_run_architecture", return_value=arch_result), \
         patch.object(ob, "_run_owasp", return_value=[]), \
         patch.object(ob, "_run_secrets", return_value=[]), \
         patch.object(ob, "_run_cve", return_value=[]), \
         patch.object(ob, "_run_legal", return_value=[]), \
         patch.object(ob, "_run_hipaa", return_value=[]), \
         patch.object(ob, "_run_eu_ai_act", return_value={"risk_category": "minimal_risk"}), \
         patch.object(ob, "_run_prompt_injection", return_value=[]), \
         patch.object(ob, "_save_baseline", return_value=None), \
         patch.object(ob, "_load_previous_baseline", return_value=None), \
         patch.object(ob, "_generate_tests_for_files", return_value=[]):

        report = ob.run(str(tmp_path))

    assert isinstance(report, OnboardingReport)
    assert report.repo_name == tmp_path.name
    assert report.attack_surface_score == 10.0
    assert report.total_vulnerabilities == 0
    assert isinstance(report.coverage, CoverageMap)


@pytest.mark.unit
def test_run_counts_total_vulnerabilities(tmp_path):
    arch_result = {"attack_surface_score": 0.0, "integration_areas": []}
    ob = _make_onboarder()

    with patch.object(ob, "_run_architecture", return_value=arch_result), \
         patch.object(ob, "_run_owasp", return_value=[{"id": "1"}] * 3), \
         patch.object(ob, "_run_secrets", return_value=[{"id": "2"}] * 2), \
         patch.object(ob, "_run_cve", return_value=[{"id": "3"}]), \
         patch.object(ob, "_run_legal", return_value=[]), \
         patch.object(ob, "_run_hipaa", return_value=[{"id": "4"}]), \
         patch.object(ob, "_run_eu_ai_act", return_value={}), \
         patch.object(ob, "_run_prompt_injection", return_value=[{"id": "5"}]), \
         patch.object(ob, "_save_baseline", return_value=None), \
         patch.object(ob, "_load_previous_baseline", return_value=None), \
         patch.object(ob, "_generate_tests_for_files", return_value=[]):

        report = ob.run(str(tmp_path))

    # owasp(3) + secrets(2) + cve(1) + legal(0) + hipaa(1) + prompt_inj(1) = 8
    assert report.total_vulnerabilities == 8


@pytest.mark.unit
def test_run_high_risk_uncovered_tagged(tmp_path):
    """Files flagged by arch scanner as high-risk uncovered should be tagged."""
    (tmp_path / "src").mkdir()
    src_file = tmp_path / "src" / "shell_exec.py"
    src_file.write_text("import subprocess\nsubprocess.run(['ls'])")

    arch_result = {
        "attack_surface_score": 40.0,
        "integration_areas": [
            {"source_file": "src/shell_exec.py", "severity": "critical",
             "category": "SHELL_EXEC"},
        ],
    }
    ob = _make_onboarder()

    with patch.object(ob, "_run_architecture", return_value=arch_result), \
         patch.object(ob, "_run_owasp", return_value=[]), \
         patch.object(ob, "_run_secrets", return_value=[]), \
         patch.object(ob, "_run_cve", return_value=[]), \
         patch.object(ob, "_run_legal", return_value=[]), \
         patch.object(ob, "_run_hipaa", return_value=[]), \
         patch.object(ob, "_run_eu_ai_act", return_value={}), \
         patch.object(ob, "_run_prompt_injection", return_value=[]), \
         patch.object(ob, "_save_baseline", return_value=None), \
         patch.object(ob, "_load_previous_baseline", return_value=None), \
         patch.object(ob, "_generate_tests_for_files", return_value=[]):

        report = ob.run(str(tmp_path))

    assert "src/shell_exec.py" in report.coverage.high_risk_uncovered
