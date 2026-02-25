"""
Developer risk PR gate — evaluates changed files against developer risk scores.

Blocks merges when files are owned by high-risk authors (score >= threshold).
Integrates with DeveloperProfile EWMA scores accumulated across CI runs.
"""
from __future__ import annotations

from pathlib import Path
from typing import Dict, List, Optional

DEFAULT_THRESHOLD = 0.70


class DeveloperRiskGate:
    """Evaluate a list of changed files and return a pass/block decision."""

    def __init__(
        self,
        threshold: float = DEFAULT_THRESHOLD,
        store_dir: Optional[Path] = None,
    ):
        self.threshold = threshold
        self._store_dir = store_dir  # forwarded to DeveloperProfile for testability

    def evaluate(
        self,
        files: List[str],
        repo_id: str,
        cwd: str = ".",
    ) -> Dict:
        """
        For each file, find its primary author via git blame and check their risk score.

        Returns:
          gate            — "pass" | "block"
          high_risk_files — [{file, dev_hash, risk_score}] sorted by score desc
          max_risk        — highest individual score (0.0 if no profiles found)
          threshold       — the value used
          files_checked   — number of files for which a profile was found
        """
        from data_store.developer_profile import DeveloperProfile

        high_risk: List[Dict] = []
        max_risk = 0.0
        checked = 0

        for f in files:
            try:
                kwargs: Dict = {"cwd": cwd}
                if self._store_dir is not None:
                    kwargs["store_dir"] = self._store_dir
                profile = DeveloperProfile.for_file(f, repo_id=repo_id, **kwargs)
                if profile is None:
                    continue
                checked += 1
                score = profile.risk_score
                max_risk = max(max_risk, score)
                if score >= self.threshold:
                    high_risk.append({
                        "file": f,
                        "dev_hash": profile.dev_hash,
                        "risk_score": round(score, 4),
                    })
            except Exception:
                pass

        high_risk.sort(key=lambda x: -x["risk_score"])
        return {
            "gate": "block" if high_risk else "pass",
            "high_risk_files": high_risk,
            "max_risk": round(max_risk, 4),
            "threshold": self.threshold,
            "files_checked": checked,
        }
