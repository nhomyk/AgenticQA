"""
Secrets History Scanner — scans git commit history and current HEAD for
accidentally committed secrets. Pure Python regex — no external tools.

scan_content() works independently (no git required) and is used for
unit tests and current HEAD scanning.
"""
from __future__ import annotations

import re
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional, Tuple


# ---------------------------------------------------------------------------
# Secret patterns
# ---------------------------------------------------------------------------
_SECRET_PATTERNS: List[Tuple[str, str, str]] = [
    ("AWS_ACCESS_KEY",      r"AKIA[0-9A-Z]{16}",                                                    "critical"),
    ("GITHUB_TOKEN",        r"gh[pors]_[0-9a-zA-Z]{36,}",                                           "critical"),
    ("STRIPE_KEY",          r"sk_(live|test)_[0-9a-zA-Z]{24,}",                                     "critical"),
    ("SENDGRID_KEY",        r"SG\.[0-9a-zA-Z\-_]{22}\.[0-9a-zA-Z\-_]{43}",                         "critical"),
    ("PRIVATE_KEY_PEM",     r"-----BEGIN (RSA |EC |OPENSSH )?PRIVATE KEY-----",                     "critical"),
    ("STRIPE_PUBLISHABLE",  r"pk_(live|test)_[0-9a-zA-Z]{24,}",                                     "high"),
    ("SLACK_TOKEN",         r"xox[baprs]-[0-9]{12}-[0-9]{12}-[0-9a-zA-Z]{24}",                     "high"),
    ("GENERIC_API_KEY",     r"api[_\-]?key\s*[=:]\s*[\"'][0-9a-zA-Z\-_]{20,}[\"']",               "high"),
    ("BEARER_TOKEN",        r"Bearer\s+[0-9a-zA-Z\-_\.]{20,}",                                      "high"),
    ("BASIC_AUTH_URL",      r"https?://[^:@\s]+:[^@\s]+@",                                          "high"),
    ("GENERIC_SECRET",      r"(secret|password|passwd|pwd)\s*[=:]\s*[\"'][^\"']{8,}[\"']",          "medium"),
]

_COMPILED_PATTERNS = [(name, re.compile(pat, re.IGNORECASE), sev) for name, pat, sev in _SECRET_PATTERNS]

# Extensions to scan in current HEAD
_SCAN_EXTS = {
    ".py", ".ts", ".tsx", ".js", ".jsx", ".env", ".yaml", ".yml",
    ".json", ".conf", ".ini", ".toml", ".sh", ".bash",
}

_SKIP_DIRS = {"node_modules", ".venv", "venv", "__pycache__", ".git", "dist", "build"}

# Severity weights for risk score
_SEVERITY_WEIGHTS = {"critical": 1.0, "high": 0.6, "medium": 0.3}


# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------

@dataclass
class SecretFinding:
    secret_type: str
    commit_hash: str      # "HEAD" for current file scan
    file_path: str
    line_number: int
    evidence: str         # redacted value
    severity: str
    still_present: bool

    def to_dict(self) -> dict:
        return {
            "secret_type": self.secret_type,
            "commit_hash": self.commit_hash,
            "file_path": self.file_path,
            "line_number": self.line_number,
            "evidence": self.evidence,
            "severity": self.severity,
            "still_present": self.still_present,
        }


@dataclass
class SecretsHistoryScanResult:
    repo_path: str
    findings: List[SecretFinding]
    commits_scanned: int
    files_scanned: int
    unique_secret_types: List[str]
    has_live_secrets: bool
    risk_score: float

    def to_dict(self) -> dict:
        return {
            "repo_path": self.repo_path,
            "findings": [f.to_dict() for f in self.findings],
            "commits_scanned": self.commits_scanned,
            "files_scanned": self.files_scanned,
            "unique_secret_types": self.unique_secret_types,
            "has_live_secrets": self.has_live_secrets,
            "risk_score": self.risk_score,
        }


# ---------------------------------------------------------------------------
# Scanner
# ---------------------------------------------------------------------------

