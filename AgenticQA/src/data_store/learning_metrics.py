"""
Per-run learning metrics snapshots.

Appends a compact JSON record to ~/.agenticqa/metrics_history.jsonl after each
CI run so the platform can show clients a real improvement curve over time.
Each record is one line (JSONL) for cheap streaming reads and append-only safety.
"""

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

try:
    from agenticqa.security.learning_loop_integrity import LearningLoopIntegrityGuard as _Guard
    _integrity_guard = _Guard()
except ImportError:
    _integrity_guard = None

_DEFAULT_HISTORY_PATH = Path.home() / ".agenticqa" / "metrics_history.jsonl"


class LearningMetricsSnapshot:
    """Records and retrieves per-run learning metrics."""

    def __init__(self, history_path: Optional[Path] = None):
        self._path = Path(history_path) if history_path else _DEFAULT_HISTORY_PATH

    # ──────────────────────────────────────────────────────────────────────
    # Write
    # ──────────────────────────────────────────────────────────────────────

    def record(
        self,
        *,
        run_id: str,
        fix_rate: Optional[float] = None,
        fixable_errors: Optional[int] = None,
        fixes_applied: Optional[int] = None,
        architectural_violations: Optional[int] = None,
        threshold_qa: Optional[float] = None,
        threshold_compliance: Optional[float] = None,
        artifact_count: Optional[int] = None,
        delegation_pairs: Optional[int] = None,
        repo_id: Optional[str] = None,
        extra: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Append a snapshot for this run. Returns the recorded dict."""
        snapshot: Dict[str, Any] = {
            "run_id": run_id,
            "recorded_at": datetime.now(timezone.utc).isoformat(),
        }
        if fix_rate is not None:
            snapshot["fix_rate"] = round(fix_rate, 4)
        if fixable_errors is not None:
            snapshot["fixable_errors"] = fixable_errors
        if fixes_applied is not None:
            snapshot["fixes_applied"] = fixes_applied
        if architectural_violations is not None:
            snapshot["architectural_violations"] = architectural_violations
        if threshold_qa is not None:
            snapshot["threshold_qa"] = round(threshold_qa, 4)
        if threshold_compliance is not None:
            snapshot["threshold_compliance"] = round(threshold_compliance, 4)
        if artifact_count is not None:
            snapshot["artifact_count"] = artifact_count
        if delegation_pairs is not None:
            snapshot["delegation_pairs"] = delegation_pairs
        if repo_id is not None:
            snapshot["repo_id"] = repo_id
        if extra:
            snapshot.update(extra)

        try:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            with open(self._path, "a") as f:
                f.write(json.dumps(snapshot) + "\n")
        except Exception:
            pass

        return snapshot

    # ──────────────────────────────────────────────────────────────────────
    # Read
    # ──────────────────────────────────────────────────────────────────────

    def load_history(
        self,
        repo_id: Optional[str] = None,
        limit: int = 50,
    ) -> List[Dict[str, Any]]:
        """Return the last `limit` snapshots, optionally filtered by repo."""
        if not self._path.exists():
            return []
        records = []
        try:
            with open(self._path) as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        rec = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    # Integrity validation — skip poisoned records
                    if _integrity_guard is not None:
                        ok, violations = _integrity_guard.validate_metrics_record(rec)
                        if not ok:
                            logger.warning(
                                "Skipping poisoned metrics record: %s",
                                [str(v) for v in violations],
                            )
                            continue
                    if repo_id and rec.get("repo_id") != repo_id:
                        continue
                    records.append(rec)
        except Exception:
            return []
        return records[-limit:]

    def get_improvement_curve(
        self,
        metric_key: str,
        repo_id: Optional[str] = None,
        window: int = 20,
    ) -> List[Dict[str, Any]]:
        """Return time-series of a single metric across the last `window` runs.

        Each point: {"run_id": str, "recorded_at": str, "value": float|int}
        Only includes records that actually contain the requested metric.
        """
        history = self.load_history(repo_id=repo_id, limit=window * 3)
        curve = []
        for rec in history:
            if metric_key in rec:
                curve.append({
                    "run_id": rec["run_id"],
                    "recorded_at": rec["recorded_at"],
                    "value": rec[metric_key],
                })
        return curve[-window:]

    def summary(self, repo_id: Optional[str] = None, window: int = 10) -> Dict[str, Any]:
        """Return a human-readable improvement summary for the last N runs."""
        history = self.load_history(repo_id=repo_id, limit=window)
        if not history:
            return {"runs": 0, "message": "No run history yet."}

        def _avg(key: str) -> Optional[float]:
            vals = [r[key] for r in history if key in r]
            return round(sum(vals) / len(vals), 4) if vals else None

        first_half = history[: len(history) // 2] or history
        second_half = history[len(history) // 2 :] or history

        def _avg_half(records: List, key: str) -> Optional[float]:
            vals = [r[key] for r in records if key in r]
            return round(sum(vals) / len(vals), 4) if vals else None

        fix_rate_early = _avg_half(first_half, "fix_rate")
        fix_rate_recent = _avg_half(second_half, "fix_rate")

        trend = None
        if fix_rate_early is not None and fix_rate_recent is not None:
            delta = fix_rate_recent - fix_rate_early
            if delta > 0.02:
                trend = "improving"
            elif delta < -0.02:
                trend = "declining"
            else:
                trend = "stable"

        return {
            "runs": len(history),
            "avg_fix_rate": _avg("fix_rate"),
            "avg_artifact_count": _avg("artifact_count"),
            "avg_delegation_pairs": _avg("delegation_pairs"),
            "fix_rate_trend": trend,
            "fix_rate_early_avg": fix_rate_early,
            "fix_rate_recent_avg": fix_rate_recent,
        }
