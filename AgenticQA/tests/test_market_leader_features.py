"""Tests for market-leader features: auto-fix PR, scan trends, compliance reports,
benchmarking, custom rules, Slack/Teams notifications."""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))
sys.path.insert(0, str(Path(__file__).parent.parent))


# ── Helper: fake scan output ────────────────────────────────────────────────

def _fake_scan_output(findings=5, critical=1, arch_score=45.0):
    return {
        "summary": {
            "repo_path": "/tmp/test-repo",
            "scanners_ok": 13,
            "scanners_failed": 0,
            "total_findings": findings,
            "total_critical": critical,
            "total_elapsed_s": 2.5,
            "risk_level": "high" if critical > 5 else ("medium" if findings > 10 else "low"),
            "build_info": {"languages": ["python", "typescript"]},
        },
        "scanners": {
            "architecture": {
                "status": "ok", "elapsed_s": 1.0,
                "result": {
                    "total_findings": 3, "files_scanned": 100,
                    "attack_surface_score": arch_score,
                    "categories": {"SHELL_EXEC": 1, "ENV_SECRETS": 2},
                    "severity_counts": {"critical": 0, "high": 2, "medium": 1},
                    "critical_count": 0, "untested_count": 1,
                },
            },
            "legal_risk": {
                "status": "ok", "elapsed_s": 0.5,
                "result": {
                    "total_findings": 2, "risk_score": 0.4, "critical": critical,
                    "findings": [
                        {"rule_id": "HARDCODED_CREDENTIAL", "file": "config.py",
                         "line": 15, "severity": "critical"},
                    ],
                },
            },
            "hipaa": {
                "status": "ok", "elapsed_s": 0.3,
                "result": {"total_findings": 0, "risk_score": 0.0, "critical": 0},
            },
            "ai_act": {
                "status": "ok", "elapsed_s": 0.4,
                "result": {
                    "risk_category": "high_risk", "conformity_score": 0.55,
                    "annex_iii": True, "findings_count": 4, "missing": 2,
                },
            },
            "prompt_injection": {
                "status": "ok", "elapsed_s": 0.2,
                "result": {"total_findings": 0, "risk_score": 0.0, "critical": 0},
            },
            "trust_graph": {
                "status": "ok", "elapsed_s": 0.3,
                "result": {
                    "frameworks": [], "agents": 0, "edges": 0,
                    "findings_count": 0, "has_cycles": False, "risk_score": 0.0,
                },
            },
            "ai_model_sbom": {
                "status": "ok", "elapsed_s": 0.2,
                "result": {"providers": ["anthropic"], "unique_models": 1,
                           "risk_score": 0.1, "license_violations": 0},
            },
            "shadow_ai": {
                "status": "ok", "elapsed_s": 0.1,
                "result": {"has_shadow_ai": False, "total_findings": 0,
                           "providers_found": [], "files_scanned": 50},
            },
            "cve_reachability": {
                "status": "ok", "elapsed_s": 0.3,
                "result": {"python_cves": 0, "python_reachable": 0,
                           "python_error": None, "js_cves": 0,
                           "js_reachable": 0, "js_error": None},
            },
            "mcp_security": {
                "status": "ok", "elapsed_s": 0.2,
                "result": {"total_findings": 0, "files_scanned": 50,
                           "risk_score": 0.0, "categories": {}},
            },
            "data_flow": {
                "status": "ok", "elapsed_s": 0.2,
                "result": {"total_findings": 0, "files_scanned": 50, "risk_score": 0.0},
            },
            "bias_detection": {
                "status": "ok", "elapsed_s": 0.1,
                "result": {"total_findings": 0, "max_risk_score": 0.0,
                           "categories_flagged": []},
            },
            "injection_guard": {
                "status": "ok", "elapsed_s": 0.1,
                "result": {"total_findings": 0, "unsafe_files": 0, "critical": 0},
            },
        },
    }


# ── Autonomous Fix PR tests ────────────────────────────────────────────────

