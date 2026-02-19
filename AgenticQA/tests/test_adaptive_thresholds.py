"""
Tests for adaptive confidence threshold calibration.

Verifies that:
1. Default thresholds are returned without an OutcomeTracker
2. Defaults are returned with insufficient calibration data
3. Thresholds adjust from calibration data
4. Cache invalidation forces recalculation
"""

import pytest
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from agenticqa.verification.threshold_calibrator import ThresholdCalibrator
from agenticqa.verification.outcome_tracker import OutcomeTracker


@pytest.fixture
def tmp_db(tmp_path):
    return str(tmp_path / "test.db")


@pytest.mark.unit
class TestThresholdCalibrator:

    def test_returns_defaults_without_tracker(self):
        calibrator = ThresholdCalibrator(outcome_tracker=None)
        assert calibrator.get_threshold("qa") == 0.7
        assert calibrator.get_threshold("performance") == 0.6
        assert calibrator.get_threshold("compliance") == 0.5
        assert calibrator.get_threshold("devops") == 0.6

    def test_returns_defaults_with_insufficient_data(self, tmp_db):
        ot = OutcomeTracker(db_path=tmp_db)
        # Only 3 samples — below MIN_CALIBRATION_SAMPLES (10)
        for i in range(3):
            ot.record_prediction(f"d-{i}", "A", "B", "task", 0.8)
            ot.record_outcome(f"d-{i}", actual_success=True)

        calibrator = ThresholdCalibrator(ot)
        assert calibrator.get_threshold("qa") == 0.7  # Default, not calibrated
        ot.close()

    def test_adjusts_threshold_from_calibration(self, tmp_db):
        ot = OutcomeTracker(db_path=tmp_db)
        # Record 20 outcomes: confidence 0.5 -> 90% success, confidence 0.3 -> 30% success
        # This means at bucket 0.5, actual_rate=0.9 (> 0.7 target), so threshold should adjust
        for i in range(10):
            ot.record_prediction(f"high-{i}", "A", "B", "task", 0.5 + (i * 0.01))
            ot.record_outcome(f"high-{i}", actual_success=(i < 9))  # 90% success

        for i in range(10):
            ot.record_prediction(f"low-{i}", "A", "B", "task", 0.3 + (i * 0.01))
            ot.record_outcome(f"low-{i}", actual_success=(i < 3))  # 30% success

        calibrator = ThresholdCalibrator(ot)
        threshold = calibrator.get_threshold("qa")

        # The calibrator should blend the optimal bucket (0.5) with the default (0.7)
        # Result: (0.5 + 0.7) / 2 = 0.6
        assert threshold != 0.7, f"Threshold should have changed from default, got {threshold}"
        assert 0.4 < threshold < 0.8, f"Threshold should be reasonable, got {threshold}"
        ot.close()

    def test_cache_invalidation(self, tmp_db):
        ot = OutcomeTracker(db_path=tmp_db)

        # Seed enough data
        for i in range(15):
            ot.record_prediction(f"d-{i}", "A", "B", "task", 0.5)
            ot.record_outcome(f"d-{i}", actual_success=True)

        calibrator = ThresholdCalibrator(ot)
        threshold_1 = calibrator.get_threshold("qa")

        # Add more data with different outcomes
        for i in range(15, 30):
            ot.record_prediction(f"d-{i}", "A", "B", "task", 0.8)
            ot.record_outcome(f"d-{i}", actual_success=(i < 20))  # Mix results

        # Without invalidation, cached value is returned
        threshold_2 = calibrator.get_threshold("qa")
        assert threshold_2 == threshold_1

        # After invalidation, threshold should be recalculated
        calibrator.invalidate_cache()
        threshold_3 = calibrator.get_threshold("qa")
        # May or may not change value, but cache should have been refreshed
        assert calibrator._cache_valid is True
        ot.close()

    def test_unknown_agent_type_returns_default(self):
        calibrator = ThresholdCalibrator(outcome_tracker=None)
        # Unknown agent type should return 0.6 (general default)
        assert calibrator.get_threshold("unknown_agent") == 0.6

    def test_all_failures_keeps_defaults(self, tmp_db):
        """When all outcomes are failures, no bucket meets target_precision."""
        ot = OutcomeTracker(db_path=tmp_db)
        for i in range(15):
            ot.record_prediction(f"d-{i}", "A", "B", "task", 0.8)
            ot.record_outcome(f"d-{i}", actual_success=False)

        calibrator = ThresholdCalibrator(ot)
        # No bucket has actual_rate >= 0.7, so defaults should be used
        assert calibrator.get_threshold("qa") == 0.7
        ot.close()
