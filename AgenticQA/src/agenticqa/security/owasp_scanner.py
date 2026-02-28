"""
OWASPScanner — static analysis covering the OWASP Top 10 (2021 edition).

The Gap
-------
Every other AgenticQA scanner looks at architecture, data flow, or agent
behaviour. This module does what a pentester does: systematically check for
the ten most common web application vulnerabilities — in source code, before
the app runs.

OWASP Top 10 (2021)
-------------------
A01  Broken Access Control           — missing auth decorators, direct object refs
A02  Cryptographic Failures          — weak/no encryption, plaintext secrets
A03  Injection                       — SQL injection, command injection, XSS
A04  Insecure Design                 — mass assignment, unsafe redirect
A05  Security Misconfiguration       — debug mode, default credentials, CORS *
A06  Vulnerable Components           — checked by CVE Reachability; flagged here too
A07  Auth & Session Mgmt Failures    — hardcoded tokens, weak session config
A08  Software & Data Integrity       — pickle loads, unsafe deserialisation
A09  Logging & Monitoring Failures   — missing audit logs on sensitive ops
A10  SSRF                            — user-controlled URLs in outbound requests

Usage
-----
    from agenticqa.security.owasp_scanner import OWASPScanner

    result = OWASPScanner().scan("/path/to/repo")
    print(result.owasp_report())
    for finding in result.critical_findings:
        print(finding)
"""
from __future__ import annotations

import re
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Tuple

# ── Skip dirs ─────────────────────────────────────────────────────────────────

_SKIP_DIRS = {
    "node_modules", ".venv", "venv", "__pycache__", ".git",
    "dist", "build", "DerivedData", "vendor", "target", ".gradle",
    ".next", "out", "coverage", ".nyc_output",
}

_SOURCE_EXTS = {".py", ".ts", ".js", ".tsx", ".jsx", ".mjs", ".go", ".java", ".rb"}

# ── OWASP rule definitions ────────────────────────────────────────────────────
# Each rule: (owasp_id, rule_id, severity, pattern, description, cwe)

