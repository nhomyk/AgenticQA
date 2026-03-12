"""
Tests for observability validation (alert rules, synthetic probes).
"""

from unittest.mock import MagicMock, patch

import pytest

from agenticqa.k8s.observability.alert_validator import (
    AlertRuleCheck,
    AlertRuleValidator,
    RuleFileReport,
)
from agenticqa.k8s.observability.probe_runner import (
    BUILTIN_PROBES,
    ProbeStatus,
    SyntheticProbeRunner,
    dns_probe,
    storage_probe,
)


VALID_RULES_YAML = """
groups:
  - name: test-alerts
    rules:
      - alert: HighErrorRate
        expr: rate(http_errors_total[5m]) > 0.05
        for: 5m
        labels:
          severity: critical
        annotations:
          summary: "Error rate is above 5%"
          description: "Service {{ $labels.service }} error rate is {{ $value }}"
          runbook_url: "https://runbooks.example.com/high-error-rate"
"""

INVALID_RULES_YAML = """
groups:
  - name: bad-alerts
    rules:
      - alert: noSeverity
        expr: up == 0
        labels: {}
        annotations: {}
      - alert: EmptyExpr
        expr: ""
        labels:
          severity: invalid_severity
        annotations:
          summary: "test"
"""

RECORDING_RULE_YAML = """
groups:
  - name: recording-rules
    rules:
      - record: job:http_requests_total:rate5m
        expr: rate(http_requests_total[5m])
"""


class TestAlertRuleValidator:
    """Test Prometheus alert rule validation."""

    @pytest.mark.unit
    def test_valid_rules(self):
        validator = AlertRuleValidator()
        report = validator.validate_rules_inline(VALID_RULES_YAML)
        assert report.total_rules == 1
        assert report.passed_rules == 1
        assert report.failed_rules == 0
        assert report.checks[0].alert_name == "HighErrorRate"
        assert report.checks[0].severity == "critical"

    @pytest.mark.unit
    def test_invalid_rules(self):
        validator = AlertRuleValidator()
        report = validator.validate_rules_inline(INVALID_RULES_YAML)
        assert report.total_rules == 2
        assert report.failed_rules == 2

        # First rule: missing severity label + missing summary annotation
        no_sev = report.checks[0]
        assert not no_sev.passed
        assert any("severity" in i for i in no_sev.issues)
        assert any("summary" in i for i in no_sev.issues)

        # Second rule: empty expr + invalid severity
        empty_expr = report.checks[1]
        assert not empty_expr.passed
        assert any("Empty expr" in i for i in empty_expr.issues)
        assert any("Invalid severity" in i for i in empty_expr.issues)

    @pytest.mark.unit
    def test_recording_rules_skipped(self):
        validator = AlertRuleValidator()
        report = validator.validate_rules_inline(RECORDING_RULE_YAML)
        assert report.total_rules == 0  # Recording rules are not alerting rules

    @pytest.mark.unit
    def test_invalid_yaml(self):
        validator = AlertRuleValidator()
        report = validator.validate_rules_inline("not: valid: yaml: [[[")
        assert report.parse_error != ""

    @pytest.mark.unit
    def test_missing_groups_key(self):
        validator = AlertRuleValidator()
        report = validator.validate_rules_inline("foo: bar")
        assert "groups" in report.parse_error.lower()

    @pytest.mark.unit
    def test_no_for_duration_warning(self):
        yaml_str = """
groups:
  - name: test
    rules:
      - alert: Instant
        expr: up == 0
        labels:
          severity: warning
        annotations:
          summary: "Instance down"
"""
        validator = AlertRuleValidator()
        report = validator.validate_rules_inline(yaml_str)
        check = report.checks[0]
        assert check.passed  # No 'for' is a warning, not a failure
        assert any("No 'for' duration" in w for w in check.warnings)

    @pytest.mark.unit
    def test_short_for_duration_warning(self):
        yaml_str = """
groups:
  - name: test
    rules:
      - alert: TooFast
        expr: up == 0
        for: 5s
        labels:
          severity: warning
        annotations:
          summary: "test"
"""
        validator = AlertRuleValidator()
        report = validator.validate_rules_inline(yaml_str)
        check = report.checks[0]
        assert any("Very short" in w for w in check.warnings)

    @pytest.mark.unit
    def test_rate_without_range_selector(self):
        yaml_str = """
groups:
  - name: test
    rules:
      - alert: BadRate
        expr: rate(http_total) > 0.5
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "test"
"""
        validator = AlertRuleValidator()
        report = validator.validate_rules_inline(yaml_str)
        check = report.checks[0]
        assert any("rate() without range selector" in i for i in check.issues)

    @pytest.mark.unit
    def test_pass_rate(self):
        validator = AlertRuleValidator()
        report = validator.validate_rules_inline(VALID_RULES_YAML)
        assert report.pass_rate == 100.0

    @pytest.mark.unit
    def test_pass_rate_empty(self):
        report = RuleFileReport(file_path="empty")
        assert report.pass_rate == 100.0

    @pytest.mark.unit
    def test_custom_required_labels(self):
        validator = AlertRuleValidator(required_labels={"severity", "team"})
        report = validator.validate_rules_inline(VALID_RULES_YAML)
        # Missing 'team' label
        assert report.failed_rules == 1

    @pytest.mark.unit
    def test_naming_convention_warning(self):
        yaml_str = """
groups:
  - name: test
    rules:
      - alert: lowercaseAlert
        expr: up == 0
        for: 5m
        labels:
          severity: info
        annotations:
          summary: "test"
"""
        validator = AlertRuleValidator()
        report = validator.validate_rules_inline(yaml_str)
        assert any("PascalCase" in w for w in report.checks[0].warnings)

    @pytest.mark.unit
    def test_validate_file(self, tmp_path):
        path = tmp_path / "rules.yaml"
        path.write_text(VALID_RULES_YAML)
        validator = AlertRuleValidator()
        report = validator.validate_file(str(path))
        assert report.passed_rules == 1

    @pytest.mark.unit
    def test_validate_file_not_found(self):
        validator = AlertRuleValidator()
        report = validator.validate_file("/nonexistent/path.yaml")
        assert report.parse_error != ""


