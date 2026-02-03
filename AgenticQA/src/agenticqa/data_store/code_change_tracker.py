"""
Code Change Impact Analysis with Before/After Snapshots

Captures data state before and after code changes, analyzes metrics,
and automatically detects regressions or improvements.

This is critical for safe code deployments and preventing quality degradation.
"""

import json
import hashlib
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Any, Optional, Callable
from dataclasses import dataclass, asdict


@dataclass
class BeforeAfterMetrics:
    """Metrics comparing before and after states."""

    # Identity
    change_name: str
    timestamp: str

    # Comparison results
    before_hash: str
    after_hash: str
    changed: bool

    # Quality metrics
    before_quality_score: float
    after_quality_score: float
    quality_delta: float
    quality_improved: bool

    # Performance metrics
    before_execution_time_ms: float
    after_execution_time_ms: float
    performance_delta: float
    performance_improved: bool

    # Test metrics
    before_tests_passed: int
    after_tests_passed: int
    before_tests_failed: int
    after_tests_failed: int
    tests_improved: bool

    # Compliance metrics
    before_compliance_score: float
    after_compliance_score: float
    compliance_improved: bool

    # Overall verdict
    safe_to_deploy: bool
    reason: str

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return asdict(self)

    def to_json(self) -> str:
        """Convert to JSON."""
        return json.dumps(self.to_dict(), indent=2, default=str)