@pytest.mark.unit
class TestAutoFixPR:
    def test_extract_fixable_findings(self):
        from agenticqa.remediation.auto_fix_pr import extract_fixable_findings
        patches = extract_fixable_findings(_fake_scan_output())
        assert len(patches) > 0
        # Should find HARDCODED_CREDENTIAL from legal_risk
        rule_ids = [p.rule_id for p in patches]
        assert "HARDCODED_CREDENTIAL" in rule_ids

    def test_extract_with_shell_exec(self):
        from agenticqa.remediation.auto_fix_pr import extract_fixable_findings
        output = _fake_scan_output()
        patches = extract_fixable_findings(output)
        # Architecture SHELL_EXEC should generate a patch
        rule_ids = [p.rule_id for p in patches]
        assert "SHELL_EXEC" in rule_ids

    def test_extract_empty_scan(self):
        from agenticqa.remediation.auto_fix_pr import extract_fixable_findings
        patches = extract_fixable_findings({"scanners": {}})
        assert patches == []

    def test_generate_fix_pr_dry_run(self):
        from agenticqa.remediation.auto_fix_pr import generate_fix_pr
        result = generate_fix_pr(
            repo_path="/tmp/nonexistent",
            scan_results=_fake_scan_output(),
            dry_run=True,
        )
        assert result.patches_generated > 0
        assert result.pr_url == ""
        assert result.patches_applied == 0  # dry run doesn't apply

    def test_fix_patch_severity(self):
        from agenticqa.remediation.auto_fix_pr import extract_fixable_findings
        patches = extract_fixable_findings(_fake_scan_output())
        severities = set(p.severity for p in patches)
        assert "critical" in severities or "high" in severities

    def test_fix_pr_result_to_dict(self):
        from agenticqa.remediation.auto_fix_pr import FixPRResult, FixPatch
        result = FixPRResult(
            patches_generated=3, patches_applied=2, pr_url="https://github.com/test/pr/1",
            patches=[FixPatch(file="a.py", line=1, scanner="test", rule_id="T1",
                             severity="high", description="test", fix_description="fix it")],
        )
        d = result.to_dict()
        assert d["patches_generated"] == 3
        assert d["patches_applied"] == 2
        assert len(d["patches"]) == 1

    def test_shadow_ai_fixes(self):
        from agenticqa.remediation.auto_fix_pr import extract_fixable_findings
        output = _fake_scan_output()
        output["scanners"]["shadow_ai"]["result"] = {
            "has_shadow_ai": True, "total_findings": 2,
            "providers_found": ["openai", "anthropic"], "files_scanned": 50,
        }
        patches = extract_fixable_findings(output)
        shadow_patches = [p for p in patches if p.scanner == "shadow_ai"]
        assert len(shadow_patches) >= 2


# ── Scan Trend tests ───────────────────────────────────────────────────────

@pytest.mark.unit
class TestScanTrend:
    def test_record_and_history(self, tmp_path):
        from agenticqa.monitoring.scan_trend import ScanTrendAggregator
        agg = ScanTrendAggregator(history_file=str(tmp_path / "history.jsonl"))
        agg.record(_fake_scan_output(5, 1), repo_id="test/repo")
        agg.record(_fake_scan_output(3, 0), repo_id="test/repo")
        history = agg.history(repo_id="test/repo")
        assert len(history) == 2
        assert history[0]["total_findings"] == 5
        assert history[1]["total_findings"] == 3

    def test_trend_improving(self, tmp_path):
        from agenticqa.monitoring.scan_trend import ScanTrendAggregator
        agg = ScanTrendAggregator(history_file=str(tmp_path / "history.jsonl"))
        # Record worsening then improving
        for i in range(5):
            agg.record(_fake_scan_output(50 - i * 5, 5 - i), repo_id="test/repo")
        for i in range(5):
            agg.record(_fake_scan_output(10 - i, 0), repo_id="test/repo")
        trend = agg.trend(repo_id="test/repo")
        assert trend["direction"] == "improving"

    def test_trend_insufficient_data(self, tmp_path):
        from agenticqa.monitoring.scan_trend import ScanTrendAggregator
        agg = ScanTrendAggregator(history_file=str(tmp_path / "history.jsonl"))
        agg.record(_fake_scan_output(), repo_id="test/repo")
        trend = agg.trend(repo_id="test/repo")
        assert trend["direction"] == "insufficient_data"

    def test_org_rollup(self, tmp_path):
        from agenticqa.monitoring.scan_trend import ScanTrendAggregator
        agg = ScanTrendAggregator(history_file=str(tmp_path / "history.jsonl"))
        agg.record(_fake_scan_output(10, 2), repo_id="repo-a")
        agg.record(_fake_scan_output(5, 0), repo_id="repo-b")
        agg.record(_fake_scan_output(20, 5), repo_id="repo-c")
        rollup = agg.org_rollup()
        assert rollup["repos"] == 3
        assert rollup["total_scans"] == 3
        assert rollup["repos_with_critical"] == 2

    def test_history_filter_by_repo(self, tmp_path):
        from agenticqa.monitoring.scan_trend import ScanTrendAggregator
        agg = ScanTrendAggregator(history_file=str(tmp_path / "history.jsonl"))
        agg.record(_fake_scan_output(), repo_id="repo-a")
        agg.record(_fake_scan_output(), repo_id="repo-b")
        history_a = agg.history(repo_id="repo-a")
        assert len(history_a) == 1

    def test_empty_history(self, tmp_path):
        from agenticqa.monitoring.scan_trend import ScanTrendAggregator
        agg = ScanTrendAggregator(history_file=str(tmp_path / "nope.jsonl"))
        assert agg.history() == []


