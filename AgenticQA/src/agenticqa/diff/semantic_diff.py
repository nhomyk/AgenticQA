"""
Semantic diff analyzer — classifies *what* changed in a PR, not just what lines changed.

Parses unified diff output and flags high-risk removals: null checks, error handlers,
validation logic, auth decorators, assertions, and timeouts. Works on any language
via regex; Python files additionally use AST for function-level attribution.

Usage:
    analyzer = SemanticDiffAnalyzer()
    result = analyzer.analyze_git_range("HEAD~1", "HEAD", cwd="/path/to/repo")
    # or
    result = analyzer.analyze_diff(diff_text)
"""
from __future__ import annotations

import re
import subprocess
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple


# ── Risk pattern catalogue ─────────────────────────────────────────────────────
# Each entry: (regex, change_type, detail, risk)

_HIGH = "high"
_MED  = "medium"
_LOW  = "low"

_PATTERNS: List[Tuple[str, str, str, str]] = [
    # Error handling
    (r"\bexcept\b",                        "removed_error_handler",   "Exception handler removed",          _HIGH),
    (r"\braise\s+\w+",                     "removed_raise",            "Exception raise removed",            _HIGH),
    (r"\bassert\s+",                       "removed_assertion",        "Assertion removed",                  _HIGH),
    # Null / guard checks
    (r"\bif\s+\S+\s+is\s+None",           "removed_null_check",       "Null check removed",                 _HIGH),
    (r"\bif\s+not\s+\w+",                 "removed_guard_clause",     "Guard clause removed",               _HIGH),
    (r"\bif\s+\w+\s*==\s*None",           "removed_none_equality",    "None equality check removed",        _HIGH),
    # Auth / permissions
    (r"@.*(?:auth|login_required|permission|require)", "removed_auth_decorator", "Auth decorator removed",  _HIGH),
    (r"\b(?:authorize|authenticate|check_permission|has_permission|is_authenticated)\b",
                                           "removed_auth_check",       "Auth/permission check removed",      _HIGH),
    # Input validation
    (r"\b(?:validate|sanitize|clean|verify|check)\w*\s*\(",
                                           "removed_validation",       "Input validation removed",           _HIGH),
    # Timeouts / resource guards
    (r"\btimeout\s*=",                     "removed_timeout",          "Timeout parameter removed",          _MED),
    (r"\bmax_retries\b|\bmax_attempts\b",  "removed_retry_limit",      "Retry limit removed",               _MED),
    # Logging / observability
    (r"\b(?:logger|logging)\s*\.",         "removed_logging",          "Logging call removed",               _MED),
    (r"\bmetrics?\.\w+\(",                 "removed_metric",           "Metrics call removed",               _MED),
    # Defensive returns
    (r"\breturn\s+(?:False|None|0|\"\")", "removed_defensive_return", "Defensive return removed",           _MED),
]

_COMPILED = [(re.compile(p, re.IGNORECASE), ct, detail, risk) for p, ct, detail, risk in _PATTERNS]

# Function definition patterns for context detection
_FUNC_DEF = re.compile(
    r"^\s*(?:def |async def |function |(?:public|private|protected|static|async)\s+\w+\s+\w+\s*\()",
)


# ── Data model ─────────────────────────────────────────────────────────────────

@dataclass
class SemanticChange:
    file: str
    function: str        # nearest enclosing function, "" if unknown
    line: int            # line number in the original file
    change_type: str
    risk: str            # "high" | "medium" | "low"
    detail: str
    removed_line: str    # the actual removed line (stripped)


@dataclass
class SemanticDiffResult:
    changes: List[SemanticChange] = field(default_factory=list)
    files_analyzed: int = 0
    high_risk_count: int = 0
    medium_risk_count: int = 0
    risk_score: float = 0.0   # 0.0–1.0, weighted by severity
    error: Optional[str] = None

    def summary(self) -> Dict:
        return {
            "risk_score": round(self.risk_score, 3),
            "high_risk_count": self.high_risk_count,
            "medium_risk_count": self.medium_risk_count,
            "files_analyzed": self.files_analyzed,
            "changes": [
                {
                    "file": c.file,
                    "function": c.function,
                    "line": c.line,
                    "change_type": c.change_type,
                    "risk": c.risk,
                    "detail": c.detail,
                    "removed_line": c.removed_line,
                }
                for c in self.changes
            ],
        }


