"""Client deployment preflight check for AgenticQA.

Validates that a target repository environment has all the tooling,
configuration, and import chain availability needed for successful
workflow execution.

Usage:
    python -m agenticqa.client_preflight [--repo PATH] [--json] [--fail-on-warning]
"""

from __future__ import annotations

import importlib
import json
import os
import shutil
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional


@dataclass
class PreflightCheck:
    name: str
    status: str  # "pass", "fail", "warn"
    message: str
    fix_hint: Optional[str] = None


@dataclass
class PreflightReport:
    repo_path: str
    checks: List[PreflightCheck] = field(default_factory=list)
    passed: bool = True
    has_warnings: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "repo_path": self.repo_path,
            "passed": self.passed,
            "has_warnings": self.has_warnings,
            "checks": [
                {
                    "name": c.name,
                    "status": c.status,
                    "message": c.message,
                    "fix_hint": c.fix_hint,
                }
                for c in self.checks
            ],
            "summary": (
                f"{sum(1 for c in self.checks if c.status == 'pass')} pass, "
                f"{sum(1 for c in self.checks if c.status == 'warn')} warn, "
                f"{sum(1 for c in self.checks if c.status == 'fail')} fail"
            ),
        }


def run_preflight(repo_path: str = ".") -> PreflightReport:
    """Run all preflight checks against a target repo."""
    resolved = str(Path(repo_path).expanduser().resolve())
    report = PreflightReport(repo_path=resolved)

    _check_git_repo(report, resolved)
    _check_git_config(report, resolved)
    _check_python_tooling(report)
    _check_node_tooling(report, resolved)
    _check_linter_availability(report, resolved)
    _check_path_sanitization(report, resolved)
    _check_import_chain(report)

    report.passed = all(c.status != "fail" for c in report.checks)
    report.has_warnings = any(c.status == "warn" for c in report.checks)
    return report


# ── Probe implementations ───────────────────────────────────────────────────


def _check_git_repo(report: PreflightReport, repo_path: str) -> None:
    """Verify the target path is a git repository."""
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--is-inside-work-tree"],
            cwd=repo_path,
            capture_output=True,
            text=True,
            timeout=10,
        )
        if result.returncode == 0 and result.stdout.strip() == "true":
            report.checks.append(PreflightCheck(
                name="git_repo",
                status="pass",
                message="Valid git repository",
            ))
        else:
            report.checks.append(PreflightCheck(
                name="git_repo",
                status="fail",
                message="Not a git repository",
                fix_hint="Run 'git init' in the target directory",
            ))
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        report.checks.append(PreflightCheck(
            name="git_repo",
            status="fail",
            message="git command not available or timed out",
            fix_hint="Install git: https://git-scm.com/downloads",
        ))


def _check_git_config(report: PreflightReport, repo_path: str) -> None:
    """Verify git user.name and user.email are configured."""
    missing = []
    for key in ("user.name", "user.email"):
        try:
            result = subprocess.run(
                ["git", "config", key],
                cwd=repo_path,
                capture_output=True,
                text=True,
                timeout=10,
            )
            if result.returncode != 0 or not result.stdout.strip():
                missing.append(key)
        except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
            missing.append(key)

    if not missing:
        report.checks.append(PreflightCheck(
            name="git_config",
            status="pass",
            message="git user.name and user.email configured",
        ))
    else:
        report.checks.append(PreflightCheck(
            name="git_config",
            status="fail",
            message=f"Missing git config: {', '.join(missing)}",
            fix_hint=(
                "git config --local user.name 'AgenticQA Bot' && "
                "git config --local user.email 'agenticqa-bot@users.noreply.github.com'"
            ),
        ))


def _check_python_tooling(report: PreflightReport) -> None:
    """Verify Python, pip, and pytest are available."""
    issues = []

    if not sys.executable:
        issues.append("Python executable not found")

    if not shutil.which("pip") and not shutil.which("pip3"):
        issues.append("pip not found")

    if not shutil.which("pytest"):
        # Also try python -m pytest
        try:
            result = subprocess.run(
                [sys.executable, "-m", "pytest", "--version"],
                capture_output=True,
                text=True,
                timeout=10,
            )
            if result.returncode != 0:
                issues.append("pytest not found")
        except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
            issues.append("pytest not found")

    if not issues:
        report.checks.append(PreflightCheck(
            name="python_tooling",
            status="pass",
            message="Python, pip, and pytest available",
        ))
    else:
        report.checks.append(PreflightCheck(
            name="python_tooling",
            status="fail",
            message=f"Missing: {', '.join(issues)}",
            fix_hint="pip install pytest",
        ))


