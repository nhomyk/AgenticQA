"""
Cross-repo org memory.

Aggregates SRE violation patterns across all repos in a GitHub org so that
patterns discovered in repo A immediately inform repo B.  The more repos
onboarded, the smarter every individual repo becomes — a compounding network
effect that no per-repo CI tool can match.

Storage: ~/.agenticqa/orgs/{org_id}/memory.json
  org_id = sha1(org_name.lower())[:12]  — same algorithm as repo_id / dev_hash

Schema
------
{
  "org_id": "...",
  "org_name": "...",
  "repos_seen": ["repo_id1", ...],
  "total_runs": int,
  "rules": {
    "E501": {
      "total_violations": int,
      "total_fixes": int,
      "fix_rate": float,   # EWMA across all repos
      "repos": ["repo_id1", ...]
    }, ...
  },
  "unfixable_rules": ["F403", ...],   # fix_rate < 0.05 after >= 5 total violations
  "last_updated": ISO8601,
}
"""
from __future__ import annotations

import hashlib
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional


def _org_from_remote(repo_path: str = ".") -> tuple[str, str]:
    """Return (org_name, org_id) from git remote URL. Falls back to 'unknown'."""
    try:
        proc = subprocess.run(
            ["git", "remote", "get-url", "origin"],
            capture_output=True, text=True, timeout=5, cwd=repo_path,
        )
        url = proc.stdout.strip()
        # Extract org: github.com/ORG/repo or git@github.com:ORG/repo
        for sep in ["/", ":"]:
            parts = url.replace("https://github.com/", "").replace("git@github.com:", "").split("/")
            if len(parts) >= 2:
                org = parts[0].lower().strip()
                if org:
                    org_id = hashlib.sha1(org.encode()).hexdigest()[:12]
                    return org, org_id
    except Exception:
        pass
    return "unknown", "unknown"


class OrgMemory:
    """
    Per-org violation memory accumulated across all repos.

    Instantiate with a repo_path to auto-detect the org from git remote, or
    pass org_name directly.
    """

    _EWMA_ALPHA = 0.3

    def __init__(
        self,
        org_name: str = "unknown",
        org_id: Optional[str] = None,
        store_dir: Optional[Path] = None,
    ):
        self.org_name = org_name
        self.org_id = org_id or hashlib.sha1(org_name.encode()).hexdigest()[:12]
        self._dir = (
            Path(store_dir) if store_dir
            else Path.home() / ".agenticqa" / "orgs" / self.org_id
        )
        self._path = self._dir / "memory.json"
        self._data: Dict[str, Any] = self._load()

    # ── Factory ────────────────────────────────────────────────────────────────

    @classmethod
    def for_repo(cls, repo_path: str = ".", **kwargs) -> "OrgMemory":
        """Auto-detect org from git remote URL of the given repo."""
        org_name, org_id = _org_from_remote(repo_path)
        return cls(org_name=org_name, org_id=org_id, **kwargs)

    # ── Persistence ────────────────────────────────────────────────────────────

    def _load(self) -> Dict[str, Any]:
        if self._path.exists():
            try:
                return json.loads(self._path.read_text())
            except Exception:
                pass
        return {
            "org_id": self.org_id,
            "org_name": self.org_name,
            "repos_seen": [],
            "total_runs": 0,
            "rules": {},
            "unfixable_rules": [],
            "last_updated": datetime.now(timezone.utc).isoformat(),
        }

    def save(self) -> None:
        try:
            self._dir.mkdir(parents=True, exist_ok=True)
            self._path.write_text(json.dumps(self._data, indent=2))
        except Exception:
            pass

    # ── Mutation ───────────────────────────────────────────────────────────────

    def update_from_sre_result(self, repo_id: str, sre_result: Dict[str, Any]) -> None:
        """
        Ingest one SRE agent result into org memory.

        Called after each SRE run; updates per-rule EWMA fix rates and
        refreshes the unfixable_rules list.
        """
        if not sre_result:
            return

        fixes_by_rule: Dict[str, int] = {}
        for fix in sre_result.get("fixes", []):
            r = fix.get("rule", "unknown")
            fixes_by_rule[r] = fixes_by_rule.get(r, 0) + 1

        # Tally violations from fixes list + architectural violations
        violations_by_rule: Dict[str, int] = {}
        for fix in sre_result.get("fixes", []):
            r = fix.get("rule", "unknown")
            violations_by_rule[r] = violations_by_rule.get(r, 0) + 1
        for r, count in sre_result.get("architectural_violations_by_rule", {}).items():
            violations_by_rule[r] = violations_by_rule.get(r, 0) + count

        rules = self._data.setdefault("rules", {})
        for rule, vcount in violations_by_rule.items():
            fcount = fixes_by_rule.get(rule, 0)
            entry = rules.setdefault(rule, {
                "total_violations": 0, "total_fixes": 0, "fix_rate": 0.0, "repos": []
            })
            entry["total_violations"] += vcount
            entry["total_fixes"] += fcount
            # EWMA of fix rate for this rule
            new_obs = fcount / vcount if vcount else 0.0
            entry["fix_rate"] = round(
                self._EWMA_ALPHA * new_obs + (1 - self._EWMA_ALPHA) * entry["fix_rate"], 4
            )
            if repo_id not in entry["repos"]:
                entry["repos"].append(repo_id)

        # Update repo list and run count
        repos_seen = self._data.setdefault("repos_seen", [])
        if repo_id not in repos_seen:
            repos_seen.append(repo_id)
        self._data["total_runs"] = self._data.get("total_runs", 0) + 1
        self._data["last_updated"] = datetime.now(timezone.utc).isoformat()

        # Refresh unfixable: fix_rate < 0.05 and >= 5 total violations
        self._data["unfixable_rules"] = [
            r for r, e in rules.items()
            if e["total_violations"] >= 5 and e["fix_rate"] < 0.05
        ]
        self.save()

    # ── Read ───────────────────────────────────────────────────────────────────

    def summary(self) -> Dict[str, Any]:
        """Return a JSON-serialisable summary for the API and dashboard."""
        rules = self._data.get("rules", {})
        top_rules = sorted(
            rules.items(), key=lambda x: x[1]["total_violations"], reverse=True
        )[:10]
        return {
            "org_id": self.org_id,
            "org_name": self.org_name,
            "repos_seen": len(self._data.get("repos_seen", [])),
            "total_runs": self._data.get("total_runs", 0),
            "unfixable_rules": self._data.get("unfixable_rules", []),
            "top_rules": [
                {"rule": r, **e} for r, e in top_rules
            ],
            "last_updated": self._data.get("last_updated"),
        }

    @property
    def unfixable_rules(self) -> List[str]:
        return self._data.get("unfixable_rules", [])