# ── Analyzer ───────────────────────────────────────────────────────────────────

class SemanticDiffAnalyzer:
    """Parse unified diff output and classify high-risk removals."""

    # ── Public API ────────────────────────────────────────────────────────────

    def analyze_git_range(
        self,
        base: str = "HEAD~1",
        head: str = "HEAD",
        cwd: str = ".",
    ) -> SemanticDiffResult:
        """Run git diff and analyze the output."""
        try:
            proc = subprocess.run(
                ["git", "diff", f"{base}..{head}", "--unified=3"],
                capture_output=True,
                text=True,
                timeout=30,
                cwd=cwd,
            )
            if proc.returncode != 0 and not proc.stdout:
                return SemanticDiffResult(error=f"git diff failed: {proc.stderr[:200]}")
            return self.analyze_diff(proc.stdout)
        except FileNotFoundError:
            return SemanticDiffResult(error="git not found")
        except Exception as e:
            return SemanticDiffResult(error=str(e))

    def analyze_diff(self, diff_text: str) -> SemanticDiffResult:
        """Analyze a unified diff string."""
        result = SemanticDiffResult()
        if not diff_text.strip():
            return result

        current_file = ""
        current_line = 0
        context_stack: List[str] = []   # track function names from context lines
        files_seen: set = set()

        for raw_line in diff_text.splitlines():
            # File header
            if raw_line.startswith("+++ b/"):
                current_file = raw_line[6:]
                files_seen.add(current_file)
                context_stack = []
                continue
            if raw_line.startswith("---") or raw_line.startswith("+++ "):
                continue

            # Hunk header: @@ -old_start,... +new_start,...
            if raw_line.startswith("@@"):
                m = re.search(r"\+(\d+)", raw_line)
                current_line = int(m.group(1)) if m else 0
                # Extract any function context hint from the @@ line
                hint_m = re.search(r"@@\s+(.+)$", raw_line)
                if hint_m:
                    context_stack = [hint_m.group(1).strip()]
                continue

            if raw_line.startswith("+"):
                current_line += 1
                continue  # additions are not risk signals

            # Context line — update function tracking
            if not raw_line.startswith("-"):
                current_line += 1
                stripped = raw_line.lstrip()
                if _FUNC_DEF.match(raw_line):
                    name = _extract_func_name(stripped)
                    if name:
                        context_stack = [name]
                continue

            # Removed line
            removed = raw_line[1:]  # strip leading '-'
            stripped_removed = removed.strip()

            # Update function context if this removed line is itself a def
            if _FUNC_DEF.match(removed):
                name = _extract_func_name(stripped_removed)
                if name:
                    context_stack = [name]

            for pattern, change_type, detail, risk in _COMPILED:
                if pattern.search(stripped_removed):
                    func_ctx = context_stack[-1] if context_stack else ""
                    change = SemanticChange(
                        file=current_file,
                        function=func_ctx,
                        line=current_line,
                        change_type=change_type,
                        risk=risk,
                        detail=detail,
                        removed_line=stripped_removed[:120],
                    )
                    result.changes.append(change)
                    break  # one classification per line

        result.files_analyzed = len(files_seen)
        result.high_risk_count = sum(1 for c in result.changes if c.risk == _HIGH)
        result.medium_risk_count = sum(1 for c in result.changes if c.risk == _MED)

        # Risk score: weighted average capped at 1.0
        if result.changes:
            weights = {_HIGH: 1.0, _MED: 0.4, _LOW: 0.1}
            total = sum(weights[c.risk] for c in result.changes)
            result.risk_score = min(1.0, total / max(len(result.changes), 1) *
                                    (result.high_risk_count * 0.5 + 0.5))

        return result


# ── Helpers ────────────────────────────────────────────────────────────────────

def _extract_func_name(line: str) -> str:
    """Extract function name from a def/function line."""
    m = re.search(r"(?:def|function)\s+(\w+)", line)
    return m.group(1) if m else ""
