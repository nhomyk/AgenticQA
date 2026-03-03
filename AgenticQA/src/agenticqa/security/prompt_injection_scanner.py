"""
Prompt injection static analysis scanner.

Scans codebases for prompt injection attack surface — code paths where
user-controlled input flows unfiltered into LLM system prompts, template
engines, eval() calls, or where the AI system role is overridable.

Subprocess-free: pure Python (re, pathlib). Mirrors LegalRiskScanner pattern.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Tuple


_SEVERITY_WEIGHTS: Dict[str, float] = {
    "critical": 1.0,
    "high": 0.7,
    "medium": 0.4,
    "low": 0.1,
}

_SOURCE_EXTS = {".py", ".ts", ".tsx", ".js", ".jsx", ".mjs", ".cjs"}

_SKIP_DIRS = {
    "node_modules", ".venv", "venv", "__pycache__",
    ".git", "dist", "build", ".next", "out",
}

# ---------------------------------------------------------------------------
# Patterns
# ---------------------------------------------------------------------------

# Direct concatenation of user input into prompt/system variables
_DIRECT_CONCAT_PATTERNS = [
    # f-string: prompt = f"...{user_input}..." or f"...{message}..."
    re.compile(
        r'(prompt|system_message|system|content)\s*[+]?=\s*f["\'].*\{(user_?input|user_message|message|query|request|body|text)\}',
        re.IGNORECASE,
    ),
    # Template literal: `...${userMessage}...` assigned to system/prompt var
    re.compile(
        r'(prompt|system_message|system|content)\s*[+]?=\s*`[^`]*\$\{(user[A-Za-z]*|message|query|request|body|text)\}',
        re.IGNORECASE,
    ),
    # Direct use of request body in LLM messages array
    re.compile(
        r'content\s*:\s*(request\.(body|text|json\(\))|body\.(message|query|prompt|input))',
        re.IGNORECASE,
    ),
    # String concatenation with + operator: prompt += user_input
    re.compile(
        r'(prompt|system_message|system|content|instruction)\s*\+=\s*.*\b(user|input|query|message|request)',
        re.IGNORECASE,
    ),
    # JavaScript concat: prompt = "..." + userInput
    re.compile(
        r'(prompt|systemMessage|system|content)\s*=\s*[^;]*\+\s*\b(user\w*|message|query|input|req\.\w+)',
        re.IGNORECASE,
    ),
]

# Template injection via .format() or % formatting with user data
_TEMPLATE_INJECT_PATTERNS = [
    re.compile(
        r'(prompt|system|template|instruction)\s*[+]?=.*\.format\s*\(',
        re.IGNORECASE,
    ),
    re.compile(
        r'(prompt|system|template)\s*%\s*(user_?input|message|query|request)',
        re.IGNORECASE,
    ),
    # Jinja2 render with user data
    re.compile(
        r'(render_template|Template\s*\(|from_string\s*\().*\b(user_?input|message|query|request)\b',
        re.IGNORECASE,
    ),
    # Broader .format() with user-like variables
    re.compile(
        r'\.format\s*\([^)]*\b(user_?input|user_?message|message|query|request|body)\b',
        re.IGNORECASE,
    ),
    # Mustache/Handlebars/EJS templates with user data
    re.compile(
        r'(?:\{\{|<%[=]?)\s*(?:user_?input|user_?message|message|query|body|input)\s*(?:\}\}|%>)',
        re.IGNORECASE,
    ),
]

# LLM output sent directly to dangerous sinks
_UNSAFE_OUTPUT_PATTERNS = [
    re.compile(
        r'(eval|exec)\s*\(\s*(llm_?output|response|completion|answer|result)',
        re.IGNORECASE,
    ),
    re.compile(
        r'subprocess\.(run|Popen|call|check_output)\s*\(.*\b(llm_?output|response|completion|answer)\b',
        re.IGNORECASE,
    ),
    re.compile(
        r'os\.(system|popen)\s*\(.*\b(llm_?output|response|completion|answer)\b',
        re.IGNORECASE,
    ),
    # innerHTML / dangerouslySetInnerHTML without sanitization
    re.compile(
        r'(innerHTML|dangerouslySetInnerHTML\s*=\s*\{\s*\{?\s*__html)\s*[:=]\s*(llm_?output|response|completion|answer)',
        re.IGNORECASE,
    ),
    # LLM output in SQL query (SQL injection via LLM)
    re.compile(
        r'(?:cursor|db|connection|session)\s*\.\s*(?:execute|query|raw)\s*\(.*\b(llm_?output|response|completion|answer|generated)',
        re.IGNORECASE,
    ),
    # LLM output used in import/module loading
    re.compile(
        r'(?:importlib\.|__import__|require)\s*\(.*\b(response|output|result|completion)',
        re.IGNORECASE,
    ),
]

# Chat API injection — user input flows directly into LLM messages construction
_CHAT_API_INJECTION_PATTERNS = [
    # messages.append with user-controlled content
    re.compile(
        r'messages\s*\.\s*append\s*\(\s*\{[^}]*content\s*:\s*(user_?input|message|query|req\.\w+|request\.\w+)',
        re.IGNORECASE,
    ),
    # Direct request body as LLM input (JS/TS)
    re.compile(
        r'content\s*[=:]\s*(?:req|request)\s*\.\s*(?:body|query|params|form)\s*[\[.]',
        re.IGNORECASE,
    ),
    # System message built from user input
    re.compile(
        r'role\s*[=:]\s*["\']system["\'].*content\s*[=:]\s*[^"\']*\b(user|input|query|message|req)\b',
        re.IGNORECASE,
    ),
]

# RAG context injection — retrieved content inserted into prompts without sanitization
_RAG_INJECTION_PATTERNS = [
    # Retrieved context directly concatenated into prompt
    re.compile(
        r'(prompt|system|template|instruction)\s*[+]?=\s*.*\b(context|retrieved|chunks?|documents?|passages?|search_results?)\b',
        re.IGNORECASE,
    ),
    # f-string with retrieved context
    re.compile(
        r'(prompt|system|content)\s*=\s*f["\'].*\{(?:context|retrieved|chunks?|documents?|passages?|search_results?)\}',
        re.IGNORECASE,
    ),
    # Template .format() with RAG results
    re.compile(
        r'\.format\s*\([^)]*(?:context|retrieved|chunks?|documents?|passages?|search_results?)\s*=',
        re.IGNORECASE,
    ),
]

# User controls role field in messages array
_ROLE_OVERRIDE_PATTERNS = [
    re.compile(
        r'role\s*:\s*(user_?role|params\b|body\b|request\b)',
        re.IGNORECASE,
    ),
    # User message inserted into system slot
    re.compile(
        r'\{\s*role\s*:\s*["\']system["\']\s*,\s*content\s*:\s*(user_?input|message|query|request|body)',
        re.IGNORECASE,
    ),
    # Dynamic role from variable
    re.compile(
        r'\{\s*role\s*:\s*[a-z_]*role[a-z_]*\s*,\s*content',
        re.IGNORECASE,
    ),
]


# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------

@dataclass
class InjectionFinding:
    file: str
    line: int
    rule_id: str
    severity: str
    message: str
    evidence: str = ""
    sink: str = ""


@dataclass
class InjectionScanResult:
    findings: List[InjectionFinding]
    surface_score: float    # 0.0–1.0, weighted by severity
    scan_error: Optional[str] = None

    # ── Convenience aliases ────────────────────────────────────────────────

    @property
    def risk_score(self) -> float:
        """Alias for ``surface_score`` — consistent with other scanners."""
        return self.surface_score

    @property
    def critical_findings(self) -> List[InjectionFinding]:
        return [f for f in self.findings if f.severity == "critical"]

    @property
    def total_findings(self) -> int:
        return len(self.findings)


# ---------------------------------------------------------------------------
# Scanner
# ---------------------------------------------------------------------------

class PromptInjectionScanner:
    """
    Pure-Python static scanner for prompt injection attack surface.

    Detects four categories:
    1. Direct user input concatenation into LLM prompts (PROMPT_INJECTION_SURFACE)
    2. Template injection via format() / Jinja2 (TEMPLATE_INJECTION)
    3. Unvalidated LLM output to dangerous sinks (UNVALIDATED_LLM_OUTPUT)
    4. User-controlled role field in messages (SYSTEM_PROMPT_OVERRIDE)
    """

    def scan(self, repo_path: str = ".") -> InjectionScanResult:
        try:
            repo = Path(repo_path).resolve()
            findings: List[InjectionFinding] = []
            findings.extend(self._scan_direct_concatenation(repo))
            findings.extend(self._scan_unvalidated_template(repo))
            findings.extend(self._scan_missing_output_validation(repo))
            findings.extend(self._scan_system_prompt_override(repo))
            findings.extend(self._scan_chat_api_injection(repo))
            findings.extend(self._scan_rag_injection(repo))
            return self._build_result(findings)
        except Exception as exc:
            return InjectionScanResult(findings=[], surface_score=0.0, scan_error=str(exc))

    # ------------------------------------------------------------------

    def _scan_direct_concatenation(self, repo: Path) -> List[InjectionFinding]:
        findings: List[InjectionFinding] = []
        for fpath in self._iter_source_files(repo):
            try:
                lines = fpath.read_text(encoding="utf-8", errors="replace").splitlines()
            except OSError:
                continue
            rel = str(fpath.relative_to(repo))
            for lineno, line in enumerate(lines, 1):
                for pat in _DIRECT_CONCAT_PATTERNS:
                    if pat.search(line):
                        findings.append(InjectionFinding(
                            file=rel, line=lineno,
                            rule_id="PROMPT_INJECTION_SURFACE",
                            severity="critical",
                            message=(
                                "User-controlled input directly concatenated into LLM prompt — "
                                "attacker can override system instructions"
                            ),
                            evidence=line.strip()[:200],
                            sink="llm_prompt",
                        ))
                        break
        return findings

    def _scan_unvalidated_template(self, repo: Path) -> List[InjectionFinding]:
        findings: List[InjectionFinding] = []
        for fpath in self._iter_source_files(repo):
            try:
                lines = fpath.read_text(encoding="utf-8", errors="replace").splitlines()
            except OSError:
                continue
            rel = str(fpath.relative_to(repo))
            for lineno, line in enumerate(lines, 1):
                for pat in _TEMPLATE_INJECT_PATTERNS:
                    if pat.search(line):
                        findings.append(InjectionFinding(
                            file=rel, line=lineno,
                            rule_id="TEMPLATE_INJECTION",
                            severity="high",
                            message=(
                                "Prompt template uses .format() or % substitution with potentially "
                                "user-controlled data — indirect prompt injection risk"
                            ),
                            evidence=line.strip()[:200],
                            sink="template_engine",
                        ))
                        break
        return findings

    def _scan_missing_output_validation(self, repo: Path) -> List[InjectionFinding]:
        findings: List[InjectionFinding] = []
        for fpath in self._iter_source_files(repo):
            try:
                lines = fpath.read_text(encoding="utf-8", errors="replace").splitlines()
            except OSError:
                continue
            rel = str(fpath.relative_to(repo))
            for lineno, line in enumerate(lines, 1):
                for pat in _UNSAFE_OUTPUT_PATTERNS:
                    if pat.search(line):
                        findings.append(InjectionFinding(
                            file=rel, line=lineno,
                            rule_id="UNVALIDATED_LLM_OUTPUT",
                            severity="medium",
                            message=(
                                "LLM output passed directly to a code-execution or HTML sink "
                                "without validation — secondary injection risk"
                            ),
                            evidence=line.strip()[:200],
                            sink=line.strip()[:50],
                        ))
                        break
        return findings

    def _scan_system_prompt_override(self, repo: Path) -> List[InjectionFinding]:
        findings: List[InjectionFinding] = []
        for fpath in self._iter_source_files(repo):
            try:
                lines = fpath.read_text(encoding="utf-8", errors="replace").splitlines()
            except OSError:
                continue
            rel = str(fpath.relative_to(repo))
            for lineno, line in enumerate(lines, 1):
                for pat in _ROLE_OVERRIDE_PATTERNS:
                    if pat.search(line):
                        findings.append(InjectionFinding(
                            file=rel, line=lineno,
                            rule_id="SYSTEM_PROMPT_OVERRIDE",
                            severity="high",
                            message=(
                                "User-controlled value used as role in LLM messages array — "
                                "attacker may inject system-role messages"
                            ),
                            evidence=line.strip()[:200],
                            sink="messages_role",
                        ))
                        break
        return findings

    def _scan_chat_api_injection(self, repo: Path) -> List[InjectionFinding]:
        findings: List[InjectionFinding] = []
        for fpath in self._iter_source_files(repo):
            try:
                lines = fpath.read_text(encoding="utf-8", errors="replace").splitlines()
            except OSError:
                continue
            rel = str(fpath.relative_to(repo))
            for lineno, line in enumerate(lines, 1):
                for pat in _CHAT_API_INJECTION_PATTERNS:
                    if pat.search(line):
                        findings.append(InjectionFinding(
                            file=rel, line=lineno,
                            rule_id="CHAT_API_INJECTION",
                            severity="high",
                            message=(
                                "User-controlled input flows directly into LLM chat messages — "
                                "attacker can inject system-level instructions"
                            ),
                            evidence=line.strip()[:200],
                            sink="chat_messages",
                        ))
                        break
        return findings

    def _scan_rag_injection(self, repo: Path) -> List[InjectionFinding]:
        findings: List[InjectionFinding] = []
        for fpath in self._iter_source_files(repo):
            try:
                lines = fpath.read_text(encoding="utf-8", errors="replace").splitlines()
            except OSError:
                continue
            rel = str(fpath.relative_to(repo))
            for lineno, line in enumerate(lines, 1):
                for pat in _RAG_INJECTION_PATTERNS:
                    if pat.search(line):
                        findings.append(InjectionFinding(
                            file=rel, line=lineno,
                            rule_id="RAG_CONTEXT_INJECTION",
                            severity="medium",
                            message=(
                                "Retrieved content or search results injected into LLM prompt "
                                "without sanitization — indirect prompt injection risk"
                            ),
                            evidence=line.strip()[:200],
                            sink="prompt_template",
                        ))
                        break
        return findings

    # ------------------------------------------------------------------

    def _iter_source_files(self, repo: Path):
        from agenticqa.security.safe_file_iter import iter_source_files
        yield from iter_source_files(repo, extensions=_SOURCE_EXTS, skip_dirs=_SKIP_DIRS)

    def _build_result(self, findings: List[InjectionFinding]) -> InjectionScanResult:
        if not findings:
            return InjectionScanResult(findings=[], surface_score=0.0)
        weights = [_SEVERITY_WEIGHTS.get(f.severity, 0.1) for f in findings]
        score = min(1.0, sum(weights) / len(weights))
        return InjectionScanResult(findings=findings, surface_score=round(score, 4))
