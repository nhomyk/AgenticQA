"""Custom rule authoring engine.

Allows enterprises to define their own scanner rules that run alongside
AgenticQA's built-in scanners.

Rule format (YAML/JSON):
    {
        "id": "CORP-001",
        "name": "Unapproved LLM Provider",
        "description": "All LLM calls must go through the corporate AI gateway",
        "severity": "high",
        "pattern": "openai\\.ChatCompletion|anthropic\\.Anthropic",
        "file_pattern": "*.py",
        "message": "Direct LLM API call detected. Use corp.ai.gateway instead.",
        "tags": ["governance", "ai-gateway"]
    }

Rules stored at:
    .agenticqa/custom_rules.json (per-repo)
    ~/.agenticqa/global_rules.json (org-wide)
"""
from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass, field
from fnmatch import fnmatch
from pathlib import Path
from typing import Optional


@dataclass
class CustomRule:
    """A single custom scanner rule."""
    id: str
    name: str
    description: str
    severity: str  # critical | high | medium | low | info
    pattern: str   # regex pattern to match
    file_pattern: str = "*"  # glob for files to scan
    message: str = ""
    tags: list = field(default_factory=list)
    enabled: bool = True
    exclude_dirs: list = field(default_factory=lambda: [
        "node_modules", ".git", "__pycache__", ".venv", "vendor", "target",
    ])

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "severity": self.severity,
            "pattern": self.pattern,
            "file_pattern": self.file_pattern,
            "message": self.message,
            "tags": self.tags,
            "enabled": self.enabled,
        }


@dataclass
class CustomRuleFinding:
    """A finding from a custom rule."""
    rule_id: str
    rule_name: str
    severity: str
    file: str
    line: int
    evidence: str
    message: str

    def to_dict(self) -> dict:
        return {
            "rule_id": self.rule_id,
            "rule_name": self.rule_name,
            "severity": self.severity,
            "file": self.file,
            "line": self.line,
            "evidence": self.evidence,
            "message": self.message,
        }


@dataclass
class CustomRuleScanResult:
    """Result from scanning with custom rules."""
    rules_loaded: int
    rules_matched: int
    total_findings: int
    critical: int
    findings: list = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "rules_loaded": self.rules_loaded,
            "rules_matched": self.rules_matched,
            "total_findings": self.total_findings,
            "critical": self.critical,
            "findings": [f.to_dict() for f in self.findings],
        }


class CustomRuleEngine:
    """Load and execute custom scanner rules."""

    def __init__(self, rules: Optional[list[CustomRule]] = None):
        self._rules: list[CustomRule] = rules or []

    @property
    def rules(self) -> list[CustomRule]:
        return self._rules

    def load_from_repo(self, repo_path: str) -> int:
        """Load custom rules from .agenticqa/custom_rules.json."""
        rules_file = Path(repo_path) / ".agenticqa" / "custom_rules.json"
        if rules_file.exists():
            return self._load_file(rules_file)
        return 0

    def load_global(self) -> int:
        """Load global custom rules from ~/.agenticqa/global_rules.json."""
        global_file = Path(os.path.expanduser("~/.agenticqa")) / "global_rules.json"
        if global_file.exists():
            return self._load_file(global_file)
        return 0

    def add_rule(self, rule: CustomRule) -> None:
        """Add a rule programmatically."""
        self._rules.append(rule)

    def save_to_repo(self, repo_path: str) -> Path:
        """Save current rules to .agenticqa/custom_rules.json."""
        rules_file = Path(repo_path) / ".agenticqa" / "custom_rules.json"
        rules_file.parent.mkdir(parents=True, exist_ok=True)
        with open(rules_file, "w") as f:
            json.dump(
                {"rules": [r.to_dict() for r in self._rules]},
                f, indent=2,
            )
        return rules_file

    def scan(self, repo_path: str) -> CustomRuleScanResult:
        """Scan a repo with all loaded rules."""
        findings: list[CustomRuleFinding] = []
        rules_matched = set()

        enabled_rules = [r for r in self._rules if r.enabled]
        if not enabled_rules:
            return CustomRuleScanResult(rules_loaded=len(self._rules), rules_matched=0,
                                       total_findings=0, critical=0)

        # Compile patterns once
        compiled = []
        for rule in enabled_rules:
            try:
                compiled.append((rule, re.compile(rule.pattern, re.IGNORECASE)))
            except re.error:
                continue

        # Walk repo files
        repo = Path(repo_path)
        for fpath in self._iter_files(repo, enabled_rules):
            try:
                content = fpath.read_text(errors="ignore")
            except (OSError, UnicodeDecodeError):
                continue

            rel_path = str(fpath.relative_to(repo))

            for rule, pattern in compiled:
                if not fnmatch(fpath.name, rule.file_pattern):
                    continue

                for i, line_text in enumerate(content.split("\n"), 1):
                    match = pattern.search(line_text)
                    if match:
                        rules_matched.add(rule.id)
                        findings.append(CustomRuleFinding(
                            rule_id=rule.id,
                            rule_name=rule.name,
                            severity=rule.severity,
                            file=rel_path,
                            line=i,
                            evidence=line_text.strip()[:120],
                            message=rule.message or rule.description,
                        ))

        critical = sum(1 for f in findings if f.severity == "critical")

        return CustomRuleScanResult(
            rules_loaded=len(enabled_rules),
            rules_matched=len(rules_matched),
            total_findings=len(findings),
            critical=critical,
            findings=findings,
        )

    def _iter_files(self, repo: Path, rules: list[CustomRule]) -> list[Path]:
        """Iterate source files, respecting exclude dirs."""
        exclude_dirs = set()
        for rule in rules:
            exclude_dirs.update(rule.exclude_dirs)

        files = []
        for fpath in repo.rglob("*"):
            if not fpath.is_file():
                continue
            if any(excl in fpath.parts for excl in exclude_dirs):
                continue
            if fpath.suffix in (".pyc", ".pyo", ".class", ".o", ".so", ".dll"):
                continue
            files.append(fpath)
            if len(files) >= 5000:
                break
        return files

    def _load_file(self, path: Path) -> int:
        """Load rules from a JSON file."""
        try:
            with open(path) as f:
                data = json.load(f)
            rules_data = data.get("rules", data if isinstance(data, list) else [])
            loaded = 0
            for rd in rules_data:
                if not rd.get("id") or not rd.get("pattern"):
                    continue
                self._rules.append(CustomRule(
                    id=rd["id"],
                    name=rd.get("name", rd["id"]),
                    description=rd.get("description", ""),
                    severity=rd.get("severity", "medium"),
                    pattern=rd["pattern"],
                    file_pattern=rd.get("file_pattern", "*"),
                    message=rd.get("message", ""),
                    tags=rd.get("tags", []),
                    enabled=rd.get("enabled", True),
                ))
                loaded += 1
            return loaded
        except (json.JSONDecodeError, OSError):
            return 0