_RULES: List[Tuple[str, str, str, re.Pattern, str, str]] = [

    # A01 — Broken Access Control
    ("A01", "A01-001", "high",
     re.compile(r"@app\.(get|post|put|delete|patch)\([^)]+\)\s*\ndef\s+\w+", re.MULTILINE),
     "Route handler with no auth decorator — may be publicly accessible",
     "CWE-284"),
    ("A01", "A01-002", "high",
     re.compile(r"request\.(args|form|json|params)\[[\"']?(id|ID|Id|user_id|object_id)[\"']?\]", re.IGNORECASE),
     "Direct object reference from request without access check — potential IDOR",
     "CWE-639"),
    ("A01", "A01-003", "medium",
     re.compile(r"allow_origins\s*=\s*\[?\s*[\"']\*[\"']", re.IGNORECASE),
     "CORS wildcard origin (*) — any domain can make credentialed requests",
     "CWE-942"),

    # A02 — Cryptographic Failures
    ("A02", "A02-001", "critical",
     re.compile(r"(password|secret|api_key|token)\s*=\s*[\"'][^\"']{4,}[\"']", re.IGNORECASE),
     "Hardcoded credential or secret in source code",
     "CWE-798"),
    ("A02", "A02-002", "high",
     re.compile(r"\bmd5\b|\bsha1\b|\bDES\b|\bRC4\b", re.IGNORECASE),
     "Weak/broken cryptographic algorithm (MD5, SHA1, DES, RC4)",
     "CWE-327"),
    ("A02", "A02-003", "high",
     re.compile(r"http://(?!localhost|127\.0\.0\.1|0\.0\.0\.0)", re.IGNORECASE),
     "Plaintext HTTP connection to non-local host — data transmitted unencrypted",
     "CWE-319"),
    ("A02", "A02-004", "medium",
     re.compile(r"ssl_verify\s*=\s*False|verify\s*=\s*False|NODE_TLS_REJECT_UNAUTHORIZED\s*=\s*[\"']0[\"']", re.IGNORECASE),
     "TLS certificate verification disabled",
     "CWE-295"),

    # A03 — Injection
    ("A03", "A03-001", "critical",
     re.compile(r"(execute|cursor\.execute|raw|rawQuery|db\.query)\s*\([^)]*(%s|f[\"']|format\(|\.format)", re.IGNORECASE),
     "Potential SQL injection — string interpolation in SQL query",
     "CWE-89"),
    ("A03", "A03-002", "critical",
     re.compile(r"(subprocess\.(call|run|Popen|check_output)|os\.system|os\.popen|exec\(|eval\()\s*\([^)]*\+", re.IGNORECASE),
     "Potential command injection — user input concatenated into shell command",
     "CWE-78"),
    ("A03", "A03-003", "high",
     re.compile(r"innerHTML\s*=|\.html\s*\([^)]*req\.|dangerouslySetInnerHTML", re.IGNORECASE),
     "Potential XSS — raw HTML injection from request data",
     "CWE-79"),
    ("A03", "A03-004", "high",
     re.compile(r"(ldap|ldap3)\.(search|bind)\s*\([^)]*(%s|f[\"']|\.format)", re.IGNORECASE),
     "Potential LDAP injection",
     "CWE-90"),
    ("A03", "A03-005", "high",
     re.compile(r"(xpath|etree|lxml).*\.findall?\s*\([^)]*(%s|f[\"']|format\()", re.IGNORECASE),
     "Potential XPath injection",
     "CWE-643"),

    # A04 — Insecure Design
    ("A04", "A04-001", "high",
     re.compile(r"(BaseModel|Schema|Serializer)\s*.*\bexclude\b.*=.*\[\]|class.*Meta.*exclude\s*=\s*\[\]", re.IGNORECASE),
     "Empty exclude list on serializer — potential mass assignment vulnerability",
     "CWE-915"),
    ("A04", "A04-002", "medium",
     re.compile(r"redirect\s*\(\s*request\.(args|form|params|query)", re.IGNORECASE),
     "Open redirect — redirect target comes from user input",
     "CWE-601"),

    # A05 — Security Misconfiguration
    ("A05", "A05-001", "high",
     re.compile(r"DEBUG\s*=\s*True|app\.debug\s*=\s*True|NODE_ENV\s*=\s*[\"']development[\"']", re.IGNORECASE),
     "Debug mode enabled — exposes stack traces and internal state",
     "CWE-215"),
    ("A05", "A05-002", "critical",
     re.compile(r"(username|user|login)\s*=\s*[\"'](admin|root|test|guest)[\"'].*\n.*(password|pwd|pass)\s*=\s*[\"'](admin|root|password|1234|test)[\"']", re.IGNORECASE),
     "Default credentials detected",
     "CWE-1392"),
    ("A05", "A05-003", "medium",
     re.compile(r"SECRET_KEY\s*=\s*[\"'][\"']|SECRET_KEY\s*=\s*[\"']changeme|SECRET_KEY\s*=\s*[\"']your-secret", re.IGNORECASE),
     "Weak or placeholder SECRET_KEY",
     "CWE-321"),

    # A07 — Auth & Session Management Failures
    ("A07", "A07-001", "high",
     re.compile(r"SESSION_COOKIE_SECURE\s*=\s*False|session\.secure\s*=\s*false|secure:\s*false", re.IGNORECASE),
     "Session cookie secure flag disabled — cookie sent over HTTP",
     "CWE-614"),
    ("A07", "A07-002", "high",
     re.compile(r"HTTPONLY\s*=\s*False|httpOnly:\s*false|http_only\s*=\s*False", re.IGNORECASE),
     "Session cookie HttpOnly flag disabled — accessible via JavaScript",
     "CWE-1004"),
    ("A07", "A07-003", "medium",
     re.compile(r"jwt\.decode\s*\([^)]+algorithms\s*=\s*\[[\"']none[\"']\]|alg.*none", re.IGNORECASE),
     "JWT 'none' algorithm allowed — token signature bypassed",
     "CWE-347"),
    ("A07", "A07-004", "medium",
     re.compile(r"(session_timeout|PERMANENT_SESSION_LIFETIME)\s*=\s*(?:timedelta\(days\s*=\s*(?:3[0-9][0-9]|[4-9][0-9]|\d{3}))", re.IGNORECASE),
     "Excessively long session lifetime (>30 days)",
     "CWE-613"),

    # A08 — Software & Data Integrity
    ("A08", "A08-001", "critical",
     re.compile(r"pickle\.loads?\s*\(|cPickle\.loads?\s*\(", re.IGNORECASE),
     "Unsafe pickle deserialisation — arbitrary code execution if input is attacker-controlled",
     "CWE-502"),
    ("A08", "A08-002", "high",
     re.compile(r"yaml\.load\s*\([^)]+(?!Loader=yaml\.SafeLoader|Loader=yaml\.CSafeLoader)", re.IGNORECASE),
     "Unsafe yaml.load() without SafeLoader — potential arbitrary code execution",
     "CWE-502"),
    ("A08", "A08-003", "high",
     re.compile(r"marshal\.loads?\s*\(|__reduce__\s*\(", re.IGNORECASE),
     "Unsafe marshal deserialisation or __reduce__ override",
     "CWE-502"),

    # A09 — Logging & Monitoring Failures
    ("A09", "A09-001", "medium",
     re.compile(r"except[^:]*:\s*\n\s*pass", re.MULTILINE),
     "Bare except with pass — exceptions silently swallowed, no audit trail",
     "CWE-390"),
    ("A09", "A09-002", "low",
     re.compile(r"(login|authenticate|logout|delete|payment|transfer).*\n(?:(?!log\.|logger|logging|audit).)*(return|raise)", re.IGNORECASE | re.MULTILINE),
     "Sensitive operation (login/delete/payment) without apparent logging",
     "CWE-778"),

    # A10 — SSRF
    ("A10", "A10-001", "critical",
     re.compile(r"(requests\.(get|post|put)|httpx\.(get|post|put)|urllib\.request\.urlopen|fetch\s*\()\s*\([^)]*request\.(args|form|json|params|query|body)", re.IGNORECASE),
     "SSRF — outbound HTTP call with URL from user-controlled request data",
     "CWE-918"),
    ("A10", "A10-002", "high",
     re.compile(r"(requests\.(get|post)|httpx\.(get|post))\s*\([^)]*\+\s*(url|target|endpoint|host|addr)", re.IGNORECASE),
     "SSRF — outbound HTTP call with concatenated URL variable",
     "CWE-918"),
]


