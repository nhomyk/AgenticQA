"""
Tests for the coverage tracker.
"""

import json

import pytest

from agenticqa.k8s.coverage import CoverageGap, CoverageTracker, TestRecord
from agenticqa.k8s.taxonomy import FailureTaxonomy


@pytest.fixture
def taxonomy():
    return FailureTaxonomy.load()


@pytest.fixture
def tracker(taxonomy):
    return CoverageTracker(taxonomy)


class TestCoverageTracker:
    """Test coverage tracking and reporting."""

    @pytest.mark.unit
    def test_initial_state(self, tracker, taxonomy):
        assert tracker.coverage_percent() == 0.0
        assert len(tracker.untested_ids) == len(taxonomy)
        assert len(tracker.tested_ids) == 0

    @pytest.mark.unit
    def test_record_single(self, tracker):
        tracker.record("POD-001", passed=True)
        assert "POD-001" in tracker.tested_ids
        assert tracker.coverage_percent() > 0

    @pytest.mark.unit
    def test_record_multiple(self, tracker, taxonomy):
        for s in taxonomy:
            tracker.record(s.id, passed=True)
        assert tracker.coverage_percent() == 100.0
        assert len(tracker.untested_ids) == 0

    @pytest.mark.unit
    def test_resilience_score_all_pass(self, tracker):
        tracker.record("POD-001", passed=True)
        tracker.record("POD-002", passed=True)
        assert tracker.resilience_score() == 100.0

    @pytest.mark.unit
    def test_resilience_score_mixed(self, tracker):
        tracker.record("POD-001", passed=True)
        tracker.record("POD-002", passed=False)
        assert tracker.resilience_score() == 50.0

    @pytest.mark.unit
    def test_resilience_score_empty(self, tracker):
        assert tracker.resilience_score() == 0.0

    @pytest.mark.unit
    def test_gaps_sorted_by_severity(self, tracker):
        gaps = tracker.gaps()
        assert len(gaps) > 0
        # First gap should be critical
        assert gaps[0].risk_level == "critical"

    @pytest.mark.unit
    def test_report_structure(self, tracker):
        tracker.record("POD-001", passed=True)
        report = tracker.report()
        assert "coverage_percent" in report
        assert "resilience_score" in report
        assert "by_category" in report
        assert "by_severity" in report
        assert "untested_critical" in report
        assert "untested_count" in report

    @pytest.mark.unit
    def test_report_by_category(self, tracker):
        tracker.record("POD-001", passed=True)
        report = tracker.report()
        pod_coverage = report["by_category"]["pod_failures"]
        assert pod_coverage["tested"] == 1
        assert pod_coverage["total"] >= 10

    @pytest.mark.unit
    def test_report_by_severity(self, tracker):
        tracker.record("POD-001", passed=True)  # POD-001 is critical
        report = tracker.report()
        crit = report["by_severity"]["critical"]
        assert crit["tested"] >= 1

    @pytest.mark.unit
    def test_save_and_load(self, tracker, taxonomy, tmp_path):
        tracker.record("POD-001", passed=True, experiment_name="test")
        tracker.record("NET-001", passed=False)

        save_path = str(tmp_path / "coverage.json")
        tracker.save(save_path)

        loaded = CoverageTracker.load(save_path, taxonomy)
        assert loaded.coverage_percent() == tracker.coverage_percent()
        assert "POD-001" in loaded.tested_ids
        assert "NET-001" in loaded.tested_ids

    @pytest.mark.unit
    def test_diff(self, taxonomy):
        prev = CoverageTracker(taxonomy)
        prev.record("POD-001", passed=True)

        curr = CoverageTracker(taxonomy)
        curr.record("POD-001", passed=True)
        curr.record("POD-002", passed=True)

        diff = curr.diff(prev)
        assert "POD-002" in diff["new_coverage"]
        assert diff["coverage_delta"] > 0
        assert len(diff["lost_coverage"]) == 0

    @pytest.mark.unit
    def test_diff_lost_coverage(self, taxonomy):
        prev = CoverageTracker(taxonomy)
        prev.record("POD-001", passed=True)
        prev.record("POD-002", passed=True)

        curr = CoverageTracker(taxonomy)
        curr.record("POD-001", passed=True)

        diff = curr.diff(prev)
        assert "POD-002" in diff["lost_coverage"]
        assert diff["coverage_delta"] < 0

    @pytest.mark.unit
    def test_record_from_chaos_results(self, tracker):
        """Test integration with ChaosEngine results."""

        class MockResult:
            taxonomy_id = "POD-001"
            experiment_name = "pod-kill"
            details = {"killed_pod": "web-123"}

            class status:
                value = "passed"

        tracker.record_from_chaos_results([MockResult()])
        assert "POD-001" in tracker.tested_ids


class TestTestRecord:
    """Test the TestRecord dataclass."""

    @pytest.mark.unit
    def test_auto_timestamp(self):
        record = TestRecord(taxonomy_id="POD-001", passed=True)
        assert record.timestamp != ""

    @pytest.mark.unit
    def test_explicit_timestamp(self):
        record = TestRecord(
            taxonomy_id="POD-001", passed=True, timestamp="2026-01-01"
        )
        assert record.timestamp == "2026-01-01"
