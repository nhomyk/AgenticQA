"""Unit tests for agenticqa.report — @pytest.mark.unit"""
import json
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock

from agenticqa.report.generator import (
    ReportGenerator,
    RepoScanResult,
    ScanReport,
    _risk_label,
    _render_markdown,
    _generate_recommendations,
    _get_notable_findings,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _mock_scan_repo(repo_path: str) -> dict:
    """Return fake scanner results for testing."""
    return {
        "architecture": {
            "status": "ok",
            "elapsed_s": 0.5,
            "result": {
                "total_findings": 10,
                "files_scanned": 50,
                "attack_surface_score": 3.5,
                "categories": {"SHELL_EXEC": 2, "EXTERNAL_HTTP": 8},
                "severity_counts": {"critical": 2, "high": 8},
                "critical_count": 2,
                "untested_count": 3,
            },
        },
        "prompt_injection": {
            "status": "ok",
            "elapsed_s": 0.2,
            "result": {
                "total_findings": 2,
                "risk_score": 0.7,
                "critical": 1,
            },
        },
        "ai_act": {
            "status": "ok",
            "elapsed_s": 0.1,
            "result": {
                "risk_category": "high_risk",
                "conformity_score": 0.75,
                "annex_iii": ["employment"],
                "findings_count": 4,
                "missing": 1,
            },
        },
        "data_flow": {
            "status": "ok",
            "elapsed_s": 0.3,
            "result": {
                "total_findings": 5,
                "files_scanned": 20,
                "risk_score": 0.8,
            },
        },
        "shadow_ai": {
            "status": "ok",
            "elapsed_s": 0.1,
            "result": {
                "has_shadow_ai": False,
                "total_findings": 0,
                "providers_found": [],
                "files_scanned": 50,
            },
        },
    }


def _make_repo_result(name: str = "test-repo", **overrides) -> RepoScanResult:
    scanners = _mock_scan_repo(f"/fake/{name}")
    scanners.update(overrides)
    return RepoScanResult(
        repo_path=f"/fake/{name}",
        repo_name=name,
        scanners=scanners,
        elapsed_s=1.2,
    )


# ---------------------------------------------------------------------------
# RepoScanResult
# ---------------------------------------------------------------------------

@pytest.mark.unit
class TestRepoScanResult:
    def test_total_findings(self):
        r = _make_repo_result()
        # architecture=10 + prompt_injection=2 + ai_act=4 + data_flow=5 + shadow_ai=0 = 21
        assert r.total_findings == 21

    def test_total_critical(self):
        r = _make_repo_result()
        # prompt_injection has critical=1
        assert r.total_critical == 1

    def test_scanners_ok(self):
        r = _make_repo_result()
        assert r.scanners_ok == 5

    def test_scanners_failed(self):
        r = _make_repo_result()
        assert r.scanners_failed == 0

    def test_failed_scanner_counted(self):
        r = _make_repo_result(
            broken_scanner={"status": "error", "error": "boom"}
        )
        assert r.scanners_failed == 1
        assert r.scanners_ok == 5


# ---------------------------------------------------------------------------
# ScanReport
# ---------------------------------------------------------------------------

@pytest.mark.unit
class TestScanReport:
    def test_to_dict_structure(self):
        report = ScanReport(
            repos=[_make_repo_result()],
            generated_at="2026-03-03 12:00:00 UTC",
            total_elapsed_s=1.5,
        )
        d = report.to_dict()
        assert d["generated_at"] == "2026-03-03 12:00:00 UTC"
        assert len(d["repos"]) == 1
        assert d["repos"][0]["repo_name"] == "test-repo"
        assert d["repos"][0]["total_findings"] == 21

    def test_to_json_valid(self):
        report = ScanReport(
            repos=[_make_repo_result()],
            generated_at="2026-03-03 12:00:00 UTC",
            total_elapsed_s=1.5,
        )
        parsed = json.loads(report.to_json())
        assert "repos" in parsed
        assert parsed["total_elapsed_s"] == 1.5

    def test_to_markdown_contains_sections(self):
        report = ScanReport(
            repos=[_make_repo_result("alpha"), _make_repo_result("beta")],
            generated_at="2026-03-03 12:00:00 UTC",
            total_elapsed_s=2.5,
        )
        md = report.to_markdown()
        assert "# AgenticQA Security Scan Report" in md
        assert "## Executive Summary" in md
        assert "## Cross-Repository Comparison" in md
        assert "## alpha" in md
        assert "## beta" in md
        assert "## Recommendations" in md
        assert "## Methodology" in md


# ---------------------------------------------------------------------------
# Risk label
# ---------------------------------------------------------------------------

@pytest.mark.unit
class TestRiskLabel:
    def test_critical(self):
        assert _risk_label(10, 100) == "CRITICAL"

    def test_high(self):
        assert _risk_label(5, 20) == "HIGH"

    def test_medium(self):
        assert _risk_label(0, 60) == "MEDIUM"

    def test_low(self):
        assert _risk_label(0, 10) == "LOW"


# ---------------------------------------------------------------------------
# Notable findings
# ---------------------------------------------------------------------------

@pytest.mark.unit
class TestNotableFindings:
    def test_architecture_attack_surface(self):
        r = _make_repo_result()
        # attack_surface_score is 3.5, below threshold (5)
        notes = _get_notable_findings(r)
        arch_notes = [n for n in notes if "Architecture" in n and "attack surface" in n]
        assert len(arch_notes) == 0

    def test_elevated_architecture_flagged(self):
        r = _make_repo_result()
        r.scanners["architecture"]["result"]["attack_surface_score"] = 8.0
        notes = _get_notable_findings(r)
        arch_notes = [n for n in notes if "attack surface" in n]
        assert len(arch_notes) == 1

    def test_prompt_injection_critical_flagged(self):
        r = _make_repo_result()
        notes = _get_notable_findings(r)
        pi_notes = [n for n in notes if "Prompt Injection" in n]
        assert len(pi_notes) == 1

    def test_eu_ai_act_missing_flagged(self):
        r = _make_repo_result()
        notes = _get_notable_findings(r)
        ai_notes = [n for n in notes if "EU AI Act" in n]
        assert len(ai_notes) == 1

    def test_shadow_ai_not_flagged_when_clean(self):
        r = _make_repo_result()
        notes = _get_notable_findings(r)
        shadow_notes = [n for n in notes if "Shadow AI" in n]
        assert len(shadow_notes) == 0

    def test_shadow_ai_flagged_when_present(self):
        r = _make_repo_result()
        r.scanners["shadow_ai"]["result"]["has_shadow_ai"] = True
        r.scanners["shadow_ai"]["result"]["providers_found"] = ["openai"]
        notes = _get_notable_findings(r)
        shadow_notes = [n for n in notes if "Shadow AI" in n]
        assert len(shadow_notes) == 1


# ---------------------------------------------------------------------------
# Recommendations
# ---------------------------------------------------------------------------

@pytest.mark.unit
class TestRecommendations:
    def test_untested_areas_recommendation(self):
        report = ScanReport(repos=[_make_repo_result()])
        recs = _generate_recommendations(report)
        arch_recs = [r for r in recs if "untested" in r.lower()]
        assert len(arch_recs) == 1

    def test_prompt_injection_recommendation(self):
        report = ScanReport(repos=[_make_repo_result()])
        recs = _generate_recommendations(report)
        pi_recs = [r for r in recs if "prompt injection" in r.lower()]
        assert len(pi_recs) == 1

    def test_ai_act_recommendation(self):
        report = ScanReport(repos=[_make_repo_result()])
        recs = _generate_recommendations(report)
        ai_recs = [r for r in recs if "eu ai act" in r.lower()]
        assert len(ai_recs) == 1

    def test_no_recs_for_clean_repo(self):
        r = RepoScanResult(
            repo_path="/fake/clean",
            repo_name="clean",
            scanners={
                "architecture": {"status": "ok", "result": {"total_findings": 0, "untested_count": 0}},
                "prompt_injection": {"status": "ok", "result": {"total_findings": 0, "critical": 0}},
            },
        )
        report = ScanReport(repos=[r])
        recs = _generate_recommendations(report)
        assert len(recs) == 0


# ---------------------------------------------------------------------------
# Markdown rendering
# ---------------------------------------------------------------------------

@pytest.mark.unit
class TestMarkdownRendering:
    def test_contains_repo_table(self):
        report = ScanReport(
            repos=[_make_repo_result("repo-a")],
            generated_at="2026-03-03",
        )
        md = _render_markdown(report)
        assert "| repo-a |" in md

    def test_contains_scanner_table(self):
        report = ScanReport(
            repos=[_make_repo_result()],
            generated_at="2026-03-03",
        )
        md = _render_markdown(report)
        assert "| architecture |" in md
        assert "| prompt_injection |" in md

    def test_failed_scanner_shown(self):
        r = _make_repo_result(
            broken={"status": "error", "error": "Import failed"}
        )
        report = ScanReport(repos=[r], generated_at="2026-03-03")
        md = _render_markdown(report)
        assert "FAIL" in md
        assert "Import failed" in md

    def test_methodology_present(self):
        report = ScanReport(repos=[], generated_at="2026-03-03")
        md = _render_markdown(report)
        assert "static analysis" in md

    def test_highest_risk_shown(self):
        r1 = _make_repo_result("safe")
        r1.scanners["prompt_injection"]["result"]["critical"] = 0
        r2 = _make_repo_result("risky")
        r2.scanners["prompt_injection"]["result"]["critical"] = 5
        report = ScanReport(repos=[r1, r2], generated_at="2026-03-03")
        md = _render_markdown(report)
        assert "risky" in md.split("Highest-risk")[1].split("\n")[0]


# ---------------------------------------------------------------------------
# ReportGenerator (with mocked scan_repo)
# ---------------------------------------------------------------------------

@pytest.mark.unit
class TestReportGenerator:
    @patch("agenticqa.report.generator.ReportGenerator._scan_single_repo")
    def test_scan_repos_returns_report(self, mock_scan):
        mock_scan.return_value = _make_repo_result()
        gen = ReportGenerator()
        report = gen.scan_repos(["/fake/repo"])
        assert len(report.repos) == 1
        assert report.generated_at != ""
        assert report.total_elapsed_s >= 0

    @patch("agenticqa.report.generator.ReportGenerator._scan_single_repo")
    def test_scan_multiple_repos(self, mock_scan):
        mock_scan.return_value = _make_repo_result()
        gen = ReportGenerator()
        report = gen.scan_repos(["/fake/a", "/fake/b", "/fake/c"])
        assert len(report.repos) == 3

    def test_nonexistent_path_handled(self):
        gen = ReportGenerator()
        report = gen.scan_repos(["/nonexistent/path/xyz"])
        assert len(report.repos) == 1
        assert "_error" in report.repos[0].scanners

    @patch("agenticqa.report.generator.ReportGenerator._scan_single_repo")
    def test_markdown_output_valid(self, mock_scan):
        mock_scan.return_value = _make_repo_result()
        gen = ReportGenerator()
        report = gen.scan_repos(["/fake/repo"])
        md = report.to_markdown()
        assert "# AgenticQA Security Scan Report" in md

    @patch("agenticqa.report.generator.ReportGenerator._scan_single_repo")
    def test_json_output_valid(self, mock_scan):
        mock_scan.return_value = _make_repo_result()
        gen = ReportGenerator()
        report = gen.scan_repos(["/fake/repo"])
        parsed = json.loads(report.to_json())
        assert "repos" in parsed