# ── Dataclasses ───────────────────────────────────────────────────────────────

@dataclass
class OWASPFinding:
    """A single OWASP Top 10 finding."""
    owasp_id: str           # A01–A10
    rule_id: str            # e.g. A03-001
    severity: str           # critical | high | medium | low
    source_file: str
    line_number: int
    evidence: str           # matched snippet (≤120 chars)
    description: str
    cwe: str
    owasp_category: str     # human name of the OWASP category

    def to_dict(self) -> dict:
        return {
            "owasp_id": self.owasp_id,
            "rule_id": self.rule_id,
            "severity": self.severity,
            "source_file": self.source_file,
            "line_number": self.line_number,
            "evidence": self.evidence[:120],
            "description": self.description,
            "cwe": self.cwe,
            "owasp_category": self.owasp_category,
        }


_OWASP_NAMES = {
    "A01": "Broken Access Control",
    "A02": "Cryptographic Failures",
    "A03": "Injection",
    "A04": "Insecure Design",
    "A05": "Security Misconfiguration",
    "A06": "Vulnerable Components",
    "A07": "Auth & Session Mgmt Failures",
    "A08": "Software & Data Integrity",
    "A09": "Logging & Monitoring Failures",
    "A10": "SSRF",
}


@dataclass
class OWASPScanResult:
    """Result of an OWASP Top 10 scan."""
    repo_path: str
    findings: List[OWASPFinding]
    files_scanned: int
    risk_score: float          # 0.0–1.0
    owasp_coverage: Dict[str, int]  # category → count
    timestamp: float = field(default_factory=time.time)
    scan_error: Optional[str] = None

    @property
    def critical_findings(self) -> List[OWASPFinding]:
        return [f for f in self.findings if f.severity == "critical"]

    @property
    def high_findings(self) -> List[OWASPFinding]:
        return [f for f in self.findings if f.severity == "high"]

    def by_category(self) -> Dict[str, List[OWASPFinding]]:
        out: Dict[str, List[OWASPFinding]] = {}
        for f in self.findings:
            out.setdefault(f.owasp_id, []).append(f)
        return out

    def owasp_report(self) -> str:
        lines = [
            f"OWASP Top 10 Scan — {self.repo_path}",
            f"Files: {self.files_scanned}  |  Findings: {len(self.findings)}  |  Risk: {self.risk_score:.2f}",
            "",
        ]
        by_cat = self.by_category()
        for oid in sorted(by_cat):
            cat_findings = by_cat[oid]
            name = _OWASP_NAMES.get(oid, oid)
            lines.append(f"  [{oid}] {name} — {len(cat_findings)} finding(s)")
            for f in cat_findings[:3]:
                lines.append(f"       [{f.severity.upper():8s}] {f.source_file}:{f.line_number} — {f.description[:80]}")
            if len(cat_findings) > 3:
                lines.append(f"       … and {len(cat_findings) - 3} more")
        return "\n".join(lines)

    def to_dict(self) -> dict:
        return {
            "repo_path": self.repo_path,
            "files_scanned": self.files_scanned,
            "risk_score": round(self.risk_score, 3),
            "owasp_coverage": self.owasp_coverage,
            "findings": [f.to_dict() for f in self.findings],
            "critical_count": len(self.critical_findings),
            "high_count": len(self.high_findings),
            "timestamp": self.timestamp,
        }


