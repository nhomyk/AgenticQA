"""
CVE Reachability Analyzer — import-level reachability for Python and JavaScript CVEs.

v1: Determines whether vulnerable packages are imported anywhere in the codebase.
A CVE is "reachable" if the vulnerable package appears in any import statement in source files.
Full call-graph analysis is a future extension; import-level catches the vast majority of cases.
"""
from __future__ import annotations

import ast
import json
import re
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Set


@dataclass
class CVEFinding:
    package: str
    cve_id: str
    severity: str             # "critical" | "high" | "moderate" | "low"
    fixed_version: str
    vulnerable_version: str
    description: str
    reachable: bool
    reachable_via: List[str] = field(default_factory=list)  # source files that import the package


@dataclass
class ReachabilityResult:
    cves: List[CVEFinding]
    reachable_cves: List[CVEFinding]
    unreachable_cves: List[CVEFinding]
    risk_score: float         # 0.0–1.0; weighted average of severity for reachable CVEs
    scan_error: Optional[str] = None


# Directories to skip when collecting imports
_SKIP_DIRS = frozenset({"node_modules", ".venv", "venv", "__pycache__", ".git", "dist", "build"})


class CVEReachabilityAnalyzer:
    """
    Determines whether vulnerable packages are imported anywhere in the codebase.

    Usage:
        analyzer = CVEReachabilityAnalyzer()
        result = analyzer.scan_python("/path/to/repo")
        for cve in result.reachable_cves:
            print(f"{cve.package} ({cve.cve_id}) — reachable via {cve.reachable_via}")
    """

    _SEVERITY_WEIGHTS: Dict[str, float] = {
        "critical": 1.0,
        "high": 0.7,
        "moderate": 0.4,
        "low": 0.1,
    }

    # ── Public API ────────────────────────────────────────────────────────────

    def scan_python(self, repo_path: str) -> ReachabilityResult:
        """
        Run pip-audit --format=json, parse CVEs, check reachability via AST import analysis.

        Gracefully degrades if pip-audit is not installed (scan_error set, empty result).
        """
        repo = Path(repo_path).resolve()
        audit_data = self._run_pip_audit(repo)
        if audit_data is None:
            return ReachabilityResult([], [], [], 0.0, scan_error="pip-audit unavailable or failed")

        pkg_to_files = self._collect_python_imports(repo)
        findings = self._parse_pip_audit(audit_data, pkg_to_files)
        return self._build_result(findings)

    def scan_javascript(self, repo_path: str) -> ReachabilityResult:
        """
        Run npm audit --json, parse CVEs, check reachability via require/import regex scan.

        Gracefully degrades if npm is not available or package.json is absent.
        """
        repo = Path(repo_path).resolve()
        audit_data = self._run_npm_audit(repo)
        if audit_data is None:
            return ReachabilityResult([], [], [], 0.0, scan_error="npm audit unavailable or failed")

        pkg_to_files = self._collect_js_imports(repo)
        findings = self._parse_npm_audit(audit_data, pkg_to_files)
        return self._build_result(findings)

    # ── Audit runners ─────────────────────────────────────────────────────────

    def _run_pip_audit(self, repo: Path) -> Optional[Dict[str, Any]]:
        # Only attempt if the repo has Python dependency files
        has_py_deps = any(
            (repo / f).exists()
            for f in ("requirements.txt", "setup.py", "setup.cfg", "pyproject.toml", "Pipfile.lock")
        )
        if not has_py_deps:
            return None

        # Build the command — target requirements.txt if present for better results
        cmd = ["pip-audit", "--format=json", "--no-deps"]
        req_txt = repo / "requirements.txt"
        if req_txt.exists():
            cmd.extend(["-r", str(req_txt)])

        try:
            proc = subprocess.run(
                cmd, capture_output=True, text=True, timeout=120, cwd=repo,
            )
            text = proc.stdout.strip()
            return json.loads(text) if text else None
        except FileNotFoundError:
            return None
        except (subprocess.TimeoutExpired, json.JSONDecodeError):
            return None

    def _run_npm_audit(self, repo: Path) -> Optional[Dict[str, Any]]:
        # Only run if package.json AND a lock file exist (npm audit needs a lock file)
        if not (repo / "package.json").exists():
            return None
        has_lock = (repo / "package-lock.json").exists() or (repo / "yarn.lock").exists()
        if not has_lock:
            # Try to generate a package-lock.json so npm audit can work
            try:
                subprocess.run(
                    ["npm", "install", "--package-lock-only", "--ignore-scripts"],
                    capture_output=True, timeout=120, cwd=repo,
                )
            except (FileNotFoundError, subprocess.TimeoutExpired):
                return None
        try:
            proc = subprocess.run(
                ["npm", "audit", "--json"],
                capture_output=True, text=True, timeout=120, cwd=repo,
            )
            # npm audit exits non-zero when vulnerabilities are found; stdout is still valid JSON
            text = proc.stdout.strip()
            return json.loads(text) if text else None
        except FileNotFoundError:
            return None
        except (subprocess.TimeoutExpired, json.JSONDecodeError):
            return None

    # ── Import extraction ─────────────────────────────────────────────────────

    def _extract_imports(self, file_path: Path) -> Set[str]:
        """AST-walk a Python file; return top-level package names of all import statements."""
        try:
            source = file_path.read_text(errors="replace")
            tree = ast.parse(source, filename=str(file_path))
        except (SyntaxError, OSError, ValueError):
            return set()

        packages: Set[str] = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    packages.add(alias.name.split(".")[0])
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    packages.add(node.module.split(".")[0])
        return packages

    def _collect_python_imports(self, repo: Path) -> Dict[str, Set[str]]:
        """
        Walk all .py files in the repo (skipping common non-source dirs).
        Returns {normalized_package_name: {file_path, ...}}.
        Package names are normalized: lowercased, hyphens→underscores.
        """
        pkg_to_files: Dict[str, Set[str]] = {}
        for py_file in repo.rglob("*.py"):
            if any(part in _SKIP_DIRS for part in py_file.parts):
                continue
            for pkg in self._extract_imports(py_file):
                norm = pkg.lower().replace("-", "_")
                pkg_to_files.setdefault(norm, set()).add(str(py_file.relative_to(repo)))
        return pkg_to_files

    def _collect_js_imports(self, repo: Path) -> Dict[str, Set[str]]:
        """
        Regex-scan .js/.ts/.jsx/.tsx/.mjs for require() and ES import statements.
        Returns {package_name: {file_path, ...}}.
        """
        pkg_to_files: Dict[str, Set[str]] = {}
        # Matches: require('foo'), require("foo"), from 'foo', from "foo"
        # Captures: the package name (possibly scoped like @scope/pkg)
        pattern = re.compile(
            r"""(?:require\s*\(\s*['"]|(?:^|[\s;{])from\s+['"])(@?[a-zA-Z0-9_.-]+(?:/[a-zA-Z0-9_.-]+)?)""",
            re.MULTILINE,
        )
        extensions = {".js", ".ts", ".jsx", ".tsx", ".mjs"}
        for js_file in repo.rglob("*"):
            if js_file.suffix not in extensions:
                continue
            if any(part in _SKIP_DIRS for part in js_file.parts):
                continue
            try:
                text = js_file.read_text(errors="replace")
            except OSError:
                continue
            for m in pattern.finditer(text):
                raw = m.group(1)
                # Scoped packages: @scope/pkg → normalize to scope/pkg for matching
                pkg = raw.split("/")[0].lstrip("@").lower()
                pkg_to_files.setdefault(pkg, set()).add(str(js_file.relative_to(repo)))
        return pkg_to_files

    # ── CVE parsing ───────────────────────────────────────────────────────────

    def _parse_pip_audit(
        self, data: Dict[str, Any], pkg_to_files: Dict[str, Set[str]]
    ) -> List[CVEFinding]:
        """
        pip-audit JSON format:
        {"dependencies": [{"name": "requests", "version": "2.27.0",
           "vulns": [{"id": "CVE-...", "fix_versions": [...], "description": "..."}]}]}
        """
        findings: List[CVEFinding] = []
        for dep in data.get("dependencies", []):
            raw_name = dep.get("name", "")
            norm = raw_name.lower().replace("-", "_")
            version = dep.get("version", "unknown")
            files = sorted(pkg_to_files.get(norm, set()))
            for vuln in dep.get("vulns", []):
                fix_versions = vuln.get("fix_versions", [])
                cve_id = vuln.get("id", "UNKNOWN")
                desc = vuln.get("description", "")
                severity = self._infer_severity_from_description(cve_id, desc)
                findings.append(CVEFinding(
                    package=raw_name,
                    cve_id=cve_id,
                    severity=severity,
                    fixed_version=fix_versions[0] if fix_versions else "no-fix",
                    vulnerable_version=version,
                    description=desc[:300],
                    reachable=len(files) > 0,
                    reachable_via=files[:10],  # cap at 10 files
                ))
        return findings

    def _parse_npm_audit(
        self, data: Dict[str, Any], pkg_to_files: Dict[str, Set[str]]
    ) -> List[CVEFinding]:
        """
        npm audit --json format (npm v7+):
        {"vulnerabilities": {"package_name": {"severity": "...", "via": [...],
           "fixAvailable": ..., "range": "..."}}}
        """
        findings: List[CVEFinding] = []
        for pkg_name, details in data.get("vulnerabilities", {}).items():
            severity = details.get("severity", "low")
            via = details.get("via", [])
            fix_info = details.get("fixAvailable", {})

            # Extract CVE IDs and descriptions from nested "via" entries
            cve_ids: List[str] = []
            descriptions: List[str] = []
            for v in via:
                if isinstance(v, dict):
                    url = v.get("url", "")
                    source = url.split("/")[-1] if url else v.get("source", "")
                    if source:
                        cve_ids.append(source)
                    title = v.get("title", "")
                    if title:
                        descriptions.append(title)

            norm = pkg_name.lower().replace("-", "_")
            files = sorted(pkg_to_files.get(norm, set()))
            findings.append(CVEFinding(
                package=pkg_name,
                cve_id=", ".join(cve_ids) if cve_ids else "UNKNOWN",
                severity=severity,
                fixed_version=(
                    fix_info.get("version", "no-fix")
                    if isinstance(fix_info, dict)
                    else "no-fix"
                ),
                vulnerable_version=details.get("range", "unknown"),
                description="; ".join(descriptions)[:300],
                reachable=len(files) > 0,
                reachable_via=files[:10],
            ))
        return findings

    # ── Severity inference ────────────────────────────────────────────────────

    def _infer_severity_from_description(self, cve_id: str, description: str) -> str:
        """Heuristic severity for pip-audit output that lacks an explicit severity field."""
        desc_lower = description.lower()
        if any(kw in desc_lower for kw in ("remote code execution", "arbitrary code", "rce")):
            return "critical"
        if any(kw in desc_lower for kw in ("sql injection", "denial of service", "ssrf", "path traversal")):
            return "high"
        if any(kw in desc_lower for kw in ("xss", "cross-site scripting", "open redirect", "csrf")):
            return "moderate"
        return "low"

    # ── Result builder ────────────────────────────────────────────────────────

    def _build_result(self, findings: List[CVEFinding]) -> ReachabilityResult:
        reachable = [f for f in findings if f.reachable]
        unreachable = [f for f in findings if not f.reachable]

        if reachable:
            weights = [self._SEVERITY_WEIGHTS.get(f.severity, 0.1) for f in reachable]
            risk_score = min(1.0, sum(weights) / len(weights))
        else:
            risk_score = 0.0

        return ReachabilityResult(
            cves=findings,
            reachable_cves=reachable,
            unreachable_cves=unreachable,
            risk_score=round(risk_score, 4),
        )