# ── Compliance Report tests ────────────────────────────────────────────────

@pytest.mark.unit
class TestComplianceReport:
    def test_generate_report(self):
        from agenticqa.compliance.report_generator import ComplianceReportGenerator
        gen = ComplianceReportGenerator()
        report = gen.generate(_fake_scan_output(), repo_id="test/repo")
        assert report.repo_id == "test/repo"
        assert len(report.sections) == 4  # hipaa, eu_ai_act, security, supply_chain
        assert 0 <= report.overall_score <= 1

    def test_report_to_markdown(self):
        from agenticqa.compliance.report_generator import ComplianceReportGenerator
        gen = ComplianceReportGenerator()
        report = gen.generate(_fake_scan_output())
        md = gen.to_markdown(report)
        assert "AgenticQA Compliance Report" in md
        assert "HIPAA" in md
        assert "EU AI Act" in md

    def test_report_to_html(self):
        from agenticqa.compliance.report_generator import ComplianceReportGenerator
        gen = ComplianceReportGenerator()
        report = gen.generate(_fake_scan_output())
        html = gen.to_html(report)
        assert "<html>" in html
        assert "AgenticQA" in html

    def test_report_to_dict(self):
        from agenticqa.compliance.report_generator import ComplianceReportGenerator
        gen = ComplianceReportGenerator()
        report = gen.generate(_fake_scan_output())
        d = report.to_dict()
        assert "sections" in d
        assert "overall_score" in d
        assert "overall_status" in d

    def test_hipaa_pass(self):
        from agenticqa.compliance.report_generator import ComplianceReportGenerator
        gen = ComplianceReportGenerator()
        report = gen.generate(_fake_scan_output(), frameworks=["hipaa"])
        hipaa = report.sections[0]
        assert hipaa.title == "HIPAA / PHI Protection"
        assert hipaa.status == "pass"

    def test_eu_ai_act_partial(self):
        from agenticqa.compliance.report_generator import ComplianceReportGenerator
        gen = ComplianceReportGenerator()
        report = gen.generate(_fake_scan_output(), frameworks=["eu_ai_act"])
        eu = report.sections[0]
        assert eu.title == "EU AI Act Compliance"
        assert eu.status == "partial"  # conformity_score=0.55

    def test_selective_frameworks(self):
        from agenticqa.compliance.report_generator import ComplianceReportGenerator
        gen = ComplianceReportGenerator()
        report = gen.generate(_fake_scan_output(), frameworks=["security"])
        assert len(report.sections) == 1
        assert report.sections[0].title == "Security Posture"


# ── Security Benchmarking tests ────────────────────────────────────────────

@pytest.mark.unit
class TestSecurityBenchmark:
    def test_benchmark_low_findings(self):
        from agenticqa.scoring.security_benchmark import benchmark_scan
        result = benchmark_scan(_fake_scan_output(findings=5, critical=0, arch_score=10))
        assert result.overall_percentile > 50
        assert result.grade in ("A+", "A", "B+", "B")

    def test_benchmark_high_findings(self):
        from agenticqa.scoring.security_benchmark import benchmark_scan
        result = benchmark_scan(_fake_scan_output(findings=10000, critical=200, arch_score=90))
        assert result.overall_percentile < 30
        assert result.grade in ("D", "F")

    def test_benchmark_comparison_text(self):
        from agenticqa.scoring.security_benchmark import benchmark_scan
        result = benchmark_scan(_fake_scan_output())
        assert "more secure than" in result.comparison_text
        assert "benchmark" in result.comparison_text

    def test_benchmark_to_dict(self):
        from agenticqa.scoring.security_benchmark import benchmark_scan
        result = benchmark_scan(_fake_scan_output())
        d = result.to_dict()
        assert "grade" in d
        assert "overall_percentile" in d
        assert "findings_percentile" in d

    def test_grade_scale(self):
        from agenticqa.scoring.security_benchmark import _grade
        assert _grade(95) == "A+"
        assert _grade(90) == "A"
        assert _grade(80) == "B+"
        assert _grade(50) == "C"
        assert _grade(30) == "F"


