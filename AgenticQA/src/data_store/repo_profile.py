"""
Repo-specific institutional memory.

Persists per-repo knowledge in ~/.agenticqa/repos/{repo_id}.json so that
agents accumulate codebase-specific patterns over time. The longer a client
uses the platform, the more tailored the analysis becomes — this is the
primary switching-cost moat.

repo_id is derived from the git remote URL (or directory path hash as fallback)
so it survives local directory moves and CI runner changes.
"""

import hashlib
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional


def _detect_repo_id(cwd: Optional[str] = None) -> str:
    """Derive a stable repo ID from git remote URL, falling back to path hash."""
    try:
        result = subprocess.run(
            ["git", "remote", "get-url", "origin"],
            capture_output=True, text=True, timeout=5,
            cwd=cwd,
        )
        url = result.stdout.strip()
        if url:
            # Normalise: strip .git suffix, lowercased
            url = url.lower().rstrip("/").removesuffix(".git")
            return hashlib.sha1(url.encode()).hexdigest()[:12]
    except Exception:
        pass

    # Fallback: hash the working directory path
    base = cwd or str(Path.cwd())
    return hashlib.sha1(base.encode()).hexdigest()[:12]


class RepoProfile:
    """Accumulates and retrieves repo-specific learning across CI runs."""

    def __init__(self, repo_id: str, store_dir: Optional[Path] = None):
        self.repo_id = repo_id
        self._dir = Path(store_dir) if store_dir else Path.home() / ".agenticqa" / "repos"
        self._path = self._dir / f"{repo_id}.json"
        self._data: Dict[str, Any] = self._load()

    # ──────────────────────────────────────────────────────────────────────
    # Factory
    # ──────────────────────────────────────────────────────────────────────

    @classmethod
    def for_current_repo(cls, cwd: Optional[str] = None, **kwargs) -> "RepoProfile":
        """Detect the current repo and load (or create) its profile."""
        repo_id = _detect_repo_id(cwd)
        return cls(repo_id, **kwargs)

    # ──────────────────────────────────────────────────────────────────────
    # Persistence
    # ──────────────────────────────────────────────────────────────────────

    def _load(self) -> Dict[str, Any]:
        if self._path.exists():
            try:
                return json.loads(self._path.read_text())
            except Exception:
                pass
        return {
            "repo_id": self.repo_id,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "total_runs": 0,
            "fix_rates_by_language": {},
            "known_architectural_violations": {},
            "known_unfixable_rules": [],
            "run_history": [],
        }

    def save(self) -> None:
        try:
            self._dir.mkdir(parents=True, exist_ok=True)
            self._path.write_text(json.dumps(self._data, indent=2))
        except Exception:
            pass

    # ──────────────────────────────────────────────────────────────────────
    # Update after a run
    # ──────────────────────────────────────────────────────────────────────

    def record_run(
        self,
        *,
        run_id: str,
        fix_rate: float,
        fixes_applied: int,
        fixable_errors: int,
        architectural_violations: Dict[str, int],
        language: Optional[str] = None,
    ) -> None:
        """Update profile with the results of one CI run."""
        self._data["total_runs"] = self._data.get("total_runs", 0) + 1
        self._data["last_seen"] = datetime.now(timezone.utc).isoformat()

        # Per-language fix rate (EWMA α=0.3 so recent runs weigh more)
        if language:
            lang_rates = self._data.setdefault("fix_rates_by_language", {})
            prior = lang_rates.get(language, fix_rate)
            lang_rates[language] = round(0.3 * fix_rate + 0.7 * prior, 4)

        # Accumulate architectural violation counts
        arch = self._data.setdefault("known_architectural_violations", {})
        for rule, count in architectural_violations.items():
            arch[rule] = arch.get(rule, 0) + count

        # Derive unfixable rules: any rule that's appeared in >2 runs architecturally
        self._data["known_unfixable_rules"] = [
            rule for rule, cnt in arch.items() if cnt >= 2
        ]

        # Compact run history (keep last 30)
        history: List[Dict] = self._data.setdefault("run_history", [])
        history.append({
            "run_id": run_id,
            "fix_rate": round(fix_rate, 4),
            "fixes_applied": fixes_applied,
            "fixable_errors": fixable_errors,
            "recorded_at": datetime.now(timezone.utc).isoformat(),
        })
        self._data["run_history"] = history[-30:]

        self.save()

    # ──────────────────────────────────────────────────────────────────────
    # Read
    # ──────────────────────────────────────────────────────────────────────

    @property
    def known_architectural_violations(self) -> Dict[str, int]:
        return self._data.get("known_architectural_violations", {})

    @property
    def known_unfixable_rules(self) -> List[str]:
        return self._data.get("known_unfixable_rules", [])

    @property
    def total_runs(self) -> int:
        return self._data.get("total_runs", 0)

    def fix_rate_for_language(self, language: str) -> Optional[float]:
        return self._data.get("fix_rates_by_language", {}).get(language)

    def summary(self) -> Dict[str, Any]:
        """Human-readable profile summary for dashboards and client reports."""
        history = self._data.get("run_history", [])
        recent_rates = [r["fix_rate"] for r in history[-5:]]
        return {
            "repo_id": self.repo_id,
            "total_runs": self.total_runs,
            "fix_rates_by_language": self._data.get("fix_rates_by_language", {}),
            "known_architectural_violations": self.known_architectural_violations,
            "known_unfixable_rules": self.known_unfixable_rules,
            "recent_avg_fix_rate": (
                round(sum(recent_rates) / len(recent_rates), 4) if recent_rates else None
            ),
            "last_seen": self._data.get("last_seen"),
        }
