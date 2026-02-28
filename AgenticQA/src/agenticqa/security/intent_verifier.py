"""
IntentToCodeVerifier — verifies that LLM-generated code matches the stated intent.

The Problem
-----------
When a developer says "add rate limiting to the login endpoint" and an LLM
writes the code, two invisible failure modes appear:

  1. HALLUCINATION   — the LLM calls functions that don't exist, uses wrong
                       API signatures, imports non-existent modules, or invents
                       arguments. The code looks plausible but fails at runtime.

  2. INTENT GAP      — the code runs but doesn't implement what was asked.
                       "Add rate limiting" → LLM adds a TODO comment and a
                       passthrough function. Tests pass. Feature is missing.

This module catches both failure modes statically + heuristically, without
requiring the code to run.

Verification modes
------------------
STATIC_ONLY    — pure AST analysis (no LLM calls, always fast)
LLM_ASSISTED   — uses Haiku to perform semantic intent matching
                 (requires ANTHROPIC_API_KEY env var)

Usage
-----
    from agenticqa.security.intent_verifier import IntentToCodeVerifier

    verifier = IntentToCodeVerifier()
    result = verifier.verify(
        intent="Add rate limiting to the login endpoint — max 5 attempts per minute",
        code_diff=\"\"\"
        + def login(username, password):
        +     return authenticate(username, password)
        \"\"\",
        file_path="src/auth/login.py",
    )
    print(result.verdict)        # INTENT_MET | GAP_DETECTED | HALLUCINATION | UNCERTAIN
    print(result.confidence)     # 0.0–1.0
    print(result.issues)         # list of specific problems found
"""
from __future__ import annotations

import ast
import os
import re
import time
from dataclasses import dataclass, field
from typing import List, Optional

# ── Hallucination detection patterns ──────────────────────────────────────────

# Known stdlib/common library modules — anything else is suspicious if imported
# but not installed. We flag the most common hallucinated patterns.
_HALLUCINATED_CALL_PATTERNS = [
    # Non-existent requests methods
    (re.compile(r"\brequests\.get_with_retry\b"), "requests.get_with_retry() does not exist"),
    (re.compile(r"\brequests\.post_json\b"), "requests.post_json() does not exist"),
    # Non-existent os methods
    (re.compile(r"\bos\.makepath\b"), "os.makepath() does not exist (use os.makedirs)"),
    (re.compile(r"\bos\.path\.makedirs\b"), "os.path.makedirs() does not exist (use os.makedirs)"),
    # Non-existent dict methods
    (re.compile(r"\.has_key\("), ".has_key() removed in Python 3 (use 'in' operator)"),
    # Non-existent string methods
    (re.compile(r"\.startswith_any\("), ".startswith_any() does not exist"),
    # Common LLM-invented Flask/FastAPI patterns
    (re.compile(r"@app\.route_get\b"), "@app.route_get() does not exist (use @app.get)"),
    (re.compile(r"@app\.route_post\b"), "@app.route_post() does not exist (use @app.post)"),
    # Invented SQLAlchemy
    (re.compile(r"\.query\.filter_first\("), ".filter_first() does not exist (use .filter().first())"),
    # Non-existent json
    (re.compile(r"\bjson\.dumps_pretty\b"), "json.dumps_pretty() does not exist (use indent=)"),
    # Invented asyncio
    (re.compile(r"\basyncio\.run_async\b"), "asyncio.run_async() does not exist"),
    # Generic invented patterns
    (re.compile(r"\butil\.retry\b"), "util.retry() — verify this module exists in the repo"),
    (re.compile(r"\bhelpers\.validate\b"), "helpers.validate() — verify this function exists"),
]