class SecretsHistoryScanner:
    """Scan git history and HEAD for accidentally committed secrets."""

    def scan(
        self,
        repo_path: str = ".",
        scan_history: bool = True,
        max_commits: int = 100,
    ) -> SecretsHistoryScanResult:
        root = Path(repo_path).resolve()
        all_findings: List[SecretFinding] = []
        commits_scanned = 0
        files_scanned = 0

        # 1. Scan current HEAD files
        head_findings: List[SecretFinding] = []
        for path in root.rglob("*"):
            if not path.is_file():
                continue
            if any(part in _SKIP_DIRS for part in path.parts):
                continue
            if path.suffix not in _SCAN_EXTS and path.name not in {".env"}:
                continue
            try:
                content = path.read_text(encoding="utf-8", errors="ignore")
                rel = str(path.relative_to(root))
                findings = self.scan_content(content, file_path=rel, commit_hash="HEAD")
                for f in findings:
                    f.still_present = True
                head_findings.extend(findings)
                files_scanned += 1
            except OSError:
                pass

        all_findings.extend(head_findings)

        # Track which (type, file, line) combos are still present
        live_keys = {(f.secret_type, f.file_path, f.line_number) for f in head_findings}

        # 2. Scan git history
        history_findings: List[SecretFinding] = []
        if scan_history:
            history_findings, commits_scanned = self._scan_git_history(root, max_commits)
            for f in history_findings:
                key = (f.secret_type, f.file_path, f.line_number)
                f.still_present = key in live_keys
            all_findings.extend(history_findings)

        # Deduplicate by (type, commit, file, line)
        seen = set()
        unique_findings: List[SecretFinding] = []
        for f in all_findings:
            key = (f.secret_type, f.commit_hash, f.file_path, f.line_number)
            if key not in seen:
                seen.add(key)
                unique_findings.append(f)

        unique_types = sorted(set(f.secret_type for f in unique_findings))
        has_live = any(f.still_present for f in unique_findings)

        # Risk score
        risk = min(100.0, sum(_SEVERITY_WEIGHTS.get(f.severity, 0) * 10 for f in unique_findings))

        return SecretsHistoryScanResult(
            repo_path=str(root),
            findings=unique_findings,
            commits_scanned=commits_scanned,
            files_scanned=files_scanned,
            unique_secret_types=unique_types,
            has_live_secrets=has_live,
            risk_score=round(risk, 2),
        )

    def scan_content(
        self,
        content: str,
        file_path: str = "",
        commit_hash: str = "HEAD",
    ) -> List[SecretFinding]:
        """Scan a string of content for secret patterns."""
        findings: List[SecretFinding] = []
        lines = content.splitlines()
        for line_num, line in enumerate(lines, start=1):
            for name, pattern, severity in _COMPILED_PATTERNS:
                for m in pattern.finditer(line):
                    findings.append(
                        SecretFinding(
                            secret_type=name,
                            commit_hash=commit_hash,
                            file_path=file_path,
                            line_number=line_num,
                            evidence=self._redact(m.group(0)),
                            severity=severity,
                            still_present=False,
                        )
                    )
        return findings

    def _scan_git_history(
        self, root: Path, max_commits: int
    ) -> Tuple[List[SecretFinding], int]:
        """Scan git commit history for secrets using git show."""
        findings: List[SecretFinding] = []
        try:
            result = subprocess.run(
                ["git", "log", "--format=%H", f"-{max_commits}"],
                cwd=str(root),
                capture_output=True,
                text=True,
                timeout=30,
            )
            if result.returncode != 0:
                return [], 0
            commits = [c.strip() for c in result.stdout.splitlines() if c.strip()]
        except (subprocess.TimeoutExpired, OSError, FileNotFoundError):
            return [], 0

        for commit in commits:
            try:
                diff_result = subprocess.run(
                    ["git", "diff-tree", "--no-commit-id", "-r", "--unified=0", commit],
                    cwd=str(root),
                    capture_output=True,
                    text=True,
                    timeout=30,
                )
                if diff_result.returncode != 0:
                    continue
                content = diff_result.stdout
                # Extract added lines (+) only
                added_lines: List[Tuple[str, str]] = []
                current_file = ""
                for line in content.splitlines():
                    if line.startswith("+++ b/"):
                        current_file = line[6:]
                    elif line.startswith("+") and not line.startswith("+++"):
                        added_lines.append((current_file, line[1:]))

                # Scan each added line
                for file_path, line_text in added_lines:
                    for name, pattern, severity in _COMPILED_PATTERNS:
                        for m in pattern.finditer(line_text):
                            findings.append(
                                SecretFinding(
                                    secret_type=name,
                                    commit_hash=commit[:12],
                                    file_path=file_path,
                                    line_number=0,
                                    evidence=self._redact(m.group(0)),
                                    severity=severity,
                                    still_present=False,
                                )
                            )
            except (subprocess.TimeoutExpired, OSError):
                continue

        return findings, len(commits)

    def _redact(self, value: str) -> str:
        """Redact a secret value: show first 4 and last 4 chars."""
        if len(value) >= 8:
            return value[:4] + "****" + value[-4:]
        return "****"
