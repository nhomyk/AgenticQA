"""
Compliance drift detection — tracks violation counts run-over-run and alerts on increases.

Storage: ~/.agenticqa/compliance_history.jsonl (one JSON record per run per repo)
"""
from __future__ import annotations

import json
import os
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

_DEFAULT_DIR = Path(os.path.expanduser("~/.agenticqa"))


class ComplianceDriftDetector:
    """Persists compliance violation snapshots and detects run-over-run drift."""

    def __init__(self, store_dir: Optional[Path] = None):
        self._dir = Path(store_dir) if store_dir else _DEFAULT_DIR
        self._dir.mkdir(parents=True, exist_ok=True)
        self._history_path = self._dir / "compliance_history.jsonl"

    # ── Write ──────────────────────────────────────────────────────────────────

    def record_run(
        self,
        run_id: str,
        violations: List[Dict],
        repo_path: str = ".",
    ) -> None:
        """Append a compliance snapshot to the JSONL history file."""
        by_type: Dict[str, int] = {}
        for v in violations:
            t = v.get("type", "unknown")
            by_type[t] = by_type.get(t, 0) + 1

        record = {
            "run_id": run_id,
            "timestamp": datetime.utcnow().isoformat(),
            "repo_path": str(repo_path),
            "violation_count": len(violations),
            "violations_by_type": by_type,
        }
        with self._history_path.open("a") as fh:
            fh.write(json.dumps(record) + "\n")

    # ── Read ───────────────────────────────────────────────────────────────────

    def _load_history(self, repo_path: str) -> List[Dict]:
        if not self._history_path.exists():
            return []
        records = []
        with self._history_path.open() as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    r = json.loads(line)
                    if r.get("repo_path") == str(repo_path):
                        records.append(r)
                except json.JSONDecodeError:
                    pass
        return records

    def detect_drift(self, repo_path: str = ".", lookback: int = 10) -> Dict:
        """
        Compare the last two runs for this repo.

        Returns:
          direction     — "improving" | "stable" | "worsening"
          delta         — current_count - previous_count (negative = improving)
          current_count, previous_count
          trending_rules — rules whose count increased (worsening only)
          runs_analysed — total historical records available
        """
        records = self._load_history(repo_path)[-lookback:]
        if len(records) < 2:
            return {
                "direction": "stable",
                "delta": 0,
                "current_count": records[-1]["violation_count"] if records else 0,
                "previous_count": None,
                "trending_rules": [],
                "runs_analysed": len(records),
            }

        prev, curr = records[-2], records[-1]
        delta = curr["violation_count"] - prev["violation_count"]
        direction = "stable" if delta == 0 else ("improving" if delta < 0 else "worsening")

        trending: List[Dict] = []
        if direction == "worsening":
            for rule, count in curr["violations_by_type"].items():
                prev_count = prev["violations_by_type"].get(rule, 0)
                if count > prev_count:
                    trending.append({
                        "rule": rule,
                        "previous": prev_count,
                        "current": count,
                        "delta": count - prev_count,
                    })
            trending.sort(key=lambda x: -x["delta"])

        return {
            "direction": direction,
            "delta": delta,
            "current_count": curr["violation_count"],
            "previous_count": prev["violation_count"],
            "trending_rules": trending,
            "runs_analysed": len(records),
            "last_run_id": curr["run_id"],
            "prev_run_id": prev["run_id"],
        }

    def history(self, repo_path: str = ".", limit: int = 30) -> List[Dict]:
        """Return recent snapshots for sparkline charting."""
        return self._load_history(repo_path)[-limit:]