# Intent keywords → code patterns that should be present
# Maps a keyword in the intent to a regex that should match in the code diff
_INTENT_SIGNALS: list[tuple[re.Pattern, re.Pattern, str]] = [
    # rate limit
    (re.compile(r"\brate.?limit", re.I),
     re.compile(r"rate.?limit|throttle|limiter|RateLimit|slowapi|flask.limiter|ratelimiter", re.I),
     "rate limiting"),
    # authentication / login
    (re.compile(r"\bauthenticate|login|sign.?in\b", re.I),
     re.compile(r"authenticate|login|password|token|jwt|oauth|session", re.I),
     "authentication"),
    # encryption
    (re.compile(r"\bencrypt|cipher|hash\b", re.I),
     re.compile(r"encrypt|cipher|bcrypt|hashlib|fernet|sha|aes|hmac", re.I),
     "encryption"),
    # database / persistence
    (re.compile(r"\bsave|persist|database|store\b", re.I),
     re.compile(r"\.save\(|\.commit\(|db\.|session\.|INSERT|UPDATE|\.add\(", re.I),
     "database write"),
    # validation
    (re.compile(r"\bvalidat|check|verify\b", re.I),
     re.compile(r"validate|raise|assert|ValueError|if.*error|pydantic|schema|zod", re.I),
     "validation"),
    # error handling
    (re.compile(r"\berror.?handl|except|try.?catch\b", re.I),
     re.compile(r"try:|except|catch|raise|Exception|Error", re.I),
     "error handling"),
    # logging
    (re.compile(r"\blog|audit|track\b", re.I),
     re.compile(r"log\.|logger|logging|print|audit|track", re.I),
     "logging"),
    # delete / remove
    (re.compile(r"\bdelete|remove|drop\b", re.I),
     re.compile(r"\.delete\(|\.remove\(|DROP|del |unlink|rmdir", re.I),
     "delete operation"),
    # test
    (re.compile(r"\btest|spec\b", re.I),
     re.compile(r"def test_|describe\(|it\(|expect\(|assert", re.I),
     "test cases"),
    # API endpoint
    (re.compile(r"\bendpoint|route|api\b", re.I),
     re.compile(r"@app\.|@router\.|def get_|def post_|async def|router\.", re.I),
     "API endpoint"),
    # caching
    (re.compile(r"\bcach(e|ing|ed)?\b", re.I),
     re.compile(r"cache|redis|memcache|lru_cache|@cache|ttl", re.I),
     "caching"),
    # pagination
    (re.compile(r"\bpaginat|page|offset|limit\b", re.I),
     re.compile(r"page|offset|limit|paginate|cursor|skip", re.I),
     "pagination"),
]

# Patterns that indicate empty / stub implementations
_STUB_PATTERNS = [
    re.compile(r"^\s*pass\s*$", re.MULTILINE),
    re.compile(r"#\s*TODO|#\s*FIXME|#\s*PLACEHOLDER|#\s*IMPLEMENT", re.IGNORECASE),
    re.compile(r'""".*TODO.*"""', re.DOTALL | re.IGNORECASE),
    re.compile(r"raise NotImplementedError"),
    re.compile(r"return None\s*#.*stub|stub.*return None", re.IGNORECASE),
]

# Extract only added lines from a unified diff
_ADDED_LINE_RE = re.compile(r"^\+(?!\+\+)(.*)$", re.MULTILINE)


# ── Dataclasses ───────────────────────────────────────────────────────────────

@dataclass
class IntentIssue:
    """A specific problem found during verification."""
    issue_type: str       # HALLUCINATION | INTENT_GAP | STUB | SYNTAX_ERROR
    severity: str         # critical | high | medium | low
    description: str
    line_snippet: str = ""

    def to_dict(self) -> dict:
        return {
            "issue_type": self.issue_type,
            "severity": self.severity,
            "description": self.description,
            "line_snippet": self.line_snippet[:200],
        }


@dataclass
class IntentVerificationResult:
    """
    Result of verifying that code implements the stated intent.

    verdict:
      INTENT_MET     — code appears to implement the intent correctly
      GAP_DETECTED   — intent keywords have no matching implementation
      HALLUCINATION  — invented APIs or non-existent functions detected
      STUB_ONLY      — code is placeholder / TODO / pass
      UNCERTAIN      — not enough signal to determine (very short diff, etc.)
    """
    verdict: str                  # INTENT_MET | GAP_DETECTED | HALLUCINATION | STUB_ONLY | UNCERTAIN
    confidence: float             # 0.0–1.0
    intent_summary: str           # paraphrased intent
    issues: List[IntentIssue]
    intent_signals_found: List[str]   # which intent keywords matched code
    intent_signals_missing: List[str] # which intent keywords had no match
    added_lines: int
    llm_analysis: Optional[str] = None  # Haiku output if LLM_ASSISTED mode
    timestamp: float = field(default_factory=time.time)

    @property
    def is_safe_to_merge(self) -> bool:
        return self.verdict == "INTENT_MET" and not any(
            i.severity == "critical" for i in self.issues
        )

    def to_dict(self) -> dict:
        return {
            "verdict": self.verdict,
            "confidence": round(self.confidence, 3),
            "intent_summary": self.intent_summary,
            "is_safe_to_merge": self.is_safe_to_merge,
            "issues": [i.to_dict() for i in self.issues],
            "intent_signals_found": self.intent_signals_found,
            "intent_signals_missing": self.intent_signals_missing,
            "added_lines": self.added_lines,
            "llm_analysis": self.llm_analysis,
            "timestamp": self.timestamp,
        }


