"""
Race Condition & Concurrency Probe — static analysis for common race
condition patterns in Python source code.

Pure Python + re — no subprocess, no external tools.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Tuple


# ---------------------------------------------------------------------------
# Source extensions to scan
# ---------------------------------------------------------------------------
_SOURCE_EXTS = {".py"}
_SKIP_DIRS = {"node_modules", ".venv", "venv", "__pycache__", ".git", "dist", "build", "tests"}

# Severity weights for risk score
_SEVERITY_WEIGHTS: Dict[str, float] = {
    "critical": 1.0,
    "high": 0.6,
    "medium": 0.3,
}

# Shared file name hints for RC-006
_SHARED_FILE_HINTS = frozenset(["log", "cache", "state", "config"])


# ---------------------------------------------------------------------------
# Pattern definitions
# Each: (pattern_id, severity, description, attack_scenario, line_pattern, multiline)
# ---------------------------------------------------------------------------

_PATTERNS: List[Tuple[str, str, str, str, str, bool]] = [
    (
        "RC-001",
        "critical",
        "TOCTOU — check-then-act on files",
        "Attacker replaces file between existence check and open/write",
        r"if\s+os\.path\.(exists|isfile|isdir)\(.+\)",
        False,
    ),
    (
        "RC-002",
        "high",
        "Non-atomic read-modify-write on shared state",
        "Two threads read same value, both increment, one write is lost",
        r"\w+\s*\+=\s*1|\w+\s*=\s*\w+\s*\+\s*1",
        False,
    ),
    (
        "RC-003",
        "high",
        "Unsynchronized global variable mutation",
        "Global state modified without lock — concurrent requests corrupt data",
        r"^(\s*)global\s+\w+",
        False,
    ),
    (
        "RC-004",
        "critical",
        "TOCTOU on session/token check",
        "Token validated then used — window for token revocation between check and use",
        r"if\s+\w+\.(is_valid|is_authenticated|is_active)\(\)",
        False,
    ),
    (
        "RC-005",
        "high",
        "Double-checked locking anti-pattern",
        "Object created twice — initialization not atomic",
        r"if\s+\w+\s+is\s+None:",
        False,
    ),
    (
        "RC-006",
        "medium",
        "File lock not used on shared file write",
        "Concurrent writes corrupt file — no exclusive lock held",
        r"with\s+open\s*\(.+['\"]w['\"]",
        False,
    ),
    (
        "RC-007",
        "medium",
        "Unprotected lazy initialization",
        "Two threads both see None, both initialize — second write discards first",
        r"if\s+(self\.)?\w+\s+is\s+None:",
        False,
    ),
]

_COMPILED_PATTERNS = [
    (pid, sev, desc, attack, re.compile(pat, re.MULTILINE), ml)
    for pid, sev, desc, attack, pat, ml in _PATTERNS
]


# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------

@dataclass
class RaceConditionFinding:
    pattern_id: str
    severity: str
    source_file: str
    line_number: int
    evidence: str
    description: str
    attack_scenario: str

    def to_dict(self) -> dict:
        return {
            "pattern_id": self.pattern_id,
            "severity": self.severity,
            "source_file": self.source_file,
            "line_number": self.line_number,
            "evidence": self.evidence,
            "description": self.description,
            "attack_scenario": self.attack_scenario,
        }


@dataclass
class RaceConditionResult:
    repo_path: str
    findings: List[RaceConditionFinding]
    files_scanned: int
    risk_score: float

    def by_pattern(self) -> Dict[str, List[RaceConditionFinding]]:
        result: Dict[str, List[RaceConditionFinding]] = {}
        for f in self.findings:
            result.setdefault(f.pattern_id, []).append(f)
        return result

    def to_dict(self) -> dict:
        return {
            "repo_path": self.repo_path,
            "findings": [f.to_dict() for f in self.findings],
            "files_scanned": self.files_scanned,
            "risk_score": self.risk_score,
            "by_pattern": {k: [f.to_dict() for f in v] for k, v in self.by_pattern().items()},
        }


# ---------------------------------------------------------------------------
# Detector
# ---------------------------------------------------------------------------

class RaceConditionDetector:
    """Static analysis for common race condition patterns in Python code."""

    def scan(self, repo_path: str = ".") -> RaceConditionResult:
        root = Path(repo_path).resolve()
        all_findings: List[RaceConditionFinding] = []
        files_scanned = 0

        for path in root.rglob("*"):
            if not path.is_file():
                continue
            if any(part in _SKIP_DIRS for part in path.parts):
                continue
            if path.suffix not in _SOURCE_EXTS:
                continue
            try:
                content = path.read_text(encoding="utf-8", errors="ignore")
                rel = str(path.relative_to(root))
                findings = self.scan_content(content, file_path=rel)
                all_findings.extend(findings)
                files_scanned += 1
            except OSError:
                pass

        # Deduplicate by (pattern_id, file, line)
        seen: set = set()
        unique: List[RaceConditionFinding] = []
        for f in all_findings:
            key = (f.pattern_id, f.source_file, f.line_number)
            if key not in seen:
                seen.add(key)
                unique.append(f)

        risk_score = min(
            100.0,
            sum(_SEVERITY_WEIGHTS.get(f.severity, 0) * 10 for f in unique),
        )

        return RaceConditionResult(
            repo_path=str(root),
            findings=unique,
            files_scanned=files_scanned,
            risk_score=round(risk_score, 2),
        )

    def scan_content(
        self, content: str, file_path: str = ""
    ) -> List[RaceConditionFinding]:
        """Scan content string for race condition patterns."""
        findings: List[RaceConditionFinding] = []
        lines = content.splitlines()

        for pid, sev, desc, attack, pattern, _ml in _COMPILED_PATTERNS:
            for m in pattern.finditer(content):
                # Calculate line number from match position
                line_num = content[: m.start()].count("\n") + 1
                evidence = lines[line_num - 1].strip() if line_num <= len(lines) else m.group(0)

                # RC-006: only flag if file var name suggests shared state
                if pid == "RC-006":
                    if not any(hint in evidence.lower() for hint in _SHARED_FILE_HINTS):
                        continue

                findings.append(
                    RaceConditionFinding(
                        pattern_id=pid,
                        severity=sev,
                        source_file=file_path,
                        line_number=line_num,
                        evidence=evidence,
                        description=desc,
                        attack_scenario=attack,
                    )
                )

        return findings
