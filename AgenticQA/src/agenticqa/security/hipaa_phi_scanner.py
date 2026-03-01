"""
HIPAA PHI (Protected Health Information) static scanner.

Detects HIPAA compliance risks in codebases:
- Hardcoded PHI: SSN, DOB, MRN patterns in source files
- PHI in logs: patient identifiers passed to logging functions
- PHI to LLM: health data flowing into external AI APIs (§164.502 Business Associate)
- Missing HIPAA audit trail on patient data routes (§164.312(b))
- PHI documents in web-accessible directories

Subprocess-free: pure Python (re, pathlib). Mirrors LegalRiskScanner pattern exactly.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Tuple


_SEVERITY_WEIGHTS: Dict[str, float] = {
    "critical": 1.0,
    "high": 0.7,
    "medium": 0.4,
    "low": 0.1,
}

_SOURCE_EXTS = {".py", ".ts", ".tsx", ".js", ".jsx", ".mjs", ".cjs", ".yml", ".yaml"}
# PHI_IN_LOGS only meaningful in code files — not YAML CI pipelines
_LOG_SCAN_EXTS = {".py", ".ts", ".tsx", ".js", ".jsx", ".mjs", ".cjs"}
# "tests" excluded: test fixtures intentionally contain fake PHI values (SSN, DOB, MRN)
_SKIP_DIRS = {
    "node_modules", ".venv", "venv", "__pycache__",
    ".git", "dist", "build", ".next", "out", "tests",
}

# Scanner files + security tool files excluded from PHI_TO_LLM
# (their code/data contains model names and patterns that look like PHI contexts)
_SCANNER_OWN_FILES = {
    "hipaa_phi_scanner.py", "legal_risk_scanner.py",
    "ai_model_sbom.py", "agent_trust_graph.py",
    "prompt_injection_scanner.py", "cve_reachability.py",
}
_PUBLIC_DIRS = {"public", "static", "assets", "www", "media", "files"}

# PHI file extensions and name patterns
_PHI_DOC_EXTS = {".hl7", ".fhir", ".ccd", ".ccda", ".pdf", ".csv", ".xlsx", ".json"}
_PHI_FILENAME_PATTERN = re.compile(
    r"(patient|medical.?record|health.?record|clinical|ehr|phi|"
    r"diagnosis|prescription|medication|lab.?result|discharge|"
    r"radiology|pathology)",
    re.IGNORECASE,
)

# ---------------------------------------------------------------------------
# Hardcoded PHI patterns
# ---------------------------------------------------------------------------
_PHI_HARDCODED_PATTERNS: List[Tuple[re.Pattern, str, str]] = [
    (
        # SSN format: 3-2-4 digits, but exclude version strings, dates,
        # and other numeric patterns that happen to match.
        # Valid SSN area numbers: 001-899 (excluding 666).
        re.compile(
            r"(?<![.\d/])"  # Not preceded by digit, dot, or slash (version/date)
            r"\b(?:0[0-9]{2}|[1-5]\d{2}|6[0-57-9]\d|[7-8]\d{2})"  # area: 001-899 excl 666
            r"-(?:0[1-9]|[1-9]\d)"   # group: 01-99
            r"-(?:(?!0000)\d{4})"   # serial: 0001-9999 (exclude 0000)
            r"\b"
            r"(?![.\d/])"  # Not followed by digit, dot, or slash
        ),
        "critical",
        "Social Security Number (SSN) literal hardcoded in source",
    ),
    (
        re.compile(
            r"(ssn|social_security|social_security_number)\s*[:=]\s*[\"'][^\"']{7,}[\"']",
            re.IGNORECASE,
        ),
        "critical",
        "SSN/social security value hardcoded in variable assignment",
    ),
    (
        re.compile(
            r"(date_of_birth|dob|birthdate|birth_date)\s*[:=]\s*[\"'][^\"']{4,}[\"']",
            re.IGNORECASE,
        ),
        "critical",
        "Date of birth (DOB) hardcoded in source — HIPAA PHI (§164.514(b)(2)(i))",
    ),
    (
        re.compile(
            r"(mrn|medical_record_num|medical_record_number)\s*[:=]\s*[\"'][^\"']{3,}[\"']",
            re.IGNORECASE,
        ),
        "critical",
        "Medical Record Number (MRN) hardcoded in source",
    ),
    (
        re.compile(
            r"(npi|national_provider_identifier)\s*[:=]\s*[\"']\d{10}[\"']",
            re.IGNORECASE,
        ),
        "high",
        "National Provider Identifier (NPI) hardcoded in source",
    ),
]

# PHI variable name indicators (for log and LLM proximity scans)
_PHI_VAR_PATTERN = re.compile(
    r"\b(patient_?name|patient_?id|patient_?data|ssn|mrn|dob|"
    r"date_of_birth|diagnosis|medication|prescription|health_?record|"
    r"medical_?record|clinical_?data|phi|ehr|lab_?result|"
    r"insurance_?id|member_?id)\b",
    re.IGNORECASE,
)

# Logging sinks
_LOG_SINK_PATTERN = re.compile(
    r"(console\.log|console\.error|console\.info|console\.warn|"
    r"logger\.\w+|logging\.\w+|log\.\w+|print\s*\(|syslog)",
    re.IGNORECASE,
)

# LLM API call indicators (same as legal_risk_scanner)
_LLM_CALL_PATTERN = re.compile(
    r"(openai\.chat|anthropic\.messages|\.completions\.create|"
    r"gpt-[34]|claude-[a-z]|generateOpenAIResponse|generateResponse|"
    r"bedrock|vertex_?ai|palm\.generate)",
    re.IGNORECASE,
)

# HIPAA audit markers
_AUDIT_MARKERS = re.compile(
    r"(audit_log|auditLog|audit_trail|access_log|hipaa_log|"
    r"record_access|log_phi_access|track_access|compliance_log)",
    re.IGNORECASE,
)

# Patient/health route patterns
_HEALTH_ROUTE_PATTERN = re.compile(
    r"(patient|health|medical|clinical|ehr|phi|diagnosis|"
    r"prescription|medication|lab|radiology)",
    re.IGNORECASE,
)
_ROUTE_HANDLER = re.compile(
    r"export\s+async\s+function\s+(GET|POST|PUT|DELETE|PATCH)\s*\(",
)


# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------

@dataclass
class PHIFinding:
    file: str
    line: int
    rule_id: str
    severity: str
    message: str
    evidence: str = ""


@dataclass
class HIPAAResult:
    findings: List[PHIFinding]
    critical_findings: List[PHIFinding]
    risk_score: float
    scan_error: Optional[str] = None


# ---------------------------------------------------------------------------
# Scanner
# ---------------------------------------------------------------------------

class HIPAAPHIScanner:
    """
    Pure-Python HIPAA PHI scanner.

    Called from ComplianceAgent.execute() in a non-blocking try/except block.
    No subprocess calls. Runs in under 1 second on typical repos.
    """

    def scan(self, repo_path: str = ".") -> HIPAAResult:
        try:
            repo = Path(repo_path).resolve()
            findings: List[PHIFinding] = []
            findings.extend(self._scan_hardcoded_phi(repo))
            findings.extend(self._scan_phi_in_logs(repo))
            findings.extend(self._scan_phi_to_llm(repo))
            findings.extend(self._scan_missing_audit(repo))
            findings.extend(self._scan_phi_documents(repo))
            return self._build_result(findings)
        except Exception as exc:
            return HIPAAResult(findings=[], critical_findings=[], risk_score=0.0,
                               scan_error=str(exc))

    # ------------------------------------------------------------------

    def _scan_hardcoded_phi(self, repo: Path) -> List[PHIFinding]:
        findings: List[PHIFinding] = []
        for fpath in self._iter_source_files(repo):
            try:
                lines = fpath.read_text(encoding="utf-8", errors="replace").splitlines()
            except OSError:
                continue
            rel = str(fpath.relative_to(repo))
            for lineno, line in enumerate(lines, 1):
                # Respect inline suppression: # noqa or # noqa: PHI
                if re.search(r"#\s*noqa", line, re.IGNORECASE):
                    continue
                for pattern, severity, desc in _PHI_HARDCODED_PATTERNS:
                    if pattern.search(line):
                        findings.append(PHIFinding(
                            file=rel, line=lineno,
                            rule_id="PHI_HARDCODED",
                            severity=severity,
                            message=desc,
                            evidence=line.strip()[:200],
                        ))
                        break  # one finding per line
        return findings

    def _scan_phi_in_logs(self, repo: Path) -> List[PHIFinding]:
        """Detect PHI variable names passed directly to logging calls on the same line."""
        findings: List[PHIFinding] = []
        for fpath in self._iter_source_files(repo, exts=_LOG_SCAN_EXTS):
            try:
                lines = fpath.read_text(encoding="utf-8", errors="replace").splitlines()
            except OSError:
                continue
            rel = str(fpath.relative_to(repo))
            for lineno, line in enumerate(lines, 1):
                if re.search(r"#\s*noqa", line, re.IGNORECASE):
                    continue
                if _LOG_SINK_PATTERN.search(line) and _PHI_VAR_PATTERN.search(line):
                    findings.append(PHIFinding(
                        file=rel, line=lineno,
                        rule_id="PHI_IN_LOGS",
                        severity="high",
                        message=(
                            "PHI variable logged to output — health data must not appear in "
                            "application logs (HIPAA §164.312(b) audit controls)"
                        ),
                        evidence=line.strip()[:200],
                    ))
        return findings

    def _scan_phi_to_llm(self, repo: Path) -> List[PHIFinding]:
        """
        Detect PHI variable names within 30 lines of an LLM API call.
        Sending PHI to external LLM APIs requires a HIPAA Business Associate Agreement.
        """
        findings: List[PHIFinding] = []
        scan_exts = {".ts", ".tsx", ".js", ".jsx", ".py"}
        for fpath in self._iter_source_files(repo, exts=scan_exts):
            # Skip scanner implementation files — regex patterns contain LLM model name strings
            if fpath.name in _SCANNER_OWN_FILES:
                continue
            try:
                lines = fpath.read_text(encoding="utf-8", errors="replace").splitlines()
            except OSError:
                continue
            rel = str(fpath.relative_to(repo))
            phi_lines: List[int] = [
                lineno for lineno, line in enumerate(lines, 1)
                if _PHI_VAR_PATTERN.search(line)
                and not re.search(r"#\s*noqa", line, re.IGNORECASE)
            ]
            if not phi_lines:
                continue
            for lineno, line in enumerate(lines, 1):
                if _LLM_CALL_PATTERN.search(line):
                    stripped = line.strip()
                    # Skip regex pattern definition lines
                    if stripped.startswith(("r\"", "r'")) or "re.compile(" in stripped:
                        continue
                    # Skip comment lines
                    if stripped.startswith(("#", "//")):
                        continue
                    for phi_line in phi_lines:
                        if 0 <= lineno - phi_line <= 30:
                            findings.append(PHIFinding(
                                file=rel, line=lineno,
                                rule_id="PHI_TO_LLM",
                                severity="critical",
                                message=(
                                    "PHI data forwarded to external LLM API within 30 lines — "
                                    "requires HIPAA BAA with the AI provider (§164.502(e))"
                                ),
                                evidence=stripped[:200],
                            ))
                            break
        return findings

    def _scan_missing_audit(self, repo: Path) -> List[PHIFinding]:
        """
        Detect health-data API route handlers with no HIPAA audit logging.
        HIPAA §164.312(b) requires audit controls on ePHI access.
        """
        findings: List[PHIFinding] = []
        route_patterns = ["app/api/**/route.ts", "pages/api/**/*.ts",
                          "app/api/**/route.tsx", "routes/**/*.py"]
        candidates: List[Path] = []
        for pat in route_patterns:
            candidates.extend(repo.glob(pat))
        for fpath in candidates:
            if not _HEALTH_ROUTE_PATTERN.search(str(fpath)):
                continue
            try:
                content = fpath.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue
            rel = str(fpath.relative_to(repo))
            for match in _ROUTE_HANDLER.finditer(content):
                method = match.group(1)
                start = match.start()
                snippet = content[start: start + 2000]
                if not _AUDIT_MARKERS.search(snippet):
                    line_num = content[:start].count("\n") + 1
                    findings.append(PHIFinding(
                        file=rel, line=line_num,
                        rule_id="HIPAA_AUDIT_MISSING",
                        severity="high",
                        message=(
                            f"Health data route `{method}` has no HIPAA audit logging — "
                            "§164.312(b) requires recording who accessed ePHI, when, and what action"
                        ),
                        evidence=f"{rel}:{line_num} export async function {method}",
                    ))
        return findings

    def _scan_phi_documents(self, repo: Path) -> List[PHIFinding]:
        """Detect PHI files (HL7, FHIR, patient CSV) in web-accessible directories."""
        findings: List[PHIFinding] = []
        for pub_name in _PUBLIC_DIRS:
            pub_dir = repo / pub_name
            if not pub_dir.is_dir():
                continue
            for fpath in pub_dir.rglob("*"):
                if not fpath.is_file():
                    continue
                if fpath.suffix.lower() not in _PHI_DOC_EXTS:
                    continue
                rel = str(fpath.relative_to(repo))
                name_lower = fpath.name.lower()
                is_phi = (
                    fpath.suffix.lower() in {".hl7", ".fhir", ".ccd", ".ccda"}
                    or _PHI_FILENAME_PATTERN.search(name_lower)
                )
                if is_phi:
                    findings.append(PHIFinding(
                        file=rel, line=1,
                        rule_id="PHI_DOCUMENT_PUBLIC",
                        severity="critical",
                        message=(
                            f"PHI document committed to web-accessible '{pub_name}/' directory — "
                            "ePHI must be protected under HIPAA Security Rule §164.312"
                        ),
                        evidence=f"{rel} ({fpath.stat().st_size:,} bytes)",
                    ))
        return findings

    # ------------------------------------------------------------------

    def _iter_source_files(self, repo: Path, exts=None):
        from agenticqa.security.safe_file_iter import iter_source_files
        yield from iter_source_files(repo, extensions=(exts or _SOURCE_EXTS), skip_dirs=_SKIP_DIRS)

    def _build_result(self, findings: List[PHIFinding]) -> HIPAAResult:
        critical = [f for f in findings if f.severity in ("critical", "high")]
        if not findings:
            score = 0.0
        else:
            weights = [_SEVERITY_WEIGHTS.get(f.severity, 0.1) for f in findings]
            score = min(1.0, sum(weights) / len(weights))
        return HIPAAResult(
            findings=findings,
            critical_findings=critical,
            risk_score=round(score, 4),
        )
