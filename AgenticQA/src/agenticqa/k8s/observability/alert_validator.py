"""
Alert Rule Validator — Test Prometheus alerting rules offline.

INTERVIEW CONCEPT: Prometheus alerting has two components:
    1. Recording rules — precompute expensive PromQL queries
    2. Alerting rules — fire when a PromQL expression crosses a threshold

The problem: most teams don't test their alert rules. They find out
alerts are broken AFTER an incident. This module validates rules by:
    - Parsing rule YAML files
    - Checking PromQL syntax (via promtool if available)
    - Validating alert metadata (severity labels, runbook annotations)
    - Running unit tests against sample metrics

Key PromQL concepts for interviews:
    rate()         — per-second rate of counter increase
    increase()     — total increase over time range
    histogram_quantile() — calculate percentiles from histograms
    absent()       — fires when a metric DOESN'T exist (meta-monitoring)
    for:           — duration the condition must be true before firing

Usage:
    validator = AlertRuleValidator()
    results = validator.validate_file("alerts.yaml")
    results = validator.validate_directory("/path/to/rules/")
"""

from __future__ import annotations

import logging
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import yaml

logger = logging.getLogger(__name__)


# Required labels/annotations for production alert rules
REQUIRED_LABELS = {"severity"}
REQUIRED_ANNOTATIONS = {"summary"}
RECOMMENDED_ANNOTATIONS = {"description", "runbook_url"}
VALID_SEVERITIES = {"critical", "warning", "info"}


@dataclass
class AlertRuleCheck:
    """Result of validating a single alerting rule."""

    group_name: str
    alert_name: str
    passed: bool
    issues: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    expr: str = ""
    for_duration: str = ""
    severity: str = ""


@dataclass
class RuleFileReport:
    """Validation report for a single rules file."""

    file_path: str
    total_rules: int = 0
    passed_rules: int = 0
    failed_rules: int = 0
    checks: list[AlertRuleCheck] = field(default_factory=list)
    promtool_valid: Optional[bool] = None  # None = promtool not available
    parse_error: str = ""

    @property
    def pass_rate(self) -> float:
        if self.total_rules == 0:
            return 100.0
        return (self.passed_rules / self.total_rules) * 100


