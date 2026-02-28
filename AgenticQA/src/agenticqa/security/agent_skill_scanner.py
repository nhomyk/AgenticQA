"""
AgentSkillScanner — AST-based security scanner for custom agent skills.

Parses custom agent `.py` files with Python's built-in `ast` module (zero
extra dependencies) and detects dangerous patterns *before* the file is
imported or executed.

Attack types detected
---------------------
COMMAND_INJECTION  — eval/exec, subprocess import, os.system, pickle, ctypes
SSRF_RISK          — socket, requests/httpx/aiohttp, cloud-metadata IPs
AMBIENT_AUTHORITY  — open() in write mode, os.environ mutation
GOVERNANCE_BYPASS  — direct import of agenticqa governance modules

Usage
-----
    from agenticqa.security.agent_skill_scanner import AgentSkillScanner

    scanner = AgentSkillScanner()
    result = scanner.scan(".agenticqa/custom_agents/my_agent.py")
    if not result.is_safe:
        raise RuntimeError(f"Blocked: {[f.detail for f in result.findings]}")
"""

from __future__ import annotations

import ast
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional

# ---------------------------------------------------------------------------
# Severity weights (same scale as MCP scanner and API middleware)
# ---------------------------------------------------------------------------
_SEVERITY_WEIGHTS = {"critical": 0.4, "high": 0.2, "medium": 0.1, "low": 0.05}

# ---------------------------------------------------------------------------
# Dangerous imports — name → (attack_type, severity)
# ---------------------------------------------------------------------------
_DANGEROUS_IMPORTS = {
    "subprocess":                       ("COMMAND_INJECTION", "critical"),
    "pty":                              ("COMMAND_INJECTION", "critical"),
    "pickle":                           ("COMMAND_INJECTION", "high"),
    "shelve":                           ("COMMAND_INJECTION", "high"),
    "marshal":                          ("COMMAND_INJECTION", "high"),
    "ctypes":                           ("COMMAND_INJECTION", "high"),
    "cffi":                             ("COMMAND_INJECTION", "high"),
    "socket":                           ("SSRF_RISK", "high"),
    "requests":                         ("SSRF_RISK", "medium"),
    "urllib":                           ("SSRF_RISK", "medium"),
    "httpx":                            ("SSRF_RISK", "medium"),
    "aiohttp":                          ("SSRF_RISK", "medium"),
    "http.client":                      ("SSRF_RISK", "medium"),
    # Governance modules — importing these to monkey-patch is a bypass vector
    "agenticqa.constitutional_gate":    ("GOVERNANCE_BYPASS", "critical"),
    "agenticqa.constitutional_wrapper": ("GOVERNANCE_BYPASS", "critical"),
    "agenticqa.delegation.guardrails":  ("GOVERNANCE_BYPASS", "critical"),
}

# ---------------------------------------------------------------------------
# Dangerous builtins / free functions called directly
# ---------------------------------------------------------------------------
_DANGEROUS_CALLS = {
    "eval":       ("COMMAND_INJECTION", "critical", "eval() executes arbitrary Python code"),
    "exec":       ("COMMAND_INJECTION", "critical", "exec() executes arbitrary Python code"),
    "compile":    ("COMMAND_INJECTION", "high",     "compile() can be used to build executable code objects"),
    "__import__": ("COMMAND_INJECTION", "high",     "__import__() bypasses import restrictions"),
    "open":       None,  # handled specially — only write modes are flagged
}

# ---------------------------------------------------------------------------
# Dangerous attribute names on any object
# ---------------------------------------------------------------------------
_DANGEROUS_ATTRS = {
    "__globals__":  ("COMMAND_INJECTION", "critical", "__globals__ exposes the module's global namespace"),
    "__builtins__": ("COMMAND_INJECTION", "critical", "__builtins__ gives access to all built-in functions"),
    "__code__":     ("COMMAND_INJECTION", "critical", "__code__ exposes raw bytecode for manipulation"),
}

