"""
Adaptive Threshold Calibrator

Uses OutcomeTracker calibration data to compute optimal confidence
thresholds. When predicted_confidence=X corresponds to actual_success_rate=Y,
we can adjust thresholds so agents only trust recommendations where
historical outcomes justify that confidence level.
"""

from typing import Dict, Optional


class ThresholdCalibrator:
    """Computes adaptive thresholds from calibration data."""

    DEFAULT_THRESHOLDS = {
        "qa": 0.7,
        "performance": 0.6,
        "compliance": 0.5,
        "devops": 0.6,
    }

    MIN_CALIBRATION_SAMPLES = 10

    def __init__(self, outcome_tracker=None):
        self.outcome_tracker = outcome_tracker
        self._cache: Dict[str, float] = {}
        self._cache_valid = False

    def get_threshold(self, agent_type: str, target_precision: float = 0.7) -> float:
        """
        Get calibrated confidence threshold for an agent type.

        Args:
            agent_type: Type of agent (qa, performance, compliance, devops)
            target_precision: Desired minimum actual success rate

        Returns:
            Calibrated threshold, or default if insufficient data
        """
        if not self.outcome_tracker:
            return self.DEFAULT_THRESHOLDS.get(agent_type, 0.6)

        if not self._cache_valid:
            self._refresh_cache(target_precision)

        return self._cache.get(
            agent_type, self.DEFAULT_THRESHOLDS.get(agent_type, 0.6)
        )

    def _refresh_cache(self, target_precision: float):
        """Recompute thresholds from calibration data."""
        try:
            calibration = self.outcome_tracker.get_calibration(bucket_size=0.1)

            if not calibration:
                self._cache_valid = True
                return

            total_samples = sum(b["total"] for b in calibration)
            if total_samples < self.MIN_CALIBRATION_SAMPLES:
                self._cache_valid = True
                return

            # Find the lowest confidence bucket where actual_rate >= target_precision
            optimal_threshold = None
            for bucket in sorted(calibration, key=lambda b: b["bucket"]):
                if bucket["actual_rate"] >= target_precision and bucket["total"] >= 3:
                    optimal_threshold = bucket["bucket"]
                    break

            if optimal_threshold is not None:
                for agent_type, default in self.DEFAULT_THRESHOLDS.items():
                    # Blend: 50% calibrated, 50% default (conservative)
                    self._cache[agent_type] = (optimal_threshold + default) / 2.0

            self._cache_valid = True
        except Exception:
            self._cache_valid = True

    def invalidate_cache(self):
        """Force recalculation on next access."""
        self._cache_valid = False