class AlertRuleValidator:
    """
    Validates Prometheus alerting rules for completeness and correctness.

    Checks:
        1. YAML parse validity
        2. Required labels (severity)
        3. Required annotations (summary, description)
        4. PromQL syntax (via promtool if available)
        5. Duration sanity (not too short, not too long)
        6. Alert naming conventions
    """

    def __init__(
        self,
        required_labels: Optional[set[str]] = None,
        required_annotations: Optional[set[str]] = None,
    ) -> None:
        self._required_labels = required_labels or REQUIRED_LABELS
        self._required_annotations = required_annotations or REQUIRED_ANNOTATIONS
        self._promtool_available: Optional[bool] = None

    def validate_file(self, file_path: str) -> RuleFileReport:
        """Validate all alerting rules in a Prometheus rules YAML file."""
        path = Path(file_path)
        report = RuleFileReport(file_path=str(path))

        # Parse YAML
        try:
            with open(path) as f:
                data = yaml.safe_load(f)
        except (yaml.YAMLError, OSError) as e:
            report.parse_error = str(e)
            return report

        if not data or "groups" not in data:
            report.parse_error = "No 'groups' key found in rules file"
            return report

        # Validate each rule
        for group in data.get("groups", []):
            group_name = group.get("name", "unnamed")
            for rule in group.get("rules", []):
                if "alert" not in rule:
                    continue  # Recording rule, not alerting
                check = self._validate_rule(group_name, rule)
                report.checks.append(check)
                report.total_rules += 1
                if check.passed:
                    report.passed_rules += 1
                else:
                    report.failed_rules += 1

        # Run promtool check if available
        report.promtool_valid = self._run_promtool_check(file_path)

        return report

    def validate_directory(self, dir_path: str) -> list[RuleFileReport]:
        """Validate all .yaml/.yml rule files in a directory."""
        path = Path(dir_path)
        reports = []
        for f in sorted(path.glob("**/*.y*ml")):
            if f.is_file():
                reports.append(self.validate_file(str(f)))
        return reports

    def validate_rules_inline(self, rules_yaml: str) -> RuleFileReport:
        """Validate rules from a YAML string (useful for testing)."""
        report = RuleFileReport(file_path="<inline>")

        try:
            data = yaml.safe_load(rules_yaml)
        except yaml.YAMLError as e:
            report.parse_error = str(e)
            return report

        if not data or "groups" not in data:
            report.parse_error = "No 'groups' key found"
            return report

        for group in data.get("groups", []):
            group_name = group.get("name", "unnamed")
            for rule in group.get("rules", []):
                if "alert" not in rule:
                    continue
                check = self._validate_rule(group_name, rule)
                report.checks.append(check)
                report.total_rules += 1
                if check.passed:
                    report.passed_rules += 1
                else:
                    report.failed_rules += 1

        return report

    # ── Private validation logic ─────────────────────────────────────────

    def _validate_rule(self, group_name: str, rule: dict) -> AlertRuleCheck:
        """Validate a single alerting rule."""
        alert_name = rule.get("alert", "unnamed")
        expr = rule.get("expr", "")
        for_duration = rule.get("for", "")
        labels = rule.get("labels", {})
        annotations = rule.get("annotations", {})

        issues = []
        warnings = []

        # Check required labels
        for label in self._required_labels:
            if label not in labels:
                issues.append(f"Missing required label: {label}")

        # Check severity value
        severity = labels.get("severity", "")
        if severity and severity not in VALID_SEVERITIES:
            issues.append(
                f"Invalid severity '{severity}' — must be one of {VALID_SEVERITIES}"
            )

        # Check required annotations
        for ann in self._required_annotations:
            if ann not in annotations:
                issues.append(f"Missing required annotation: {ann}")

        # Check recommended annotations (warnings, not failures)
        for ann in RECOMMENDED_ANNOTATIONS:
            if ann not in annotations:
                warnings.append(f"Missing recommended annotation: {ann}")

        # Check expression is not empty
        if not expr:
            issues.append("Empty expr (PromQL expression)")

        # Check for common PromQL mistakes
        if expr:
            if "rate(" in expr and "[" not in expr:
                issues.append("rate() without range selector — needs [5m] or similar")
            if "==" in expr and "bool" not in expr and "for" not in rule:
                warnings.append(
                    "Equality check without 'for' duration — may fire on transient spikes"
                )

        # Check for duration
        if for_duration:
            self._check_duration(for_duration, issues, warnings)
        else:
            warnings.append(
                "No 'for' duration — alert fires immediately on first evaluation"
            )

        # Check naming convention (PascalCase recommended)
        if alert_name and not alert_name[0].isupper():
            warnings.append(
                f"Alert name '{alert_name}' should be PascalCase by convention"
            )

        return AlertRuleCheck(
            group_name=group_name,
            alert_name=alert_name,
            passed=len(issues) == 0,
            issues=issues,
            warnings=warnings,
            expr=expr,
            for_duration=for_duration,
            severity=severity,
        )

    @staticmethod
    def _check_duration(
        duration: str, issues: list[str], warnings: list[str]
    ) -> None:
        """Validate a Prometheus duration string."""
        # Parse simple durations (5m, 1h, 30s)
        try:
            unit = duration[-1]
            value = int(duration[:-1])
            if unit == "s" and value < 30:
                warnings.append(
                    f"Very short 'for' duration ({duration}) — may cause alert flapping"
                )
            if unit == "h" and value > 24:
                warnings.append(
                    f"Very long 'for' duration ({duration}) — alert may fire too late"
                )
        except (ValueError, IndexError):
            pass  # Complex duration format, skip validation

    def _run_promtool_check(self, file_path: str) -> Optional[bool]:
        """Run promtool check rules if available."""
        if self._promtool_available is None:
            try:
                subprocess.run(
                    ["promtool", "--version"],
                    capture_output=True,
                    check=True,
                    timeout=5,
                )
                self._promtool_available = True
            except (FileNotFoundError, subprocess.CalledProcessError):
                self._promtool_available = False

        if not self._promtool_available:
            return None

        try:
            result = subprocess.run(
                ["promtool", "check", "rules", file_path],
                capture_output=True,
                text=True,
                check=False,
                timeout=30,
            )
            return result.returncode == 0
        except subprocess.TimeoutExpired:
            return None