# ── Custom Rules tests ─────────────────────────────────────────────────────

@pytest.mark.unit
class TestCustomRules:
    def test_add_and_scan(self, tmp_path):
        from agenticqa.security.custom_rules import CustomRuleEngine, CustomRule
        # Create a test file
        (tmp_path / "app.py").write_text("import openai\nclient = openai.ChatCompletion.create()\n")
        engine = CustomRuleEngine()
        engine.add_rule(CustomRule(
            id="CORP-001", name="Direct OpenAI", description="Use AI gateway",
            severity="high", pattern=r"openai\.ChatCompletion",
            file_pattern="*.py", message="Use corp.ai.gateway",
        ))
        result = engine.scan(str(tmp_path))
        assert result.rules_loaded == 1
        assert result.rules_matched == 1
        assert result.total_findings == 1
        assert result.findings[0].rule_id == "CORP-001"
        assert result.findings[0].line == 2

    def test_save_and_load(self, tmp_path):
        from agenticqa.security.custom_rules import CustomRuleEngine, CustomRule
        engine = CustomRuleEngine()
        engine.add_rule(CustomRule(
            id="TEST-001", name="Test Rule", description="Testing",
            severity="medium", pattern=r"TODO",
        ))
        engine.save_to_repo(str(tmp_path))
        assert (tmp_path / ".agenticqa" / "custom_rules.json").exists()

        # Load in new engine
        engine2 = CustomRuleEngine()
        loaded = engine2.load_from_repo(str(tmp_path))
        assert loaded == 1
        assert engine2.rules[0].id == "TEST-001"

    def test_file_pattern_filter(self, tmp_path):
        from agenticqa.security.custom_rules import CustomRuleEngine, CustomRule
        (tmp_path / "app.py").write_text("openai.chat()")
        (tmp_path / "app.js").write_text("openai.chat()")
        engine = CustomRuleEngine()
        engine.add_rule(CustomRule(
            id="PY-001", name="Python Only", description="",
            severity="low", pattern=r"openai", file_pattern="*.py",
        ))
        result = engine.scan(str(tmp_path))
        # Should only find in .py file
        assert result.total_findings == 1
        assert result.findings[0].file.endswith(".py")

    def test_disabled_rule_skipped(self, tmp_path):
        from agenticqa.security.custom_rules import CustomRuleEngine, CustomRule
        (tmp_path / "app.py").write_text("openai.chat()")
        engine = CustomRuleEngine()
        engine.add_rule(CustomRule(
            id="DISABLED-001", name="Disabled", description="",
            severity="low", pattern=r"openai", enabled=False,
        ))
        result = engine.scan(str(tmp_path))
        assert result.total_findings == 0

    def test_multiple_rules(self, tmp_path):
        from agenticqa.security.custom_rules import CustomRuleEngine, CustomRule
        (tmp_path / "app.py").write_text("import openai\nos.system('ls')\n")
        engine = CustomRuleEngine()
        engine.add_rule(CustomRule(id="R1", name="R1", description="",
                                   severity="high", pattern=r"openai"))
        engine.add_rule(CustomRule(id="R2", name="R2", description="",
                                   severity="critical", pattern=r"os\.system"))
        result = engine.scan(str(tmp_path))
        assert result.rules_matched == 2
        assert result.total_findings == 2
        assert result.critical == 1

    def test_to_dict(self, tmp_path):
        from agenticqa.security.custom_rules import CustomRuleEngine, CustomRule
        (tmp_path / "test.py").write_text("pattern_match")
        engine = CustomRuleEngine()
        engine.add_rule(CustomRule(id="T1", name="T1", description="",
                                   severity="low", pattern=r"pattern_match"))
        result = engine.scan(str(tmp_path))
        d = result.to_dict()
        assert "rules_loaded" in d
        assert "findings" in d

    def test_load_nonexistent_file(self, tmp_path):
        from agenticqa.security.custom_rules import CustomRuleEngine
        engine = CustomRuleEngine()
        loaded = engine.load_from_repo(str(tmp_path))
        assert loaded == 0