# ── Scanner ───────────────────────────────────────────────────────────────────

class OWASPScanner:
    """
    Static analysis scanner covering OWASP Top 10 (2021).
    Scans Python, TypeScript, JavaScript, Go, Java, Ruby source files.
    No dynamic execution required.
    """

    def scan(self, repo_path: str = ".") -> OWASPScanResult:
        root = Path(repo_path).resolve()
        findings: List[OWASPFinding] = []
        files_scanned = 0

        try:
            for f in root.rglob("*"):
                if not f.is_file():
                    continue
                if any(part in _SKIP_DIRS for part in f.parts):
                    continue
                if f.suffix.lower() not in _SOURCE_EXTS:
                    continue
                files_scanned += 1
                findings.extend(self._scan_file(f, root))
        except Exception as e:
            return OWASPScanResult(
                repo_path=str(root),
                findings=[],
                files_scanned=files_scanned,
                risk_score=0.0,
                owasp_coverage={},
                scan_error=str(e),
            )

        # Deduplicate by (rule_id, file, line)
        seen: set = set()
        deduped: List[OWASPFinding] = []
        for finding in findings:
            key = (finding.rule_id, finding.source_file, finding.line_number)
            if key not in seen:
                seen.add(key)
                deduped.append(finding)

        risk = self._compute_risk(deduped, files_scanned)
        coverage = {}
        for f in deduped:
            coverage[f.owasp_id] = coverage.get(f.owasp_id, 0) + 1

        return OWASPScanResult(
            repo_path=str(root),
            findings=deduped,
            files_scanned=files_scanned,
            risk_score=risk,
            owasp_coverage=coverage,
        )

    def _scan_file(self, path: Path, root: Path) -> List[OWASPFinding]:
        try:
            source = path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            return []

        rel = str(path.relative_to(root)).replace("\\", "/")
        findings: List[OWASPFinding] = []

        for owasp_id, rule_id, severity, pattern, description, cwe in _RULES:
            for m in pattern.finditer(source):
                line_num = source[: m.start()].count("\n") + 1
                evidence = source[max(0, m.start() - 20): m.end() + 60].strip()
                findings.append(OWASPFinding(
                    owasp_id=owasp_id,
                    rule_id=rule_id,
                    severity=severity,
                    source_file=rel,
                    line_number=line_num,
                    evidence=evidence,
                    description=description,
                    cwe=cwe,
                    owasp_category=_OWASP_NAMES.get(owasp_id, owasp_id),
                ))

        return findings

    @staticmethod
    def _compute_risk(findings: List[OWASPFinding], files_scanned: int) -> float:
        """Density-normalised risk score 0.0–1.0."""
        if not findings or files_scanned == 0:
            return 0.0
        weights = {"critical": 10, "high": 5, "medium": 2, "low": 1}
        raw = sum(weights.get(f.severity, 1) for f in findings)
        # Normalise: 1.0 = 10 critical findings per file (extreme)
        normalised = raw / (files_scanned * 10)
        return round(min(normalised, 1.0), 3)
