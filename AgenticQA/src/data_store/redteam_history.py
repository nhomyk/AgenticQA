"""
Red team scan history — append-only JSONL time-series.

Records scanner_strength, gate_strength, bypass counts, and patch activity
after every red-team scan so the platform can surface a security posture
improvement curve over time.

Mirrors the LearningMetricsSnapshot pattern:
  - One JSON line per scan at ~/.agenticqa/redteam_history.jsonl
  - Append-only for cheap streaming reads and no corruption risk
  - Trend helpers: get_trend(), summary()
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

_DEFAULT_HISTORY_PATH = Path.home() / ".agenticqa" / "redteam_history.jsonl"


class RedTeamHistoryStore:
    """Records and retrieves per-scan red team metrics."""

    def __init__(self, history_path: Optional[Path] = None):
        self._path = Path(history_path) if history_path else _DEFAULT_HISTORY_PATH

    # ──────────────────────────────────────────────────────────────────────
    # Write
    # ──────────────────────────────────────────────────────────────────────

    def record(
        self,
        *,
        run_id: Optional[str] = None,
        mode: str = "fast",
        target: str = "both",
        bypass_attempts: int = 0,
        successful_bypasses: int = 0,
        scanner_strength: float = 0.0,
        gate_strength: float = 0.0,
        patches_applied: int = 0,
        proposals_generated: int = 0,
        status: str = "clean",
        prompt_injection_surface: Optional[float] = None,
        prompt_injection_findings: Optional[int] = None,
        extra: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Append a scan snapshot. Returns the recorded dict."""
        snapshot: Dict[str, Any] = {
            "run_id": run_id or datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ"),
            "recorded_at": datetime.now(timezone.utc).isoformat(),
            "mode": mode,
            "target": target,
            "bypass_attempts": bypass_attempts,
            "successful_bypasses": successful_bypasses,
            "scanner_strength": round(scanner_strength, 4),
            "gate_strength": round(gate_strength, 4),
            "patches_applied": patches_applied,
            "proposals_generated": proposals_generated,
            "status": status,
        }
        if prompt_injection_surface is not None:
            snapshot["prompt_injection_surface"] = round(prompt_injection_surface, 4)
        if prompt_injection_findings is not None:
            snapshot["prompt_injection_findings"] = prompt_injection_findings
        if extra:
            snapshot.update(extra)

        try:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            with open(self._path, "a") as f:
                f.write(json.dumps(snapshot) + "\n")
        except Exception:
            pass  # non-blocking — never crash a scan over history write

        return snapshot

    def record_from_result(
        self,
        result: Dict[str, Any],
        *,
        run_id: Optional[str] = None,
        mode: str = "fast",
        target: str = "both",
    ) -> Dict[str, Any]:
        """Convenience wrapper: pull fields directly from a RedTeamAgent result dict."""
        run_id = run_id or os.getenv("GITHUB_RUN_ID") or datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        return self.record(
            run_id=run_id,
            mode=mode,
            target=target,
            bypass_attempts=result.get("bypass_attempts", 0),
            successful_bypasses=result.get("successful_bypasses", 0),
            scanner_strength=result.get("scanner_strength", 0.0),
            gate_strength=result.get("gate_strength", 0.0),
            patches_applied=result.get("patches_applied", 0),
            proposals_generated=result.get("proposals_generated", 0),
            status=result.get("status", "clean"),
            prompt_injection_surface=result.get("prompt_injection_surface"),
            prompt_injection_findings=result.get("prompt_injection_findings"),
        )

    # ──────────────────────────────────────────────────────────────────────
    # Read
    # ──────────────────────────────────────────────────────────────────────

    def load_history(
        self,
        mode_filter: Optional[str] = None,
        limit: int = 50,
    ) -> List[Dict[str, Any]]:
        """Return the last `limit` scan records, optionally filtered by mode."""
        if not self._path.exists():
            return []
        records: List[Dict[str, Any]] = []
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
                    if mode_filter and rec.get("mode") != mode_filter:
                        continue
                    records.append(rec)
        except Exception:
            return []
        return records[-limit:]

    def get_trend(
        self,
        metric_key: str,
        window: int = 20,
        mode_filter: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Time-series of a single metric across the last `window` scans.

        Each point: {"run_id", "recorded_at", "value"}
        Only includes records that contain the requested metric.
        """
        history = self.load_history(mode_filter=mode_filter, limit=window * 3)
        curve = []
        for rec in history:
            if metric_key in rec:
                curve.append({
                    "run_id": rec["run_id"],
                    "recorded_at": rec["recorded_at"],
                    "value": rec[metric_key],
                })
        return curve[-window:]

    def summary(self, window: int = 10, mode_filter: Optional[str] = None) -> Dict[str, Any]:
        """Human-readable security posture summary across the last N scans."""
        history = self.load_history(mode_filter=mode_filter, limit=window)
        if not history:
            return {"scans": 0, "message": "No red team scan history yet."}

        def _avg(key: str) -> Optional[float]:
            vals = [r[key] for r in history if key in r and isinstance(r[key], (int, float))]
            return round(sum(vals) / len(vals), 4) if vals else None

        first_half = history[: max(len(history) // 2, 1)]
        second_half = history[max(len(history) // 2, 1):] or history

        def _avg_half(records: List, key: str) -> Optional[float]:
            vals = [r[key] for r in records if key in r and isinstance(r[key], (int, float))]
            return round(sum(vals) / len(vals), 4) if vals else None

        scanner_early = _avg_half(first_half, "scanner_strength")
        scanner_recent = _avg_half(second_half, "scanner_strength")

        scanner_trend = None
        if scanner_early is not None and scanner_recent is not None:
            delta = scanner_recent - scanner_early
            if delta > 0.02:
                scanner_trend = "hardening"
            elif delta < -0.02:
                scanner_trend = "degrading"
            else:
                scanner_trend = "stable"

        latest = history[-1] if history else {}

        return {
            "scans": len(history),
            "latest_scanner_strength": latest.get("scanner_strength"),
            "latest_gate_strength": latest.get("gate_strength"),
            "latest_status": latest.get("status"),
            "avg_scanner_strength": _avg("scanner_strength"),
            "avg_gate_strength": _avg("gate_strength"),
            "avg_bypasses": _avg("successful_bypasses"),
            "total_patches_applied": sum(r.get("patches_applied", 0) for r in history),
            "total_proposals_generated": sum(r.get("proposals_generated", 0) for r in history),
            "scanner_trend": scanner_trend,
            "scanner_strength_early_avg": scanner_early,
            "scanner_strength_recent_avg": scanner_recent,
        }
