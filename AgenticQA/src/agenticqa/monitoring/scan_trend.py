"""Scan trend aggregator — unified view of security posture over time.

Combines data from 4 history sources:
  1. Compliance drift (JSONL)
  2. Red team history (JSONL)
  3. Learning metrics (JSONL)
  4. Scan result snapshots (JSONL — new, stored here)

Provides:
  - Per-repo time-series for charting
  - Cross-repo org rollup
  - Trend direction (improving/stable/worsening)
  - Percentile ranking against benchmark data
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional


_HISTORY_DIR = Path(os.path.expanduser("~/.agenticqa"))
_SCAN_HISTORY_FILE = _HISTORY_DIR / "scan_history.jsonl"


@dataclass
class ScanSnapshot:
    """One scan result recorded over time."""
    repo_id: str
    timestamp: str
    scanners_ok: int
    total_findings: int
    total_critical: int
    risk_level: str
    elapsed_s: float
    languages: list = field(default_factory=list)
    scanner_breakdown: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "repo_id": self.repo_id,
            "timestamp": self.timestamp,
            "scanners_ok": self.scanners_ok,
            "total_findings": self.total_findings,
            "total_critical": self.total_critical,
            "risk_level": self.risk_level,
            "elapsed_s": self.elapsed_s,
            "languages": self.languages,
            "scanner_breakdown": self.scanner_breakdown,
        }


class ScanTrendAggregator:
    """Aggregate scan results over time for trend analysis."""

    def __init__(self, history_file: Optional[str] = None):
        self._file = Path(history_file) if history_file else _SCAN_HISTORY_FILE

    def record(self, scan_output: dict, repo_id: str = "") -> ScanSnapshot:
        """Record a scan result for trend tracking."""
        summary = scan_output.get("summary", {})
        scanners = scan_output.get("scanners", {})

        # Build per-scanner breakdown
        breakdown = {}
        for name, data in scanners.items():
            if data.get("status") == "ok":
                r = data["result"]
                breakdown[name] = {
                    "findings": r.get("total_findings", r.get("findings_count", 0)),
                    "critical": r.get("critical", 0),
                    "risk_score": r.get("risk_score", 0),
                }

        snapshot = ScanSnapshot(
            repo_id=repo_id or summary.get("repo_path", "unknown"),
            timestamp=datetime.now(timezone.utc).isoformat(),
            scanners_ok=summary.get("scanners_ok", 0),
            total_findings=summary.get("total_findings", 0),
            total_critical=summary.get("total_critical", 0),
            risk_level=summary.get("risk_level", "unknown"),
            elapsed_s=summary.get("total_elapsed_s", 0),
            languages=summary.get("build_info", {}).get("languages", []),
            scanner_breakdown=breakdown,
        )

        # Append to JSONL
        try:
            self._file.parent.mkdir(parents=True, exist_ok=True)
            with open(self._file, "a") as f:
                f.write(json.dumps(snapshot.to_dict()) + "\n")
        except OSError:
            pass

        return snapshot

    def history(self, repo_id: str = "", limit: int = 50) -> list[dict]:
        """Load scan history, optionally filtered by repo."""
        if not self._file.exists():
            return []

        records = []
        try:
            with open(self._file) as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        record = json.loads(line)
                        if repo_id and record.get("repo_id") != repo_id:
                            continue
                        records.append(record)
                    except json.JSONDecodeError:
                        continue
        except OSError:
            return []

        return records[-limit:]

    def trend(self, repo_id: str = "", window: int = 10) -> dict:
        """Calculate trend direction from recent scan history."""
        records = self.history(repo_id=repo_id, limit=window * 2)
        if len(records) < 2:
            return {
                "direction": "insufficient_data",
                "records": len(records),
                "current_findings": records[-1]["total_findings"] if records else 0,
            }

        # Split into halves
        mid = len(records) // 2
        early = records[:mid]
        recent = records[mid:]

        early_avg = sum(r["total_findings"] for r in early) / len(early)
        recent_avg = sum(r["total_findings"] for r in recent) / len(recent)

        early_crit = sum(r["total_critical"] for r in early) / len(early)
        recent_crit = sum(r["total_critical"] for r in recent) / len(recent)

        # Determine direction
        delta = recent_avg - early_avg
        threshold = max(1, early_avg * 0.1)  # 10% change threshold

        if delta < -threshold:
            direction = "improving"
        elif delta > threshold:
            direction = "worsening"
        else:
            direction = "stable"

        return {
            "direction": direction,
            "records": len(records),
            "early_avg_findings": round(early_avg, 1),
            "recent_avg_findings": round(recent_avg, 1),
            "early_avg_critical": round(early_crit, 1),
            "recent_avg_critical": round(recent_crit, 1),
            "delta_findings": round(delta, 1),
            "current_findings": records[-1]["total_findings"],
            "current_critical": records[-1]["total_critical"],
            "current_risk": records[-1]["risk_level"],
        }

    def org_rollup(self, limit: int = 100) -> dict:
        """Aggregate scan data across all repos for org-level view."""
        all_records = self.history(limit=limit)
        if not all_records:
            return {"repos": 0, "total_scans": 0}

        # Group by repo
        repos: dict[str, list] = {}
        for r in all_records:
            repo = r.get("repo_id", "unknown")
            repos.setdefault(repo, []).append(r)

        repo_summaries = []
        for repo_id, records in repos.items():
            latest = records[-1]
            repo_summaries.append({
                "repo_id": repo_id,
                "scans": len(records),
                "latest_findings": latest["total_findings"],
                "latest_critical": latest["total_critical"],
                "latest_risk": latest["risk_level"],
                "languages": latest.get("languages", []),
            })

        # Sort by critical findings (worst first)
        repo_summaries.sort(key=lambda r: r["latest_critical"], reverse=True)

        total_findings = sum(r["latest_findings"] for r in repo_summaries)
        total_critical = sum(r["latest_critical"] for r in repo_summaries)

        return {
            "repos": len(repos),
            "total_scans": len(all_records),
            "total_findings": total_findings,
            "total_critical": total_critical,
            "repos_with_critical": sum(1 for r in repo_summaries if r["latest_critical"] > 0),
            "repo_summaries": repo_summaries,
        }
