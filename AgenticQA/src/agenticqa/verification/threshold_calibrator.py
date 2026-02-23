"""
Adaptive Threshold Calibrator

Uses OutcomeTracker calibration data to compute optimal confidence
thresholds. When predicted_confidence=X corresponds to actual_success_rate=Y,
we can adjust thresholds so agents only trust recommendations where
historical outcomes justify that confidence level.
"""

import json
from pathlib import Path
from typing import Dict, Optional

_DEFAULT_PERSIST_PATH = Path.home() / ".agenticqa" / "thresholds.json"


class ThresholdCalibrator:
    """Computes adaptive thresholds from calibration data."""

    DEFAULT_THRESHOLDS = {
        "qa": 0.7,
        "performance": 0.6,
        "compliance": 0.5,
        "devops": 0.6,
    }

    MIN_CALIBRATION_SAMPLES = 10

    def __init__(self, outcome_tracker=None, persist_path: Optional[Path] = None):
        self.outcome_tracker = outcome_tracker
        self._persist_path = Path(persist_path) if persist_path else _DEFAULT_PERSIST_PATH
        self._cache: Dict[str, float] = {}
        self._cache_valid = False
        # Load previously persisted thresholds so agents benefit immediately
        self._load()

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
                self._cache.clear()
                self._cache_valid = True
                return

            total_samples = sum(b["total"] for b in calibration)
            if total_samples < self.MIN_CALIBRATION_SAMPLES:
                self._cache.clear()
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
            else:
                # No bucket meets target precision — discard any stale loaded values
                # so callers fall back to DEFAULT_THRESHOLDS rather than stale data.
                self._cache.clear()

            self._cache_valid = True
        except Exception:
            self._cache_valid = True

        if self._cache:
            self._save()

    def _save(self):
        """Persist calibrated thresholds to disk."""
        try:
            self._persist_path.parent.mkdir(parents=True, exist_ok=True)
            self._persist_path.write_text(json.dumps(self._cache, indent=2))
        except Exception:
            pass

    def _load(self):
        """Load previously persisted thresholds as a warm-start hint.

        We populate _cache but leave _cache_valid=False so that a live
        _refresh_cache() still runs on first access. If calibration succeeds,
        live values override what was on disk. If calibration finds no valid
        threshold, _cache is cleared and DEFAULT_THRESHOLDS take over.
        Only when there is no outcome_tracker are disk values used directly.
        """
        try:
            if self._persist_path.exists():
                data = json.loads(self._persist_path.read_text())
                if isinstance(data, dict):
                    self._cache = {k: float(v) for k, v in data.items()}
                    # Intentionally leave _cache_valid = False
        except Exception:
            pass

    def invalidate_cache(self):
        """Force recalculation on next access."""
        self._cache_valid = False