def _check_node_tooling(report: PreflightReport, repo_path: str) -> None:
    """If package.json exists, verify node/npm are available."""
    package_json = Path(repo_path) / "package.json"
    if not package_json.exists():
        report.checks.append(PreflightCheck(
            name="node_tooling",
            status="pass",
            message="No package.json — Node.js not required",
        ))
        return

    issues = []
    if not shutil.which("node"):
        issues.append("node not found")
    if not shutil.which("npm") and not shutil.which("yarn") and not shutil.which("pnpm"):
        issues.append("npm/yarn/pnpm not found")
    if not (Path(repo_path) / "node_modules").exists():
        issues.append("node_modules missing (run npm install)")

    if not issues:
        report.checks.append(PreflightCheck(
            name="node_tooling",
            status="pass",
            message="Node.js tooling available",
        ))
    else:
        report.checks.append(PreflightCheck(
            name="node_tooling",
            status="warn",
            message=f"Node.js issues: {', '.join(issues)}",
            fix_hint="Install Node.js and run 'npm install'",
        ))


def _check_linter_availability(report: PreflightReport, repo_path: str) -> None:
    """Check for language-appropriate linters."""
    repo = Path(repo_path)
    has_python = any(repo.glob("**/*.py"))
    has_js = (repo / "package.json").exists() or any(repo.glob("**/*.js")) or any(repo.glob("**/*.ts"))

    available = []
    missing = []

    if has_python:
        if shutil.which("flake8"):
            available.append("flake8")
        elif shutil.which("ruff"):
            available.append("ruff")
        else:
            missing.append("flake8 or ruff (Python)")

    if has_js:
        if shutil.which("eslint") or shutil.which("oxlint"):
            available.append("eslint/oxlint")
        else:
            missing.append("eslint or oxlint (JavaScript/TypeScript)")

    if shutil.which("shellcheck"):
        available.append("shellcheck")

    if not missing:
        report.checks.append(PreflightCheck(
            name="linter_availability",
            status="pass",
            message=f"Linters available: {', '.join(available) or 'none needed'}",
        ))
    else:
        report.checks.append(PreflightCheck(
            name="linter_availability",
            status="warn",
            message=f"Missing linters: {', '.join(missing)}",
            fix_hint="pip install flake8 (Python) or npm install -g eslint (JS/TS)",
        ))


def _check_path_sanitization(report: PreflightReport, repo_path: str) -> None:
    """Verify the repo path passes AgenticQA path sanitization."""
    if os.environ.get("AGENTICQA_PATH_SANITIZE_DISABLE") == "1":
        report.checks.append(PreflightCheck(
            name="path_sanitization",
            status="pass",
            message="Path sanitization disabled via AGENTICQA_PATH_SANITIZE_DISABLE=1",
        ))
        return

    try:
        from agenticqa.security.path_sanitizer import sanitize_repo_path
        sanitize_repo_path(repo_path)
        report.checks.append(PreflightCheck(
            name="path_sanitization",
            status="pass",
            message="Repo path passes sanitization",
        ))
    except ValueError as e:
        report.checks.append(PreflightCheck(
            name="path_sanitization",
            status="fail",
            message=f"Path rejected: {e}",
            fix_hint=(
                f"Set AGENTICQA_ALLOWED_ROOTS={repo_path} or "
                "AGENTICQA_PATH_SANITIZE_DISABLE=1"
            ),
        ))
    except ImportError:
        report.checks.append(PreflightCheck(
            name="path_sanitization",
            status="warn",
            message="Could not import path_sanitizer — skipping check",
        ))


def _check_import_chain(report: PreflightReport) -> None:
    """Verify key AgenticQA modules can be imported."""
    modules = [
        "agenticqa.workflow_requests",
        "agenticqa.worker_pool",
        "agenticqa.workflow_worker",
    ]
    failed = []
    for mod in modules:
        try:
            importlib.import_module(mod)
        except Exception as e:
            failed.append(f"{mod} ({type(e).__name__})")

    if not failed:
        report.checks.append(PreflightCheck(
            name="import_chain",
            status="pass",
            message="All core AgenticQA modules importable",
        ))
    else:
        report.checks.append(PreflightCheck(
            name="import_chain",
            status="fail",
            message=f"Failed imports: {', '.join(failed)}",
            fix_hint='pip install "agenticqa @ git+https://github.com/nhomyk/AgenticQA.git#subdirectory=AgenticQA"',
        ))


# ── CLI entrypoint ───────────────────────────────────────────────────────────


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description="AgenticQA client preflight check")
    parser.add_argument("--repo", default=".", help="Repository path to check")
    parser.add_argument("--json", action="store_true", dest="json_output", help="Output JSON")
    parser.add_argument("--fail-on-warning", action="store_true")
    args = parser.parse_args()

    report = run_preflight(args.repo)

    if args.json_output:
        print(json.dumps(report.to_dict(), indent=2))
    else:
        print(f"AgenticQA Preflight Check: {report.repo_path}\n")
        for check in report.checks:
            icon = {"pass": "OK  ", "warn": "WARN", "fail": "FAIL"}[check.status]
            print(f"  [{icon}] {check.name}: {check.message}")
            if check.fix_hint:
                print(f"          Fix: {check.fix_hint}")
        print(f"\n  {report.to_dict()['summary']}")

    exit_code = 0
    if not report.passed:
        exit_code = 1
    elif args.fail_on_warning and report.has_warnings:
        exit_code = 2
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