# ── Slack/Teams Notification tests ─────────────────────────────────────────

@pytest.mark.unit
class TestSlackNotifier:
    def test_not_configured(self):
        from agenticqa.notifications.slack import SlackNotifier
        notifier = SlackNotifier(webhook_url="")
        result = notifier.notify_scan(_fake_scan_output())
        assert result.sent is False
        assert "not set" in result.error

    def test_configured_property(self):
        from agenticqa.notifications.slack import SlackNotifier
        assert SlackNotifier(webhook_url="").configured is False
        assert SlackNotifier(webhook_url="https://hooks.slack.com/test").configured is True

    def test_notify_scan_format(self):
        from agenticqa.notifications.slack import SlackNotifier
        notifier = SlackNotifier(webhook_url="https://hooks.slack.com/test")
        # Mock the HTTP call
        with patch("urllib.request.urlopen") as mock_urlopen:
            mock_resp = MagicMock()
            mock_resp.status = 200
            mock_resp.__enter__ = MagicMock(return_value=mock_resp)
            mock_resp.__exit__ = MagicMock(return_value=False)
            mock_urlopen.return_value = mock_resp

            result = notifier.notify_scan(_fake_scan_output())
            assert result.sent is True
            assert result.platform == "slack"

            # Verify the payload has Block Kit format
            call_args = mock_urlopen.call_args
            req = call_args[0][0]
            payload = json.loads(req.data)
            assert "blocks" in payload

    def test_trend_alert(self):
        from agenticqa.notifications.slack import SlackNotifier
        notifier = SlackNotifier(webhook_url="https://hooks.slack.com/test")
        with patch("urllib.request.urlopen") as mock_urlopen:
            mock_resp = MagicMock()
            mock_resp.status = 200
            mock_resp.__enter__ = MagicMock(return_value=mock_resp)
            mock_resp.__exit__ = MagicMock(return_value=False)
            mock_urlopen.return_value = mock_resp
            result = notifier.notify_trend_alert("worsening", delta=15.0)
            assert result.sent is True

    def test_trend_alert_stable_skipped(self):
        from agenticqa.notifications.slack import SlackNotifier
        notifier = SlackNotifier(webhook_url="https://hooks.slack.com/test")
        result = notifier.notify_trend_alert("stable")
        assert result.sent is False

    def test_compliance_deadline_alert(self):
        from agenticqa.notifications.slack import SlackNotifier
        notifier = SlackNotifier(webhook_url="https://hooks.slack.com/test")
        with patch("urllib.request.urlopen") as mock_urlopen:
            mock_resp = MagicMock()
            mock_resp.status = 200
            mock_resp.__enter__ = MagicMock(return_value=mock_resp)
            mock_resp.__exit__ = MagicMock(return_value=False)
            mock_urlopen.return_value = mock_resp
            result = notifier.notify_compliance_deadline(
                "EU AI Act", "Art.9", "Risk Management", days_remaining=30,
            )
            assert result.sent is True

    def test_compliance_not_urgent_skipped(self):
        from agenticqa.notifications.slack import SlackNotifier
        notifier = SlackNotifier(webhook_url="https://hooks.slack.com/test")
        result = notifier.notify_compliance_deadline(
            "EU AI Act", "Art.9", "Risk Management", days_remaining=180,
        )
        assert result.sent is False


@pytest.mark.unit
class TestTeamsNotifier:
    def test_not_configured(self):
        from agenticqa.notifications.slack import TeamsNotifier
        notifier = TeamsNotifier(webhook_url="")
        result = notifier.notify_scan(_fake_scan_output())
        assert result.sent is False

    def test_notify_scan(self):
        from agenticqa.notifications.slack import TeamsNotifier
        notifier = TeamsNotifier(webhook_url="https://outlook.office.com/webhook/test")
        with patch("urllib.request.urlopen") as mock_urlopen:
            mock_resp = MagicMock()
            mock_resp.status = 200
            mock_resp.__enter__ = MagicMock(return_value=mock_resp)
            mock_resp.__exit__ = MagicMock(return_value=False)
            mock_urlopen.return_value = mock_resp
            result = notifier.notify_scan(_fake_scan_output())
            assert result.sent is True
            assert result.platform == "teams"