class TestSyntheticProbeRunner:
    """Test synthetic probe management."""

    @pytest.mark.unit
    def test_builtin_probes(self):
        assert "dns" in BUILTIN_PROBES
        assert "api-server" in BUILTIN_PROBES
        assert "storage" in BUILTIN_PROBES

    @pytest.mark.unit
    def test_dns_probe_spec(self):
        spec = dns_probe("monitoring")
        assert spec.name == "dns-resolution"
        assert spec.namespace == "monitoring"
        assert "NET-001" in spec.taxonomy_ids

    @pytest.mark.unit
    def test_storage_probe_spec(self):
        spec = storage_probe()
        assert "STOR-001" in spec.taxonomy_ids

    @pytest.mark.unit
    def test_register_builtin(self):
        runner = SyntheticProbeRunner()
        runner.register_builtin()
        assert len(runner._probes) == len(BUILTIN_PROBES)

    @pytest.mark.unit
    @patch.object(SyntheticProbeRunner, "_kubectl")
    def test_run_probe_success(self, mock_kubectl):
        mock_kubectl.return_value = "Name: kubernetes\nAddress: 10.96.0.1"
        runner = SyntheticProbeRunner()
        runner.register_builtin()
        result = runner.run_probe("dns")
        assert result.status == ProbeStatus.HEALTHY
        assert result.latency_ms > 0

    @pytest.mark.unit
    @patch.object(SyntheticProbeRunner, "_kubectl")
    def test_run_probe_failure(self, mock_kubectl):
        mock_kubectl.return_value = None
        runner = SyntheticProbeRunner()
        runner.register_builtin()
        result = runner.run_probe("dns")
        assert result.status == ProbeStatus.UNHEALTHY

    @pytest.mark.unit
    def test_run_unknown_probe(self):
        runner = SyntheticProbeRunner()
        result = runner.run_probe("nonexistent")
        assert result.status == ProbeStatus.ERROR

    @pytest.mark.unit
    def test_generate_cronjob(self):
        runner = SyntheticProbeRunner()
        runner.register_builtin()
        cj = runner.generate_cronjob("dns")
        assert cj is not None
        assert cj["kind"] == "CronJob"
        assert cj["spec"]["schedule"] == "*/5 * * * *"
        assert cj["spec"]["concurrencyPolicy"] == "Forbid"
        container = cj["spec"]["jobTemplate"]["spec"]["template"]["spec"]["containers"][0]
        assert container["resources"]["requests"]["cpu"] == "10m"

    @pytest.mark.unit
    def test_generate_cronjob_unknown(self):
        runner = SyntheticProbeRunner()
        assert runner.generate_cronjob("nonexistent") is None

    @pytest.mark.unit
    def test_generate_all_manifests(self):
        runner = SyntheticProbeRunner()
        runner.register_builtin()
        manifests = runner.generate_all_manifests()
        assert "CronJob" in manifests
        assert "---" in manifests  # Multiple manifests separated

    @pytest.mark.unit
    @patch.object(SyntheticProbeRunner, "_kubectl")
    def test_summary(self, mock_kubectl):
        mock_kubectl.return_value = "healthy output"
        runner = SyntheticProbeRunner()
        runner.register_builtin()
        results = runner.run_all()
        summary = runner.summary(results)
        assert summary["total_probes"] == len(BUILTIN_PROBES)
        assert "healthy_rate" in summary
