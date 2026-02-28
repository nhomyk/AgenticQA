"""
PR Risk Pre-flight Scorer

Predicts the risk of a pull request *before* CI runs, so engineers know
what to expect and reviewers can triage accordingly.

Risk factors
------------
1. Author fix-rate history  — devs with low historical fix rates ship riskier code
2. Unfixable rules          — org memory flags rules that no one ever fixes
3. Architectural files      — changes to security/auth/database layers score higher
4. Learning metrics trend   — if the repo is declining overall, any PR is riskier
5. Diff volume              — large diffs have more surface area for bugs

Usage
-----
    from agenticqa.scoring.pr_risk_scorer import PRRiskScorer

    scorer = PRRiskScorer()
    report = scorer.score(
        author_email="dev@example.com",
        changed_files=["src/auth/login.py", "src/db/migrations.py"],
        diff_lines="+def greet(name):\n+    return f'Hello, {name}'\n",
        repo_path=".",
    )
    print(report.recommendation)   # LOW RISK | MEDIUM RISK | HIGH RISK
    print(report.risk_score)        # 0-100
    print(report.predicted_violations)
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional


# ── Risk weights ───────────────────────────────────────────────────────────────

_ARCH_PATTERNS = re.compile(
    r"(auth|login|token|jwt|passw|secret|crypt|oauth|session"
    r"|db|database|migration|model|schema"
    r"|payment|billing|stripe|checkout"
    r"|admin|permission|role|rbac"
    r"|config|setting|env|secret)",
    re.IGNORECASE,
)

_DIFF_DANGEROUS = re.compile(
    r"(os\.system|subprocess\.|eval\(|exec\(|pickle\.|yaml\.load\b"
    r"|hardcoded|password\s*=\s*['\"][^'\"]{4,}"
    r"|api_key\s*=\s*['\"][^'\"]{8,})",
    re.IGNORECASE,
)


@dataclass
class PRRiskReport:
    author_email: str
    risk_score: float                        # 0-100
    recommendation: str                      # LOW RISK | MEDIUM RISK | HIGH RISK
    predicted_violations: List[str] = field(default_factory=list)
    reasoning: List[str] = field(default_factory=list)
    author_fix_rate: Optional[float] = None  # None if no history
    unfixable_rules_hit: List[str] = field(default_factory=list)
    trend: str = "unknown"                   # improving | stable | declining | unknown

    def to_dict(self) -> dict:
        return {
            "author_email": self.author_email,
            "risk_score": round(self.risk_score, 1),
            "recommendation": self.recommendation,
            "predicted_violations": self.predicted_violations,
            "reasoning": self.reasoning,
            "author_fix_rate": self.author_fix_rate,
            "unfixable_rules_hit": self.unfixable_rules_hit,
            "trend": self.trend,
        }


class PRRiskScorer:
    """Score pull-request risk before CI runs."""

    def score(
        self,
        author_email: str,
        changed_files: List[str],
        diff_lines: str = "",
        repo_path: str = ".",
    ) -> PRRiskReport:
        score = 0.0
        reasoning: List[str] = []
        violations: List[str] = []
        unfixable: List[str] = []

        # ── 1. Author fix-rate history ─────────────────────────────────────────
        fix_rate = self._author_fix_rate(author_email, repo_path)
        if fix_rate is not None:
            if fix_rate < 0.3:
                score += 30
                reasoning.append(
                    f"Author has a low historical fix rate ({fix_rate:.0%}) — "
                    "issues they introduce are rarely resolved."
                )
                violations.append("LOW_AUTHOR_FIX_RATE")
            elif fix_rate < 0.6:
                score += 15
                reasoning.append(
                    f"Author fix rate is moderate ({fix_rate:.0%})."
                )
            else:
                reasoning.append(
                    f"Author has a strong fix rate ({fix_rate:.0%}) — lower risk."
                )
        else:
            score += 10
            reasoning.append("No history for this author — treating as unknown risk.")

        # ── 2. Org memory: unfixable rules ─────────────────────────────────────
        unfixable_rules = self._unfixable_rules(repo_path)
        if unfixable_rules:
            unfixable = list(unfixable_rules)
            score += min(len(unfixable_rules) * 5, 20)
            reasoning.append(
                f"Org memory: {len(unfixable_rules)} rule(s) are historically "
                f"never fixed in this repo: {', '.join(sorted(unfixable_rules)[:5])}"
            )
            violations.extend(f"UNFIXABLE:{r}" for r in sorted(unfixable_rules)[:5])

        # ── 3. Architectural / sensitive files ─────────────────────────────────
        arch_files = [f for f in changed_files if _ARCH_PATTERNS.search(f)]
        if arch_files:
            score += min(len(arch_files) * 8, 24)
            reasoning.append(
                f"{len(arch_files)} sensitive file(s) touched: "
                f"{', '.join(arch_files[:3])}"
            )
            violations.append("SENSITIVE_FILE_TOUCHED")

        # ── 4. Dangerous diff patterns ─────────────────────────────────────────
        danger_hits = _DIFF_DANGEROUS.findall(diff_lines)
        if danger_hits:
            score += min(len(danger_hits) * 10, 20)
            reasoning.append(
                f"Diff contains {len(danger_hits)} dangerous pattern(s): "
                f"{', '.join(set(danger_hits[:3]))}"
            )
            violations.append("DANGEROUS_DIFF_PATTERN")

        # ── 5. Learning metrics trend ──────────────────────────────────────────
        trend = self._learning_trend(repo_path)
        if trend == "declining":
            score += 10
            reasoning.append("Repo quality trend is declining — heightened review needed.")
        elif trend == "improving":
            score = max(score - 5, 0)
            reasoning.append("Repo quality trend is improving — slight risk reduction.")

        # ── 6. Diff volume ─────────────────────────────────────────────────────
        line_count = len(diff_lines.splitlines())
        if line_count > 500:
            score += 10
            reasoning.append(f"Large diff ({line_count} lines) — more surface area.")
        elif line_count > 200:
            score += 5
            reasoning.append(f"Medium diff ({line_count} lines).")

        score = min(score, 100.0)

        if score >= 60:
            rec = "HIGH RISK"
        elif score >= 30:
            rec = "MEDIUM RISK"
        else:
            rec = "LOW RISK"

        return PRRiskReport(
            author_email=author_email,
            risk_score=score,
            recommendation=rec,
            predicted_violations=violations,
            reasoning=reasoning,
            author_fix_rate=fix_rate,
            unfixable_rules_hit=unfixable,
            trend=trend,
        )

    # ── Private helpers ────────────────────────────────────────────────────────

    def _author_fix_rate(self, email: str, repo_path: str) -> Optional[float]:
        """Read fix rate from DeveloperProfile store if available.

        Uses the canonical repo_path on disk to derive a stable repo_id,
        avoiding any shell execution.
        """
        try:
            import hashlib
            import json

            # Derive repo_id from the resolved absolute path — no shell needed.
            resolved = str(Path(repo_path).resolve())
            repo_id = hashlib.md5(resolved.encode()).hexdigest()[:12]

            email_hash = hashlib.md5(email.lower().encode()).hexdigest()[:16]
            profile_path = (
                Path.home() / ".agenticqa" / "developers" / repo_id / f"{email_hash}.json"
            )
            if profile_path.exists():
                data = json.loads(profile_path.read_text())
                return data.get("ewma_fix_rate")
        except Exception:
            pass
        return None

    def _unfixable_rules(self, repo_path: str) -> set:
        """Load unfixable rules from org memory store."""
        try:
            from agenticqa.data_store.org_memory import OrgMemory
            mem = OrgMemory()
            return set(mem.unfixable_rules)
        except Exception:
            return set()

    def _learning_trend(self, repo_path: str) -> str:
        """Get overall learning trend for this repo."""
        try:
            from agenticqa.data_store.learning_metrics import LearningMetricsSnapshot
            snap = LearningMetricsSnapshot()
            summary = snap.summary()
            return summary.get("trend", "unknown")
        except Exception:
            return "unknown"