# ---------------------------------------------------------------------------
# Cloud metadata / SSRF string literals
# ---------------------------------------------------------------------------
_SSRF_LITERALS = {
    "169.254.169.254":        ("SSRF_RISK", "critical", "AWS/Azure IMDS metadata endpoint hardcoded"),
    "metadata.google.internal": ("SSRF_RISK", "critical", "GCP metadata server hardcoded"),
    "100.100.100.200":        ("SSRF_RISK", "critical", "Alibaba Cloud metadata endpoint hardcoded"),
}


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class SkillFinding:
    """A single security finding from the AST scanner."""
    lineno: int
    col: int
    attack_type: str   # e.g. COMMAND_INJECTION
    severity: str      # critical | high | medium | low
    detail: str        # human-readable description
    node_type: str     # ast node class name, e.g. "Call"

    def __repr__(self) -> str:  # noqa: D105
        return f"[{self.severity.upper()}] {self.attack_type} at line {self.lineno}: {self.detail}"


@dataclass
class SkillScanResult:
    """Result of scanning one agent skill file."""
    path: str
    findings: List[SkillFinding] = field(default_factory=list)
    risk_score: float = 0.0
    parse_error: Optional[str] = None

    @property
    def is_safe(self) -> bool:
        """
        True only when:
        - the file parsed without error,
        - no critical findings were detected, and
        - the aggregate risk score is below 0.5.
        """
        return (
            self.parse_error is None
            and not any(f.severity == "critical" for f in self.findings)
            and self.risk_score < 0.5
        )

    def to_dict(self) -> dict:
        return {
            "path": self.path,
            "is_safe": self.is_safe,
            "risk_score": round(self.risk_score, 3),
            "parse_error": self.parse_error,
            "findings": [
                {
                    "lineno": f.lineno,
                    "col": f.col,
                    "attack_type": f.attack_type,
                    "severity": f.severity,
                    "detail": f.detail,
                    "node_type": f.node_type,
                }
                for f in self.findings
            ],
        }


# ---------------------------------------------------------------------------
# AST visitor
# ---------------------------------------------------------------------------

