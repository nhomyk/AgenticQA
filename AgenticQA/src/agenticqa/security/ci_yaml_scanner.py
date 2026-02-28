"""
CIYAMLInjectionScanner — detects GitHub Actions YAML injection vulnerabilities.

Problem
-------
GitHub Actions YAML files frequently interpolate untrusted values directly into
`run:` shell steps via ${{ ... }} expressions.  When github.event.issue.title,
github.head_ref, or other PR/issue-sourced values flow into shell commands
without sanitisation, an attacker can inject arbitrary shell commands that run
in the CI context — with full access to repository secrets.

This is GitHub's own documented CVE class:
  https://securitylab.github.com/research/github-actions-untrusted-input/

Attack vectors detected
-----------------------
EXPRESSION_INJECTION    — untrusted github context expression in run: step
SECRET_EXFIL            — pattern that could send secrets to external URL
UNPINNED_ACTION         — action uses floating tag (v1, main) not SHA digest
SELF_HOSTED_RUNNER      — self-hosted runners can be used for lateral movement
PWSH_BYPASS             — PowerShell execution policy bypass flags
PULL_REQUEST_WRITE      — PR_TARGET trigger with write permissions (confused deputy)
ARTIFACT_INJECTION      — upload-artifact with user-controlled path

Usage
-----
    from agenticqa.security.ci_yaml_scanner import CIYAMLInjectionScanner

    scanner = CIYAMLInjectionScanner()
    results = scanner.scan_directory(".github/workflows")
    for r in results:
        for f in r.findings:
            print(f)
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

# ── Untrusted GitHub context sources ─────────────────────────────────────────

_UNTRUSTED_SOURCES = [
    r"github\.event\.issue\.title",
    r"github\.event\.issue\.body",
    r"github\.event\.pull_request\.title",
    r"github\.event\.pull_request\.body",
    r"github\.event\.pull_request\.head\.ref",
    r"github\.event\.pull_request\.head\.label",
    r"github\.event\.comment\.body",
    r"github\.event\.review\.body",
    r"github\.event\.review_comment\.body",
    r"github\.event\.discussion\.title",
    r"github\.event\.discussion\.body",
    r"github\.head_ref",
    r"github\.event\.workflow_run\.head_branch",
]

_UNTRUSTED_RE = re.compile(
    r"\$\{\{[^}]*(?:" + "|".join(_UNTRUSTED_SOURCES) + r")[^}]*\}\}",
    re.IGNORECASE,
)

# Pattern: secrets sent to external via curl/wget
_SECRET_EXFIL_RE = re.compile(
    r"(curl|wget|nc|ncat|bash\s+-i)\s+.*(\$\{\{\s*secrets\.|GITHUB_TOKEN)",
    re.IGNORECASE,
)

# Pinned action: uses: owner/repo@SHA (40 hex chars)
_SHA_PIN_RE = re.compile(r"uses:\s+\S+@[0-9a-f]{40}", re.IGNORECASE)
_USES_RE    = re.compile(r"uses:\s+(\S+@\S+)")

_SELF_HOSTED_RE = re.compile(r"runs-on:.*self-hosted", re.IGNORECASE)
_PWSH_BYPASS_RE = re.compile(r"-ExecutionPolicy\s+Bypass", re.IGNORECASE)
_PR_TARGET_RE   = re.compile(r"pull_request_target", re.IGNORECASE)
_ARTIFACT_RE    = re.compile(r"upload-artifact.*\$\{\{", re.IGNORECASE | re.DOTALL)

_SEVERITY_WEIGHTS = {"critical": 0.40, "high": 0.20, "medium": 0.10, "low": 0.05}


@dataclass
class CIFinding:
    lineno: int
    attack_type: str
    severity: str
    detail: str
    matched: str = ""

    def __str__(self) -> str:
        return f"[{self.severity.upper()}] {self.attack_type} line {self.lineno}: {self.detail}"


@dataclass
class CIScanResult:
    path: str
    findings: List[CIFinding] = field(default_factory=list)
    risk_score: float = 0.0
    parse_error: Optional[str] = None

    @property
    def is_safe(self) -> bool:
        return (
            self.parse_error is None
            and not any(f.severity in ("critical", "high") for f in self.findings)
            and self.risk_score < 0.5
        )


class CIYAMLInjectionScanner:
    """Scans GitHub Actions YAML files for injection vulnerabilities."""

    def scan_directory(self, path: str) -> List[CIScanResult]:
        root = Path(path)
        results = []
        for p in sorted(root.rglob("*.yml")) + sorted(root.rglob("*.yaml")):
            # Only scan workflow files
            if ".github" in str(p) or "workflow" in str(p).lower() or "ci" in p.stem.lower():
                results.append(self.scan_file(str(p)))
        return results

    def scan_file(self, path: str) -> CIScanResult:
        try:
            text = Path(path).read_text(encoding="utf-8", errors="replace")
        except Exception as exc:
            return CIScanResult(path=path, parse_error=str(exc))

        findings: List[CIFinding] = []
        lines = text.splitlines()

        in_run_block = False
        run_indent = 0
        pr_target_present = False

        for lineno, line in enumerate(lines, start=1):
            stripped = line.lstrip()

            # Track pull_request_target trigger (context for confused-deputy check)
            if _PR_TARGET_RE.search(line):
                pr_target_present = True
                findings.append(CIFinding(
                    lineno=lineno, attack_type="PULL_REQUEST_WRITE",
                    severity="high",
                    detail="pull_request_target trigger can give write perms to fork PRs — verify no checkout of PR head",
                    matched=line.strip(),
                ))

            # Detect expression injection in run: steps
            if _UNTRUSTED_RE.search(line):
                findings.append(CIFinding(
                    lineno=lineno, attack_type="EXPRESSION_INJECTION",
                    severity="critical",
                    detail="Untrusted GitHub context expression interpolated directly into shell — use intermediate env var",
                    matched=_UNTRUSTED_RE.search(line).group(0),
                ))

            # Secret exfiltration
            if _SECRET_EXFIL_RE.search(line):
                findings.append(CIFinding(
                    lineno=lineno, attack_type="SECRET_EXFIL",
                    severity="critical",
                    detail="Possible secret exfiltration via network command",
                    matched=line.strip()[:100],
                ))

            # Self-hosted runner
            if _SELF_HOSTED_RE.search(line):
                findings.append(CIFinding(
                    lineno=lineno, attack_type="SELF_HOSTED_RUNNER",
                    severity="medium",
                    detail="Self-hosted runner: environment not isolated; lateral movement risk",
                    matched=line.strip(),
                ))

            # Unpinned actions
            m = _USES_RE.search(line)
            if m and not _SHA_PIN_RE.search(line):
                ref = m.group(1)
                # Skip docker:// and local ./ actions
                if not ref.startswith(("docker://", "./")):
                    findings.append(CIFinding(
                        lineno=lineno, attack_type="UNPINNED_ACTION",
                        severity="medium",
                        detail=f"Action not pinned to commit SHA: {ref} — vulnerable to tag mutation attack",
                        matched=ref,
                    ))

            # PowerShell bypass
            if _PWSH_BYPASS_RE.search(line):
                findings.append(CIFinding(
                    lineno=lineno, attack_type="PWSH_BYPASS",
                    severity="high",
                    detail="PowerShell execution policy bypass — verify this is intentional",
                    matched=line.strip(),
                ))

            # Artifact injection
            if _ARTIFACT_RE.search(line):
                findings.append(CIFinding(
                    lineno=lineno, attack_type="ARTIFACT_INJECTION",
                    severity="medium",
                    detail="upload-artifact path contains expression — attacker may control artifact name",
                    matched=line.strip()[:80],
                ))

        # Deduplicate (same lineno + attack_type)
        seen = set()
        deduped = []
        for f in findings:
            key = (f.lineno, f.attack_type)
            if key not in seen:
                seen.add(key)
                deduped.append(f)

        risk = min(sum(_SEVERITY_WEIGHTS.get(f.severity, 0.05) for f in deduped), 1.0)
        return CIScanResult(path=path, findings=deduped, risk_score=round(risk, 4))