# ── Verifier ──────────────────────────────────────────────────────────────────

class IntentToCodeVerifier:
    """
    Verifies that code diffs implement the stated natural-language intent.

    Two modes:
      static_only=True  — fast, no API calls, heuristic only
      static_only=False — calls Claude Haiku for semantic analysis if
                          ANTHROPIC_API_KEY is set; falls back to static
    """

    def __init__(self, static_only: bool = True) -> None:
        self._static_only = static_only

    def verify(
        self,
        intent: str,
        code_diff: str,
        file_path: str = "",
    ) -> IntentVerificationResult:
        """
        Verify that code_diff implements intent.

        Args:
            intent:     Natural language description of what should be implemented
                        (e.g. "Add rate limiting to the login endpoint, max 5/min")
            code_diff:  Unified diff string (+ lines = added code)
                        OR plain code string if not a diff
            file_path:  Source file path (used for context only)

        Returns:
            IntentVerificationResult
        """
        # Extract added lines from diff (fall back to treating whole string as code)
        added_lines_text = self._extract_added_lines(code_diff)
        n_added = added_lines_text.count("\n") + 1 if added_lines_text.strip() else 0

        issues: List[IntentIssue] = []

        # ── 1. Syntax check (Python only) ─────────────────────────────────
        if file_path.endswith(".py") or self._looks_like_python(added_lines_text):
            syntax_issue = self._check_python_syntax(added_lines_text)
            if syntax_issue:
                issues.append(syntax_issue)

        # ── 2. Hallucination detection ────────────────────────────────────
        hallucination_issues = self._detect_hallucinations(added_lines_text)
        issues.extend(hallucination_issues)

        # ── 3. Stub detection ─────────────────────────────────────────────
        stub_issues = self._detect_stubs(added_lines_text)
        issues.extend(stub_issues)

        # ── 4. Intent signal matching ─────────────────────────────────────
        found_signals, missing_signals = self._match_intent_signals(intent, added_lines_text)

        # ── 5. LLM semantic analysis (optional) ──────────────────────────
        llm_analysis: Optional[str] = None
        if not self._static_only:
            llm_analysis = self._llm_verify(intent, added_lines_text)

        # ── 6. Determine verdict ──────────────────────────────────────────
        verdict, confidence = self._determine_verdict(
            issues=issues,
            found_signals=found_signals,
            missing_signals=missing_signals,
            n_added=n_added,
            llm_analysis=llm_analysis,
        )

        return IntentVerificationResult(
            verdict=verdict,
            confidence=confidence,
            intent_summary=intent[:200],
            issues=issues,
            intent_signals_found=found_signals,
            intent_signals_missing=missing_signals,
            added_lines=n_added,
            llm_analysis=llm_analysis,
        )

    # ── Internal helpers ──────────────────────────────────────────────────────

    @staticmethod
    def _extract_added_lines(diff: str) -> str:
        """Extract added lines from a unified diff. Falls back to full string."""
        added = _ADDED_LINE_RE.findall(diff)
        if added:
            return "\n".join(added)
        return diff  # not a diff — treat as plain code

    @staticmethod
    def _looks_like_python(code: str) -> bool:
        py_signals = ["def ", "import ", "class ", "    ", "return ", "self."]
        return sum(1 for s in py_signals if s in code) >= 2

    @staticmethod
    def _check_python_syntax(code: str) -> Optional[IntentIssue]:
        try:
            ast.parse(code)
        except SyntaxError as e:
            return IntentIssue(
                issue_type="SYNTAX_ERROR",
                severity="critical",
                description=f"Python syntax error: {e.msg} (line {e.lineno})",
                line_snippet=str(e.text or ""),
            )
        return None

    @staticmethod
    def _detect_hallucinations(code: str) -> List[IntentIssue]:
        issues: List[IntentIssue] = []
        for pattern, description in _HALLUCINATED_CALL_PATTERNS:
            m = pattern.search(code)
            if m:
                start = max(0, m.start() - 20)
                snippet = code[start: m.end() + 40].strip()
                issues.append(IntentIssue(
                    issue_type="HALLUCINATION",
                    severity="high",
                    description=f"Likely hallucinated API: {description}",
                    line_snippet=snippet,
                ))
        return issues

    @staticmethod
    def _detect_stubs(code: str) -> List[IntentIssue]:
        issues: List[IntentIssue] = []
        for pattern in _STUB_PATTERNS:
            m = pattern.search(code)
            if m:
                issues.append(IntentIssue(
                    issue_type="STUB",
                    severity="high",
                    description="Code appears to be a stub or placeholder — no real implementation.",
                    line_snippet=m.group(0)[:100].strip(),
                ))
                break  # one stub warning is enough
        return issues

    @staticmethod
    def _match_intent_signals(intent: str, code: str) -> tuple[list, list]:
        found, missing = [], []
        for intent_re, code_re, label in _INTENT_SIGNALS:
            if intent_re.search(intent):
                if code_re.search(code):
                    found.append(label)
                else:
                    missing.append(label)
        return found, missing

    @staticmethod
    def _llm_verify(intent: str, code: str) -> Optional[str]:
        """Call Claude Haiku to semantically verify intent vs code."""
        api_key = os.getenv("ANTHROPIC_API_KEY", "")
        if not api_key:
            return None
        try:
            import anthropic
            client = anthropic.Anthropic(api_key=api_key)
            prompt = (
                f"You are a code review assistant. A developer stated this intent:\n"
                f'"{intent}"\n\n'
                f"The following code was added:\n```\n{code[:3000]}\n```\n\n"
                f"Answer in 2-3 sentences:\n"
                f"1. Does the code implement the stated intent? (yes/no/partially)\n"
                f"2. What is missing or incorrect, if anything?\n"
                f"3. Are there any obviously hallucinated or non-existent APIs?\n"
                f"Be precise and technical."
            )
            msg = client.messages.create(
                model="claude-haiku-4-5-20251001",
                max_tokens=300,
                messages=[{"role": "user", "content": prompt}],
            )
            return msg.content[0].text
        except Exception as e:
            return f"LLM analysis unavailable: {e}"

    @staticmethod
    def _determine_verdict(
        issues: List[IntentIssue],
        found_signals: List[str],
        missing_signals: List[str],
        n_added: int,
        llm_analysis: Optional[str],
    ) -> tuple[str, float]:
        """Return (verdict, confidence)."""

        # Any syntax error → definite fail
        if any(i.issue_type == "SYNTAX_ERROR" for i in issues):
            return "HALLUCINATION", 0.95

        # Any hallucination → flag it immediately (even short diffs)
        has_hallucination = any(i.issue_type == "HALLUCINATION" for i in issues)
        if has_hallucination:
            if any(i.issue_type == "SYNTAX_ERROR" for i in issues):
                return "HALLUCINATION", 0.95
            return "HALLUCINATION", 0.85

        # Pure stub with nothing real
        has_stub = any(i.issue_type == "STUB" for i in issues)
        if has_stub and n_added < 10:
            return "STUB_ONLY", 0.90

        # Not enough code to evaluate
        if n_added < 3:
            return "UNCERTAIN", 0.3

        # No intent signals at all (couldn't match anything from intent keywords)
        if not found_signals and not missing_signals:
            return "UNCERTAIN", 0.4

        # Calculate gap ratio
        total = len(found_signals) + len(missing_signals)
        gap_ratio = len(missing_signals) / total if total > 0 else 0

        if gap_ratio >= 0.7:
            return "GAP_DETECTED", 0.80
        if gap_ratio >= 0.4:
            return "GAP_DETECTED", 0.60

        # LLM boosting if available
        llm_negative = False
        if llm_analysis:
            lower = llm_analysis.lower()
            if any(w in lower for w in ["no,", "missing", "not implement", "doesn't implement", "hallucin"]):
                llm_negative = True

        if llm_negative and gap_ratio > 0:
            return "GAP_DETECTED", 0.70

        confidence = max(0.5, 1.0 - gap_ratio - 0.05 * len(issues))
        return "INTENT_MET", round(min(confidence, 0.98), 2)