class CodeChangeTracker:
    """
    Tracks code changes and their impact on data quality and performance.

    Workflow:
    1. Capture BEFORE snapshot
    2. Apply code change
    3. Capture AFTER snapshot
    4. Analyze metrics
    5. Decide: Deploy or Rollback
    """

    def __init__(self, changes_dir: str = ".code_changes"):
        """
        Initialize code change tracker.

        Args:
            changes_dir: Directory to store change analyses
        """
        self.changes_dir = Path(changes_dir)
        self.changes_dir.mkdir(exist_ok=True)
        self.current_change: Optional[str] = None
        self.before_snapshot: Optional[Dict[str, Any]] = None

    def start_change(self, change_name: str, before_data: Dict[str, Any]) -> str:
        """
        Begin tracking a code change.

        Args:
            change_name: Name of the change (e.g., "optimize_qa_agent")
            before_data: Data snapshot before change

        Returns:
            Change ID for tracking
        """
        self.current_change = change_name
        self.before_snapshot = {
            "timestamp": datetime.utcnow().isoformat(),
            "name": change_name,
            "data": before_data,
            "hash": self._compute_hash(before_data),
        }

        change_id = f"{change_name}_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}"

        # Save before snapshot
        before_file = self.changes_dir / f"{change_id}_before.json"
        with open(before_file, "w") as f:
            json.dump(self.before_snapshot, f, indent=2, default=str)

        print(f"📸 Before snapshot captured: {change_id}")
        return change_id

    def end_change(self, after_data: Dict[str, Any], change_id: str) -> Dict[str, Any]:
        """
        Complete tracking of a code change.

        Args:
            after_data: Data snapshot after change
            change_id: Change ID from start_change()

        Returns:
            Change analysis results
        """
        if not self.before_snapshot:
            raise ValueError("No active change. Call start_change() first.")

        after_snapshot = {
            "timestamp": datetime.utcnow().isoformat(),
            "name": self.current_change,
            "data": after_data,
            "hash": self._compute_hash(after_data),
        }

        # Save after snapshot
        after_file = self.changes_dir / f"{change_id}_after.json"
        with open(after_file, "w") as f:
            json.dump(after_snapshot, f, indent=2, default=str)

        # Analyze impact
        analysis = self._analyze_impact(self.before_snapshot, after_snapshot, change_id)

        # Save analysis
        analysis_file = self.changes_dir / f"{change_id}_analysis.json"
        with open(analysis_file, "w") as f:
            json.dump(analysis, f, indent=2, default=str)

        print(f"📸 After snapshot captured: {change_id}")

        return analysis

    def _compute_hash(self, data: Dict[str, Any]) -> str:
        """Compute SHA256 hash of data."""
        json_str = json.dumps(data, sort_keys=True, default=str)
        return hashlib.sha256(json_str.encode()).hexdigest()

    def _analyze_impact(
        self, before: Dict[str, Any], after: Dict[str, Any], change_id: str
    ) -> BeforeAfterMetrics:
        """Analyze impact of code change."""

        before_data = before["data"]
        after_data = after["data"]

        # Extract metrics
        before_quality = before_data.get("quality_score", 0.0)
        after_quality = after_data.get("quality_score", 0.0)
        quality_delta = after_quality - before_quality

        before_exec_time = before_data.get("execution_time_ms", 0.0)
        after_exec_time = after_data.get("execution_time_ms", 0.0)
        perf_delta = before_exec_time - after_exec_time  # Negative = slower, positive = faster

        before_tests_pass = before_data.get("tests_passed", 0)
        after_tests_pass = after_data.get("tests_passed", 0)
        before_tests_fail = before_data.get("tests_failed", 0)
        after_tests_fail = after_data.get("tests_failed", 0)

        before_compliance = before_data.get("compliance_score", 0.0)
        after_compliance = after_data.get("compliance_score", 0.0)

        # Determine improvements
        quality_improved = after_quality > before_quality
        performance_improved = perf_delta > 0  # Positive delta = faster
        tests_improved = (
            after_tests_pass > before_tests_pass or after_tests_fail < before_tests_fail
        )
        compliance_improved = after_compliance >= before_compliance

        # Determine if safe to deploy
        safe_to_deploy, reason = self._determine_deployment_safety(
            quality_improved,
            performance_improved,
            tests_improved,
            compliance_improved,
            quality_delta,
            after_tests_fail,
        )

        metrics = BeforeAfterMetrics(
            change_name=before["name"],
            timestamp=datetime.utcnow().isoformat(),
            before_hash=before["hash"],
            after_hash=after["hash"],
            changed=before["hash"] != after["hash"],
            before_quality_score=before_quality,
            after_quality_score=after_quality,
            quality_delta=quality_delta,
            quality_improved=quality_improved,
            before_execution_time_ms=before_exec_time,
            after_execution_time_ms=after_exec_time,
            performance_delta=perf_delta,
            performance_improved=performance_improved,
            before_tests_passed=before_tests_pass,
            after_tests_passed=after_tests_pass,
            before_tests_failed=before_tests_fail,
            after_tests_failed=after_tests_fail,
            tests_improved=tests_improved,
            before_compliance_score=before_compliance,
            after_compliance_score=after_compliance,
            compliance_improved=compliance_improved,
            safe_to_deploy=safe_to_deploy,
            reason=reason,
        )

        return metrics

    def _determine_deployment_safety(
        self,
        quality_improved: bool,
        performance_improved: bool,
        tests_improved: bool,
        compliance_improved: bool,
        quality_delta: float,
        tests_failed: int,
    ) -> tuple[bool, str]:
        """Determine if change is safe to deploy."""

        # Blocking conditions
        if not compliance_improved:
            return False, "Compliance score decreased - security risk"

        if tests_failed > 0:
            return False, f"Tests failing after change - {tests_failed} failures detected"

        if quality_delta < -10:
            return (
                False,
                f"Quality degraded significantly ({quality_delta:.1f}%) - regression detected",
            )

        # Safe conditions
        if quality_improved and tests_improved:
            return True, "✅ All metrics improved - safe to deploy"

        if quality_improved and not performance_improved and tests_improved:
            return True, "✅ Quality and tests improved - acceptable"

        if quality_delta > -5 and tests_improved:
            return True, "✅ Minimal quality loss acceptable, tests improved"

        if quality_improved and tests_improved and performance_improved:
            return True, "✅ All metrics improved significantly - priority deployment"

        return False, "⚠️ Mixed results - manual review required"

    def get_change_analysis(self, change_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve analysis for a change."""
        analysis_file = self.changes_dir / f"{change_id}_analysis.json"
        if analysis_file.exists():
            with open(analysis_file, "r") as f:
                return json.load(f)
        return None

    def list_changes(self) -> List[str]:
        """List all tracked changes."""
        return sorted(
            set(
                f.name.split("_before.json")[0].split("_after.json")[0].split("_analysis.json")[0]
                for f in self.changes_dir.glob("*.json")
            )
        )

    def rollback_change(self, before_data_restore: Callable) -> bool:
        """
        Rollback a failed change by restoring before state.

        Args:
            before_data_restore: Callback function to restore data

        Returns:
            True if rollback successful
        """
        if not self.before_snapshot:
            return False

        try:
            before_data_restore(self.before_snapshot["data"])
            print(f"🔄 Rollback successful for: {self.current_change}")
            self.current_change = None
            self.before_snapshot = None
            return True
        except Exception as e:
            print(f"❌ Rollback failed: {e}")
            return False


class ChangeImpactReport:
    """Generate human-readable reports of code changes."""

    @staticmethod
    def generate_report(metrics: BeforeAfterMetrics) -> str:
        """Generate a detailed change impact report."""
        report = []

        report.append("=" * 80)
        report.append("📊 CODE CHANGE IMPACT ANALYSIS REPORT")
        report.append("=" * 80)
        report.append("")

        # Change info
        report.append(f"Change: {metrics.change_name}")
        report.append(f"Timestamp: {metrics.timestamp}")
        report.append("")

        # Overall verdict
        verdict = "✅ SAFE TO DEPLOY" if metrics.safe_to_deploy else "❌ BLOCK DEPLOYMENT"
        report.append(f"Verdict: {verdict}")
        report.append(f"Reason: {metrics.reason}")
        report.append("")

        # Quality metrics
        report.append("📈 QUALITY METRICS:")
        report.append(f"  Before: {metrics.before_quality_score:.1f}%")
        report.append(f"  After:  {metrics.after_quality_score:.1f}%")
        report.append(f"  Delta:  {metrics.quality_delta:+.1f}%")
        report.append(f"  Status: {'✅ Improved' if metrics.quality_improved else '❌ Degraded'}")
        report.append("")

        # Performance metrics
        report.append("⚡ PERFORMANCE METRICS:")
        report.append(f"  Before: {metrics.before_execution_time_ms:.2f}ms")
        report.append(f"  After:  {metrics.after_execution_time_ms:.2f}ms")
        report.append(f"  Delta:  {metrics.performance_delta:+.2f}ms")
        report.append(f"  Status: {'✅ Faster' if metrics.performance_improved else '⚠️  Slower'}")
        report.append("")

        # Test metrics
        report.append("✔️ TEST METRICS:")
        report.append(
            f"  Before: {metrics.before_tests_passed} passed, {metrics.before_tests_failed} failed"
        )
        report.append(
            f"  After:  {metrics.after_tests_passed} passed, {metrics.after_tests_failed} failed"
        )
        report.append(f"  Status: {'✅ Improved' if metrics.tests_improved else '❌ Degraded'}")
        report.append("")

        # Compliance
        report.append("🔒 COMPLIANCE:")
        report.append(f"  Before: {metrics.before_compliance_score:.1f}%")
        report.append(f"  After:  {metrics.after_compliance_score:.1f}%")
        report.append(f"  Status: {'✅ Maintained' if metrics.compliance_improved else '❌ Risk'}")
        report.append("")

        report.append("=" * 80)

        return "\n".join(report)
