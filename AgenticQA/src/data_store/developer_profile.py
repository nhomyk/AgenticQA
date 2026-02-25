"""
Per-developer risk memory.

Attributes code violations to developers using git blame, then accumulates
an EWMA risk score across CI runs. The longer the platform runs, the more
accurate the per-developer risk picture becomes — a compounding moat.

Storage: ~/.agenticqa/developers/{repo_id}/{dev_hash}.json
Privacy: developer emails are SHA-1 hashed before storage (same pattern as repo_id).

EWMA α = 0.3 — same as RepoProfile, so recent runs weigh more than historical ones.
"""
from __future__ import annotations

import hashlib
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional


def _hash_email(email: str) -> str:
    """One-way hash of a developer email — same algorithm as repo_id."""
    return hashlib.sha1(email.lower().strip().encode()).hexdigest()[:12]


def _get_primary_author(file_path: str, cwd: Optional[str] = None) -> Optional[str]:
    """
    Run git blame --porcelain on the file and return the email of the author
    responsible for the most lines.

    Returns None if git blame fails (untracked file, fresh repo, no git, etc.).
    """
    try:
        proc = subprocess.run(
            ["git", "blame", "--porcelain", file_path],
            capture_output=True,
            text=True,
            timeout=10,
            cwd=cwd or ".",
        )
        if proc.returncode != 0 or not proc.stdout:
            return None
        emails: Dict[str, int] = {}
        for line in proc.stdout.splitlines():
            if line.startswith("author-mail "):
                email = line.removeprefix("author-mail ").strip().strip("<>")
                if email and email != "not.committed.yet":
                    emails[email] = emails.get(email, 0) + 1
        if not emails:
            return None
        return max(emails, key=emails.__getitem__)
    except Exception:
        return None