class _SkillVisitor(ast.NodeVisitor):
    """Walk the AST and accumulate security findings."""

    def __init__(self) -> None:
        self.findings: List[SkillFinding] = []

    def _add(
        self,
        node: ast.AST,
        attack_type: str,
        severity: str,
        detail: str,
    ) -> None:
        self.findings.append(
            SkillFinding(
                lineno=getattr(node, "lineno", 0),
                col=getattr(node, "col_offset", 0),
                attack_type=attack_type,
                severity=severity,
                detail=detail,
                node_type=type(node).__name__,
            )
        )

    # ── Import checks ────────────────────────────────────────────────────────

    def visit_Import(self, node: ast.Import) -> None:  # noqa: N802
        for alias in node.names:
            name = alias.name
            # Check the top-level module name and the full dotted name
            for check_name, info in _DANGEROUS_IMPORTS.items():
                if name == check_name or name.startswith(check_name + "."):
                    attack_type, severity = info
                    self._add(
                        node, attack_type, severity,
                        f"`import {name}` — dangerous module import",
                    )
                    break
        self.generic_visit(node)

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:  # noqa: N802
        module = node.module or ""
        for check_name, info in _DANGEROUS_IMPORTS.items():
            if module == check_name or module.startswith(check_name + "."):
                attack_type, severity = info
                names = ", ".join(a.name for a in node.names)
                self._add(
                    node, attack_type, severity,
                    f"`from {module} import {names}` — dangerous module import",
                )
                break
        self.generic_visit(node)

    # ── Call checks ──────────────────────────────────────────────────────────

    def visit_Call(self, node: ast.Call) -> None:  # noqa: N802
        func = node.func

        # --- Free function calls: eval(), exec(), compile(), __import__() ---
        if isinstance(func, ast.Name):
            fname = func.id
            if fname in _DANGEROUS_CALLS:
                info = _DANGEROUS_CALLS[fname]
                if info is not None:
                    attack_type, severity, detail = info
                    self._add(node, attack_type, severity, detail)
                elif fname == "open":
                    self._check_open_call(node)

        # --- Attribute calls: os.system(), os.environ.update(), etc. ---
        elif isinstance(func, ast.Attribute):
            attr = func.attr

            # os.system / os.popen / os.exec*
            if attr in {"system", "popen", "execv", "execve", "execvp", "execl", "execle"}:
                if isinstance(func.value, ast.Name) and func.value.id == "os":
                    self._add(
                        node, "COMMAND_INJECTION", "critical",
                        f"`os.{attr}()` — direct OS command execution",
                    )

            # os.environ.update / os.putenv
            elif attr in {"update", "putenv"}:
                self._check_env_mutation(node, func, attr)

        self.generic_visit(node)

    def _check_open_call(self, node: ast.Call) -> None:
        """Flag open() only when called with a write/append mode."""
        write_modes = {"w", "a", "wb", "ab", "r+b", "r+", "x", "xb"}
        for arg in node.args[1:2]:  # second positional argument = mode
            if isinstance(arg, ast.Constant) and arg.value in write_modes:
                self._add(
                    node, "AMBIENT_AUTHORITY", "medium",
                    f"`open(..., '{arg.value}')` — write-mode file access in agent skill",
                )
        for kw in node.keywords:
            if kw.arg == "mode" and isinstance(kw.value, ast.Constant):
                if kw.value.value in write_modes:
                    self._add(
                        node, "AMBIENT_AUTHORITY", "medium",
                        f"`open(..., mode='{kw.value.value}')` — write-mode file access in agent skill",
                    )

    def _check_env_mutation(self, node: ast.Call, func: ast.Attribute, attr: str) -> None:
        """Flag os.environ.update() and os.putenv()."""
        val = func.value
        is_environ_update = (
            attr == "update"
            and isinstance(val, ast.Attribute)
            and val.attr == "environ"
            and isinstance(val.value, ast.Name)
            and val.value.id == "os"
        )
        is_putenv = (
            attr == "putenv"
            and isinstance(val, ast.Name)
            and val.id == "os"
        )
        if is_environ_update:
            self._add(
                node, "AMBIENT_AUTHORITY", "medium",
                "`os.environ.update()` — modifying the parent process environment",
            )
        elif is_putenv:
            self._add(
                node, "AMBIENT_AUTHORITY", "medium",
                "`os.putenv()` — setting an environment variable directly",
            )

    # ── Attribute access checks ───────────────────────────────────────────────

    def visit_Attribute(self, node: ast.Attribute) -> None:  # noqa: N802
        if node.attr in _DANGEROUS_ATTRS:
            attack_type, severity, detail = _DANGEROUS_ATTRS[node.attr]
            self._add(node, attack_type, severity, detail)
        self.generic_visit(node)

    # ── String literal checks ─────────────────────────────────────────────────

    def visit_Constant(self, node: ast.Constant) -> None:  # noqa: N802
        if isinstance(node.value, str):
            for literal, (attack_type, severity, detail) in _SSRF_LITERALS.items():
                if literal in node.value:
                    self._add(node, attack_type, severity, detail)
        self.generic_visit(node)


# ---------------------------------------------------------------------------
# Public scanner class
# ---------------------------------------------------------------------------

class AgentSkillScanner:
    """
    AST-based security scanner for AgenticQA custom agent skills.

    Zero external dependencies — uses Python's built-in `ast` module only.
    """

    def scan(self, path: str | Path) -> SkillScanResult:
        """Scan a `.py` file on disk."""
        path = Path(path)
        try:
            source = path.read_text(encoding="utf-8", errors="replace")
        except OSError as exc:
            return SkillScanResult(
                path=str(path),
                parse_error=f"Cannot read file: {exc}",
            )
        return self.scan_source(source, filename=str(path))

    def scan_source(self, source: str, filename: str = "<string>") -> SkillScanResult:
        """
        Scan Python source code given as a string.

        Useful for scanning generated code before it is written to disk.
        """
        result = SkillScanResult(path=filename)

        try:
            tree = ast.parse(source, filename=filename)
        except SyntaxError as exc:
            result.parse_error = f"SyntaxError at line {exc.lineno}: {exc.msg}"
            return result

        visitor = _SkillVisitor()
        visitor.visit(tree)
        result.findings = visitor.findings

        # Compute risk score — sum weights, cap at 1.0
        score = sum(_SEVERITY_WEIGHTS.get(f.severity, 0.0) for f in result.findings)
        result.risk_score = min(score, 1.0)

        return result

    def scan_directory(self, path: str | Path) -> List[SkillScanResult]:
        """Scan all `*.py` files in a directory (non-recursive)."""
        directory = Path(path)
        if not directory.is_dir():
            return []
        return [self.scan(p) for p in sorted(directory.glob("*.py"))]
