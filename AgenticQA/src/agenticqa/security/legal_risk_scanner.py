"""
Legal risk scanner for the ComplianceAgent.

Detects legal and security risks in codebases:
- Hardcoded credentials and secrets
- PII / legal documents committed to web-accessible directories
- Attorney-client privilege exposure (document content sent to LLM APIs)
- SSRF risks from hardcoded localhost proxy URLs
- Missing authentication on API route handlers

Subprocess-free: pure Python (re, pathlib, ast). Non-blocking when called from
ComplianceAgent.execute() — all exceptions caught at call site.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Tuple


# ---------------------------------------------------------------------------
# Severity weights (mirrors CVEReachabilityAnalyzer._SEVERITY_WEIGHTS)
# ---------------------------------------------------------------------------
_SEVERITY_WEIGHTS: Dict[str, float] = {
    "critical": 1.0,
    "high": 0.7,
    "medium": 0.4,
    "low": 0.1,
}

# ---------------------------------------------------------------------------
# Source-file extensions to scan for credentials / privilege / SSRF
# ---------------------------------------------------------------------------
_SOURCE_EXTS = {".py", ".ts", ".tsx", ".js", ".jsx", ".mjs", ".cjs", ".yml", ".yaml"}
_ENV_NAMES = {".env", ".env.local", ".env.production", ".env.development"}

# SSRF is only meaningful in files that can make network calls — not YAML/config
_SSRF_CODE_EXTS = {".py", ".ts", ".tsx", ".js", ".jsx", ".mjs", ".cjs"}

# Directories that skip during source scan
# "tests" excluded: test fixtures intentionally contain fake credentials/PHI
_SKIP_DIRS = {
    "node_modules", ".venv", "venv", "__pycache__",
    ".git", "dist", "build", ".next", "out", "tests",
}

# Scanner implementation files — excluded from PRIVILEGE_BREACH self-scan
_SCANNER_OWN_FILES = {"legal_risk_scanner.py", "hipaa_phi_scanner.py"}

# Placeholder / example values that are not real credentials
_PLACEHOLDER_RE = re.compile(
    r"(your[-_]?(?:key|secret|token)[-_]?here|changeme|placeholder|"
    r"\bexample|to[-_]?do|xxx+|<[^>]+>|change[-_]?in[-_]?prod)",
    re.IGNORECASE,
)

# All-caps env var names used as string constants (e.g. ENV_FOO = "SOME_ENV_VAR")
# Requires at least one underscore — real credentials (e.g. AWS keys) have no underscores
_ENV_VAR_NAME_RE = re.compile(r"^[A-Z][A-Z0-9]*_[A-Z0-9_]+$")

# Web-accessible directories where committed documents are a PII risk
_PUBLIC_DIRS = {"public", "static", "assets", "www", "media", "files"}

# Document file extensions that are PII-risk in public directories
_DOC_EXTS = {".pdf", ".doc", ".docx", ".odt", ".rtf"}

# Legal/sensitive name patterns (case-insensitive)
_LEGAL_PATTERNS = re.compile(
    r"(employment|agreement|contract|nda|non.?disclosure|confidential|"
    r"salary|payroll|severance|settlement|lawsuit|litigation)",
    re.IGNORECASE,
)

# ---------------------------------------------------------------------------
# Credential detection patterns: (regex, rule_id, severity, description)
# ---------------------------------------------------------------------------
_CREDENTIAL_PATTERNS: List[Tuple[re.Pattern, str, str, str]] = [
    (
        re.compile(r"mongodb\+srv://[^\"'\s:]+:[^\"'\s@]+@", re.IGNORECASE),
        "CREDENTIAL_EXPOSURE", "critical",
        "Hardcoded MongoDB Atlas URI with embedded credentials",
    ),
    (
        re.compile(r"(mysql|postgresql|postgres|redis|amqp|rabbitmq)://[^\"'\s:]+:[^\"'\s@]+@", re.IGNORECASE),
        "CREDENTIAL_EXPOSURE", "critical",
        "Hardcoded database connection string with embedded credentials",
    ),
    (
        re.compile(r"AKIA[A-Z2-7]{16}"),
        "CREDENTIAL_EXPOSURE", "critical",
        "AWS IAM access key committed to source",
    ),
    (
        re.compile(r"sk-[A-Za-z0-9]{20,}"),
        "CREDENTIAL_EXPOSURE", "critical",
        "Hardcoded OpenAI API key (sk- prefix)",
    ),
    (
        re.compile(r"-----BEGIN (RSA |EC |OPENSSH )?PRIVATE KEY-----"),
        "CREDENTIAL_EXPOSURE", "critical",
        "Private key material committed to source",
    ),
    (
        re.compile(r'(password|passwd|secret|api_?key)\s*[:=]\s*["\'][^"\']{8,}["\']', re.IGNORECASE),
        "CREDENTIAL_EXPOSURE", "high",
        "Hardcoded password/secret string assigned to variable",
    ),
]

# SSRF: localhost URL used as a proxy target in fetch/requests/axios calls
_SSRF_PATTERN = re.compile(r'https?://localhost:[0-9]+', re.IGNORECASE)

# SSRF false-positive exclusions: contexts where localhost is a configured default, not a proxy target
_SSRF_SKIP_PATTERN = re.compile(
    r"(os\.getenv\s*\(|add_argument\s*\(|\.text_input\s*\(|"
    r"value\s*=\s*[\"']http://localhost|default\s*=\s*[\"']http://localhost|"
    r"\[.*\]\(http://localhost|[\"']Endpoint[\"']\s*:|"
    # Function/constructor default parameters: def fn(url="http://localhost:...") or constructor(url = '...')
    r"def\s+\w+\s*\(|constructor\s*\(|"
    # Doctest lines: >>> client = Foo("http://localhost:...")
    r">>>\s+\w)",
    re.IGNORECASE,
)
# Spec/config/example files are never real SSRF attack surface
_SSRF_SKIP_SUFFIXES = {".spec.js", ".spec.ts", ".spec.tsx"}
_SSRF_SKIP_FILENAMES = {"playwright.config.js", "playwright.config.ts", "playwright.config.mjs"}
# scripts/ are CLI tools, not web-facing code — localhost URLs are expected default endpoints
_SSRF_SKIP_DIRS = {"tests", "examples", "scripts"}

# Privilege exposure: file-read operations
_FILE_READ_PATTERN = re.compile(
    r"(fs\.readFile|fs\.promises\.readFile|open\s*\(|"
    r"Path\s*\(.*\)\.read_text|readFileSync)",
    re.IGNORECASE,
)
# LLM API call indicators
_LLM_CALL_PATTERN = re.compile(
    r"(openai\.chat|anthropic\.messages|\.completions\.create|"
    r"gpt-[34]|claude-[a-z]|generateOpenAIResponse|generateResponse)",
    re.IGNORECASE,
)

# Auth markers for route-handler scan
_AUTH_MARKERS = re.compile(
    r"(auth\s*\(|getSession\s*\(|verifyToken|requireAuth|authenticate|"
    r"Authorization|bearer|jwt\.verify|checkAuth|isAuthenticated)",
    re.IGNORECASE,
)
# Next.js / Express route handler declarations
_ROUTE_HANDLER = re.compile(
    r"export\s+async\s+function\s+(GET|POST|PUT|DELETE|PATCH)\s*\(",
)


# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------

@dataclass
class LegalRiskFinding:
    file: str
    line: int
    rule_id: str
    severity: str          # critical | high | medium | low
    message: str
    evidence: str = ""     # snippet or path info


@dataclass
class LegalRiskResult:
    findings: List[LegalRiskFinding]
    critical_findings: List[LegalRiskFinding]   # severity in (critical, high)
    risk_score: float                            # 0.0–1.0
    scan_error: Optional[str] = None


# ---------------------------------------------------------------------------
# Scanner
# ---------------------------------------------------------------------------

class LegalRiskScanner:
    """
    Pure-Python scanner for legal and security compliance risks.

    Designed to be called from ComplianceAgent.execute() in a non-blocking
    try/except block.  No subprocess calls — runs in under 1 second on typical
    repos (< 500 source files).
    """

    def scan(self, repo_path: str = ".") -> LegalRiskResult:
        """Run all sub-scans and return aggregated result."""
        try:
            repo = Path(repo_path).resolve()
            findings: List[LegalRiskFinding] = []
            findings.extend(self._scan_credentials(repo))
            findings.extend(self._scan_pii_documents(repo))
            findings.extend(self._scan_privilege_exposure(repo))
            findings.extend(self._scan_missing_auth(repo))
            return self._build_result(findings)
        except Exception as exc:
            return LegalRiskResult(
                findings=[],
                critical_findings=[],
                risk_score=0.0,
                scan_error=str(exc),
            )

    # ------------------------------------------------------------------
    # Sub-scanners
    # ------------------------------------------------------------------

    def _scan_credentials(self, repo: Path) -> List[LegalRiskFinding]:
        findings: List[LegalRiskFinding] = []
        for fpath in self._iter_source_files(repo):
            rel = str(fpath.relative_to(repo))
            # .env.example / .env.sample → skip (placeholder files)
            if any(x in fpath.name.lower() for x in ("example", "sample", "template")):
                continue
            try:
                lines = fpath.read_text(encoding="utf-8", errors="replace").splitlines()
            except OSError:
                continue
            for lineno, line in enumerate(lines, 1):
                stripped = line.strip()
                # Skip inline suppression comments
                if re.search(r"#\s*noqa", line, re.IGNORECASE):
                    continue
                # Skip pure comments and documentation lines
                if stripped.startswith(("#", "//", "/*", "*", "\"\"\"", "'''", "(e.g.")):
                    pass  # still check for SSRF below, but skip credential patterns
                else:
                    for pattern, rule_id, severity, desc in _CREDENTIAL_PATTERNS:
                        if pattern.search(line):
                            # Skip placeholder / example values
                            if _PLACEHOLDER_RE.search(line):
                                break
                            # Skip all-caps env-var name constants (e.g. ENV_FOO = "SOME_VAR_NAME")
                            quoted = re.search(r'["\']([^"\']{4,})["\']', line)
                            if quoted and _ENV_VAR_NAME_RE.match(quoted.group(1)):
                                break
                            findings.append(LegalRiskFinding(
                                file=rel,
                                line=lineno,
                                rule_id=rule_id,
                                severity=severity,
                                message=desc,
                                evidence=stripped[:200],
                            ))
                            break  # one finding per line

                # SSRF check — only in code files; skip defaults, docs, tests, examples
                if (
                    fpath.suffix.lower() in _SSRF_CODE_EXTS
                    and fpath.suffix.lower() not in _SSRF_SKIP_SUFFIXES
                    and fpath.name not in _SSRF_SKIP_FILENAMES
                    and not any(p in _SSRF_SKIP_DIRS for p in fpath.parts)
                    and _SSRF_PATTERN.search(line)
                    and not stripped.startswith(("#", "//", '"""', "'''", ">>>"))
                    and not re.search(r"\bprint\s*\(|console\.(log|info|warn|error)", line)
                    and not _SSRF_SKIP_PATTERN.search(line)
                ):
                    findings.append(LegalRiskFinding(
                        file=rel,
                        line=lineno,
                        rule_id="SSRF_RISK",
                        severity="medium",
                        message="Hardcoded localhost URL used as proxy target — potential SSRF if path is user-controlled",
                        evidence=stripped[:200],
                    ))
        return findings

    def _scan_pii_documents(self, repo: Path) -> List[LegalRiskFinding]:
        findings: List[LegalRiskFinding] = []
        for pub_name in _PUBLIC_DIRS:
            pub_dir = repo / pub_name
            if not pub_dir.is_dir():
                continue
            for fpath in pub_dir.rglob("*"):
                if not fpath.is_file():
                    continue
                if fpath.suffix.lower() not in _DOC_EXTS:
                    continue
                rel = str(fpath.relative_to(repo))
                size = fpath.stat().st_size
                name_lower = fpath.name.lower()
                if _LEGAL_PATTERNS.search(name_lower):
                    severity = "critical"
                    msg = (
                        f"Legal/employment document committed to web-accessible '{pub_name}/' directory "
                        f"— confidential content publicly accessible"
                    )
                else:
                    severity = "high"
                    msg = (
                        f"Binary document ({fpath.suffix}) committed to web-accessible '{pub_name}/' directory "
                        f"— may contain sensitive content"
                    )
                findings.append(LegalRiskFinding(
                    file=rel,
                    line=1,
                    rule_id="PII_DOCUMENT_PUBLIC",
                    severity=severity,
                    message=msg,
                    evidence=f"{rel} ({size:,} bytes)",
                ))
        return findings

    def _scan_privilege_exposure(self, repo: Path) -> List[LegalRiskFinding]:
        """
        Detect co-occurrence of file-read + LLM API call within 30 lines,
        which indicates document content is being forwarded to an external LLM
        (destroying attorney-client privilege for legal documents).
        """
        findings: List[LegalRiskFinding] = []
        scan_exts = {".ts", ".tsx", ".js", ".jsx", ".py"}
        for fpath in self._iter_source_files(repo, exts=scan_exts):
            # Skip scanner implementation files — their regex patterns contain LLM model names
            if fpath.name in _SCANNER_OWN_FILES:
                continue
            # Skip test directories — test fixtures intentionally contain file-read + LLM patterns
            if any(p in {"tests", "test", "__tests__"} for p in fpath.parts):
                continue
            try:
                lines = fpath.read_text(encoding="utf-8", errors="replace").splitlines()
            except OSError:
                continue
            rel = str(fpath.relative_to(repo))
            read_lines: List[int] = []
            for lineno, line in enumerate(lines, 1):
                if _FILE_READ_PATTERN.search(line):
                    read_lines.append(lineno)
            if not read_lines:
                continue
            for lineno, line in enumerate(lines, 1):
                if _LLM_CALL_PATTERN.search(line):
                    stripped = line.strip()
                    # Skip regex pattern definitions (lines with raw string or re.compile)
                    if stripped.startswith(("r\"", "r'")) or "re.compile(" in stripped:
                        continue
                    # Skip comment lines
                    if stripped.startswith(("#", "//")):
                        continue
                    # Respect inline suppression
                    if re.search(r"#\s*noqa", line, re.IGNORECASE):
                        continue
                    # Check if any file-read occurred within 30 lines above
                    for rline in read_lines:
                        if 0 <= lineno - rline <= 30:
                            findings.append(LegalRiskFinding(
                                file=rel,
                                line=lineno,
                                rule_id="PRIVILEGE_BREACH",
                                severity="high",
                                message=(
                                    "File content read and forwarded to external LLM API within 30 lines — "
                                    "attorney-client privilege may be waived for legal documents (ABA Rule 1.6)"
                                ),
                                evidence=stripped[:200],
                            ))
                            break
        return findings

    def _scan_missing_auth(self, repo: Path) -> List[LegalRiskFinding]:
        """
        Detect Next.js / Express API route handlers with no authentication
        middleware or auth check in the handler body.
        """
        findings: List[LegalRiskFinding] = []
        # Next.js: app/api/**/route.ts  or  pages/api/**/*.ts
        route_patterns = ["app/api/**/route.ts", "pages/api/**/*.ts", "app/api/**/route.tsx"]
        candidate_files: List[Path] = []
        for pat in route_patterns:
            candidate_files.extend(repo.glob(pat))
        for fpath in candidate_files:
            try:
                content = fpath.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue
            rel = str(fpath.relative_to(repo))
            # Find each exported HTTP handler
            for match in _ROUTE_HANDLER.finditer(content):
                method = match.group(1)
                start = match.start()
                # Extract up to 60 lines after the handler declaration
                snippet = content[start: start + 2000]
                if not _AUTH_MARKERS.search(snippet):
                    line_num = content[:start].count("\n") + 1
                    findings.append(LegalRiskFinding(
                        file=rel,
                        line=line_num,
                        rule_id="NO_AUTH_ROUTE",
                        severity="medium",
                        message=(
                            f"API route handler `{method}` has no authentication check — "
                            f"unauthenticated access to potentially sensitive legal data"
                        ),
                        evidence=f"{rel}:{line_num} export async function {method}",
                    ))
        return findings

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _iter_source_files(
        self, repo: Path, exts: Optional[set] = None
    ):
        """Yield source files, skipping common non-code directories."""
        from agenticqa.security.safe_file_iter import iter_source_files
        # Also yield .env-style files by name
        target_exts = exts if exts is not None else _SOURCE_EXTS
        all_exts = target_exts | {".env"}  # include .env files
        for fpath in iter_source_files(repo, extensions=all_exts, skip_dirs=_SKIP_DIRS):
            yield fpath
        # Catch .env files with no extension (e.g., .env, .env.local)
        from agenticqa.security.safe_file_iter import MAX_FILES, SKIP_DIRS as _SAFE_SKIP
        count = 0
        for fpath in repo.rglob("*"):
            if count >= MAX_FILES:
                break
            if not fpath.is_file():
                continue
            if any(part in _SAFE_SKIP for part in fpath.parts):
                continue
            if fpath.name in _ENV_NAMES and fpath.suffix.lower() not in all_exts:
                yield fpath
            count += 1

    def _build_result(self, findings: List[LegalRiskFinding]) -> LegalRiskResult:
        critical_findings = [
            f for f in findings if f.severity in ("critical", "high")
        ]
        if not findings:
            score = 0.0
        else:
            weights = [_SEVERITY_WEIGHTS.get(f.severity, 0.1) for f in findings]
            score = min(1.0, sum(weights) / len(weights))
        return LegalRiskResult(
            findings=findings,
            critical_findings=critical_findings,
            risk_score=round(score, 4),
        )
