"""
Test Suite for Code Change Tracking and Rollback

Ensures that before/after snapshots work correctly and code changes
are properly validated for safety.
"""

import pytest
from agenticqa.data_store.code_change_tracker import CodeChangeTracker, BeforeAfterMetrics
from agenticqa.data_store.change_executor import SafeCodeChangeExecutor, ChangeHistoryAnalyzer


@pytest.fixture
def change_tracker():
    """Create code change tracker."""
    return CodeChangeTracker(".test_changes")


@pytest.fixture
def safe_executor():
    """Create safe code change executor."""
    return SafeCodeChangeExecutor()


@pytest.fixture
def test_before_data():
    """Before state test data."""
    return {
        "quality_score": 85.0,
        "execution_time_ms": 150.0,
        "tests_passed": 95,
        "tests_failed": 5,
        "compliance_score": 90.0,
    }


@pytest.fixture
def test_after_data_improved():
    """After state with improvements."""
    return {
        "quality_score": 92.0,
        "execution_time_ms": 120.0,
        "tests_passed": 98,
        "tests_failed": 2,
        "compliance_score": 92.0,
    }


@pytest.fixture
def test_after_data_degraded():
    """After state with degradation."""
    return {
        "quality_score": 72.0,
        "execution_time_ms": 200.0,
        "tests_passed": 85,
        "tests_failed": 15,
        "compliance_score": 75.0,
    }


class TestCodeChangeTracker:
    """Test code change tracking functionality."""

    def test_start_change(self, change_tracker, test_before_data):
        """Test starting change tracking."""
        change_id = change_tracker.start_change("test_change", test_before_data)

        assert change_id is not None
        assert "test_change" in change_id
        assert change_tracker.current_change == "test_change"

    def test_end_change_improvement(
        self, change_tracker, test_before_data, test_after_data_improved
    ):
        """Test ending change when metrics improve."""
        change_id = change_tracker.start_change("improvement", test_before_data)
        analysis = change_tracker.end_change(test_after_data_improved, change_id)

        assert analysis.quality_improved is True
        assert analysis.performance_improved is True
        assert analysis.tests_improved is True
        assert analysis.safe_to_deploy is True

    def test_end_change_degradation(
        self, change_tracker, test_before_data, test_after_data_degraded
    ):
        """Test ending change when metrics degrade."""
        change_id = change_tracker.start_change("degradation", test_before_data)
        analysis = change_tracker.end_change(test_after_data_degraded, change_id)

        assert analysis.quality_improved is False
        assert analysis.safe_to_deploy is False

    def test_metric_calculation(self, change_tracker, test_before_data, test_after_data_improved):
        """Test metric calculations."""
        change_id = change_tracker.start_change("metrics_test", test_before_data)
        analysis = change_tracker.end_change(test_after_data_improved, change_id)

        assert analysis.quality_delta == pytest.approx(7.0)
        assert analysis.performance_delta == pytest.approx(30.0)  # Faster
        assert analysis.before_tests_failed == 5
        assert analysis.after_tests_failed == 2

    def test_list_changes(self, change_tracker, test_before_data, test_after_data_improved):
        """Test listing all tracked changes."""
        change_id1 = change_tracker.start_change("change1", test_before_data)
        change_tracker.end_change(test_after_data_improved, change_id1)

        change_id2 = change_tracker.start_change("change2", test_before_data)
        change_tracker.end_change(test_after_data_improved, change_id2)

        changes = change_tracker.list_changes()

        assert len(changes) == 2
        assert any("change1" in c for c in changes)
        assert any("change2" in c for c in changes)


class TestDeploymentSafety:
    """Test deployment safety determination."""

    def test_safe_when_all_improved(
        self, change_tracker, test_before_data, test_after_data_improved
    ):
        """Test safe deployment when all metrics improve."""
        change_id = change_tracker.start_change("all_improve", test_before_data)
        analysis = change_tracker.end_change(test_after_data_improved, change_id)

        assert analysis.safe_to_deploy is True

    def test_unsafe_when_tests_fail(self, change_tracker, test_before_data):
        """Test unsafe deployment when tests fail."""
        change_id = change_tracker.start_change("test_failure", test_before_data)

        after_with_failures = {
            "quality_score": 90.0,
            "execution_time_ms": 140.0,
            "tests_passed": 50,
            "tests_failed": 50,  # Many failures!
            "compliance_score": 90.0,
        }

        analysis = change_tracker.end_change(after_with_failures, change_id)

        assert analysis.safe_to_deploy is False
        assert "Tests failing" in analysis.reason

    def test_unsafe_when_compliance_decreases(self, change_tracker, test_before_data):
        """Test unsafe deployment when compliance score decreases."""
        change_id = change_tracker.start_change("compliance_risk", test_before_data)

        after_low_compliance = {
            "quality_score": 95.0,
            "execution_time_ms": 100.0,
            "tests_passed": 100,
            "tests_failed": 0,
            "compliance_score": 50.0,  # Dropped significantly
        }

        analysis = change_tracker.end_change(after_low_compliance, change_id)

        assert analysis.safe_to_deploy is False
        assert "Compliance" in analysis.reason


class TestChangeImpactReport:
    """Test impact report generation."""

    def test_report_generation(self, change_tracker, test_before_data, test_after_data_improved):
        """Test that reports are generated correctly."""
        from agenticqa.data_store.code_change_tracker import ChangeImpactReport

        change_id = change_tracker.start_change("report_test", test_before_data)
        analysis = change_tracker.end_change(test_after_data_improved, change_id)

        report = ChangeImpactReport.generate_report(analysis)

        assert "CODE CHANGE IMPACT ANALYSIS REPORT" in report
        assert "SAFE TO DEPLOY" in report
        assert "85.0" in report  # Before quality
        assert "92.0" in report  # After quality


class TestChangeHistoryAnalyzer:
    """Test change history analysis."""

    def test_statistics_generation(
        self, change_tracker, test_before_data, test_after_data_improved, test_after_data_degraded
    ):
        """Test statistics calculation."""
        # Create successful change
        change_id1 = change_tracker.start_change("success", test_before_data)
        change_tracker.end_change(test_after_data_improved, change_id1)

        # Create failed change
        change_id2 = change_tracker.start_change("failure", test_before_data)
        change_tracker.end_change(test_after_data_degraded, change_id2)

        analyzer = ChangeHistoryAnalyzer(change_tracker)
        stats = analyzer.get_change_statistics()

        assert stats["total_changes"] == 2
        assert stats["successful_changes"] == 1
        assert stats["failed_changes"] == 1
        assert stats["success_rate"] == pytest.approx(50.0)

    def test_summary_report(self, change_tracker, test_before_data, test_after_data_improved):
        """Test summary report generation."""
        change_id = change_tracker.start_change("summary_test", test_before_data)
        change_tracker.end_change(test_after_data_improved, change_id)

        analyzer = ChangeHistoryAnalyzer(change_tracker)
        report = analyzer.generate_summary_report()

        assert "CODE CHANGE HISTORY SUMMARY" in report
        assert "Total Changes:" in report
        assert "Success Rate:" in report