class DeveloperProfile:
    """
    Accumulates per-developer violation patterns across CI runs.

    Risk score (0.0–1.0) is an EWMA of observation values, where:
      - observation = 1.0  if a violation was NOT auto-fixed (unfixable or architectural)
      - observation = 0.0  if a violation was auto-fixed (low actual risk)
    """

    _ALPHA = 0.3  # EWMA weight for new observations (same as RepoProfile)

    def __init__(
        self,
        dev_hash: str,
        repo_id: str,
        store_dir: Optional[Path] = None,
    ):
        self.dev_hash = dev_hash
        self.repo_id = repo_id
        self._dir = (
            Path(store_dir)
            if store_dir
            else Path.home() / ".agenticqa" / "developers" / repo_id
        )
        self._path = self._dir / f"{dev_hash}.json"
        self._data: Dict[str, Any] = self._load()

    # ── Factory methods ───────────────────────────────────────────────────────

    @classmethod
    def for_file(
        cls,
        file_path: str,
        repo_id: str,
        cwd: Optional[str] = None,
        **kwargs,
    ) -> Optional["DeveloperProfile"]:
        """
        Look up the primary author of a file via git blame and return their profile.
        Returns None if blame fails (untracked file, fresh repo, etc.).
        """
        email = _get_primary_author(file_path, cwd=cwd)
        if not email:
            return None
        dev_hash = _hash_email(email)
        return cls(dev_hash, repo_id, **kwargs)

    @classmethod
    def for_email(
        cls,
        email: str,
        repo_id: str,
        **kwargs,
    ) -> "DeveloperProfile":
        """Directly instantiate by email (no git blame needed)."""
        dev_hash = _hash_email(email)
        return cls(dev_hash, repo_id, **kwargs)

    # ── Persistence ───────────────────────────────────────────────────────────

    def _load(self) -> Dict[str, Any]:
        if self._path.exists():
            try:
                return json.loads(self._path.read_text())
            except Exception:
                pass
        return {
            "dev_hash": self.dev_hash,
            "repo_id": self.repo_id,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "total_violations": 0,
            "total_fixes": 0,
            "risk_score": 0.0,
            "violations_by_rule": {},
            "run_history": [],
        }

    def save(self) -> None:
        try:
            self._dir.mkdir(parents=True, exist_ok=True)
            self._path.write_text(json.dumps(self._data, indent=2))
        except Exception:
            pass  # non-blocking; best-effort persistence

    # ── Mutation ──────────────────────────────────────────────────────────────

    def record_violation(self, rule: str, fixed: bool) -> None:
        """
        Record one violation event and update the EWMA risk score.

        Args:
            rule: Lint/CVE rule identifier (e.g. "E501", "F401", "CVE-2024-1234")
            fixed: Whether this violation was automatically fixed this run
        """
        self._data["total_violations"] = self._data.get("total_violations", 0) + 1
        if fixed:
            self._data["total_fixes"] = self._data.get("total_fixes", 0) + 1

        # Per-rule counts
        by_rule = self._data.setdefault("violations_by_rule", {})
        entry = by_rule.setdefault(rule, {"count": 0, "fixes": 0})
        entry["count"] += 1
        if fixed:
            entry["fixes"] += 1

        # EWMA risk score: unfixed = high risk (1.0), fixed = low risk (0.0)
        observation = 0.0 if fixed else 1.0
        prior = self._data.get("risk_score", 0.0)
        self._data["risk_score"] = round(
            self._ALPHA * observation + (1 - self._ALPHA) * prior, 4
        )
        self._data["last_seen"] = datetime.now(timezone.utc).isoformat()
        self.save()

    def record_run(
        self,
        run_id: str,
        violations: int,
        fixes: int,
    ) -> None:
        """Record a run-level summary for historical tracking. Keeps last 30 entries."""
        history: List[Dict] = self._data.setdefault("run_history", [])
        history.append({
            "run_id": run_id,
            "violations": violations,
            "fixes": fixes,
            "fix_rate": round(fixes / max(violations, 1), 4),
            "recorded_at": datetime.now(timezone.utc).isoformat(),
        })
        self._data["run_history"] = history[-30:]
        self.save()

    # ── Read ──────────────────────────────────────────────────────────────────

    @property
    def risk_score(self) -> float:
        return self._data.get("risk_score", 0.0)

    @property
    def total_violations(self) -> int:
        return self._data.get("total_violations", 0)

    @property
    def total_fixes(self) -> int:
        return self._data.get("total_fixes", 0)

    def summary(self) -> Dict[str, Any]:
        """Human-readable summary for the API and dashboard."""
        top_rules = sorted(
            self._data.get("violations_by_rule", {}).items(),
            key=lambda x: x[1]["count"],
            reverse=True,
        )[:5]
        return {
            "dev_hash": self.dev_hash,
            "repo_id": self.repo_id,
            "risk_score": self.risk_score,
            "total_violations": self.total_violations,
            "total_fixes": self.total_fixes,
            "top_rules": [{"rule": r, **stats} for r, stats in top_rules],
            "last_seen": self._data.get("last_seen"),
            "created_at": self._data.get("created_at"),
        }


class DeveloperRiskLeaderboard:
    """
    Aggregates DeveloperProfile summaries across a repo for the risk leaderboard.
    Reads all ~/.agenticqa/developers/{repo_id}/*.json files.
    """

    def __init__(self, repo_id: str, store_dir: Optional[Path] = None):
        self.repo_id = repo_id
        self._dir = (
            Path(store_dir)
            if store_dir
            else Path.home() / ".agenticqa" / "developers" / repo_id
        )

    def top_n(self, n: int = 10) -> List[Dict[str, Any]]:
        """Return top-N developers by risk score (highest first)."""
        if not self._dir.exists():
            return []
        profiles = []
        for path in self._dir.glob("*.json"):
            try:
                data = json.loads(path.read_text())
                profiles.append(data)
            except Exception:
                continue
        profiles.sort(key=lambda d: d.get("risk_score", 0.0), reverse=True)
        return [
            {
                "dev_hash": p.get("dev_hash", path.stem),
                "risk_score": p.get("risk_score", 0.0),
                "total_violations": p.get("total_violations", 0),
                "total_fixes": p.get("total_fixes", 0),
                "last_seen": p.get("last_seen"),
            }
            for p in profiles[:n]
        ]
