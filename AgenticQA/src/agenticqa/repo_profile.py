"""Repository profiling and command resolution utilities for portable workflow execution."""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional


@dataclass
class RepoProfile:
    repo_root: str
    primary_language: str
    languages: List[str]
    package_managers: List[str]
    ci_provider: str
    test_runner_hints: List[str]
    has_tests_dir: bool

    def to_dict(self) -> Dict[str, Any]:
        return {
            "repo_root": self.repo_root,
            "primary_language": self.primary_language,
            "languages": self.languages,
            "package_managers": self.package_managers,
            "ci_provider": self.ci_provider,
            "test_runner_hints": self.test_runner_hints,
            "has_tests_dir": self.has_tests_dir,
        }


def detect_repo_profile(repo_root: Path) -> RepoProfile:
    root = repo_root.resolve()

    has_pyproject = (root / "pyproject.toml").exists()
    has_requirements = (root / "requirements.txt").exists()
    has_package_json = (root / "package.json").exists()

    languages: List[str] = []
    if has_pyproject or has_requirements:
        languages.append("python")
    if has_package_json:
        languages.append("javascript")

    if not languages:
        # Lightweight heuristic from file extensions.
        has_py_files = any(root.glob("**/*.py"))
        has_js_files = any(root.glob("**/*.js")) or any(root.glob("**/*.ts"))
        if has_py_files:
            languages.append("python")
        if has_js_files:
            languages.append("javascript")

    if "python" in languages:
        primary = "python"
    elif "javascript" in languages:
        primary = "javascript"
    else:
        primary = "unknown"

    package_managers: List[str] = []
    if (root / "poetry.lock").exists():
        package_managers.append("poetry")
    if (root / "Pipfile").exists():
        package_managers.append("pipenv")
    if has_requirements or has_pyproject:
        package_managers.append("pip")

    if (root / "pnpm-lock.yaml").exists():
        package_managers.append("pnpm")
    if (root / "yarn.lock").exists():
        package_managers.append("yarn")
    if has_package_json:
        package_managers.append("npm")

    ci_provider = "none"
    if (root / ".github" / "workflows").exists():
        ci_provider = "github_actions"

    test_runner_hints: List[str] = []
    if (root / "pytest.ini").exists() or has_pyproject:
        test_runner_hints.append("pytest")

    if has_package_json:
        try:
            package_json = json.loads((root / "package.json").read_text(encoding="utf-8"))
            scripts = package_json.get("scripts") or {}
            if isinstance(scripts, dict) and scripts.get("test"):
                test_runner_hints.append("npm_test")
        except Exception:
            pass

    has_tests_dir = (root / "tests").exists() or (root / "test").exists()

    # Preserve insertion order while deduplicating.
    package_managers = list(dict.fromkeys(package_managers))
    test_runner_hints = list(dict.fromkeys(test_runner_hints))

    return RepoProfile(
        repo_root=str(root),
        primary_language=primary,
        languages=languages,
        package_managers=package_managers,
        ci_provider=ci_provider,
        test_runner_hints=test_runner_hints,
        has_tests_dir=has_tests_dir,
    )


def resolve_generated_test_command(
    repo_root: Path,
    profile: RepoProfile,
    test_paths: List[Path],
) -> Dict[str, Any]:
    """Resolve best-effort command for generated SDET tests with graceful fallback."""
    path_args = [str(p) for p in test_paths]

    # Preferred runner for generated tests in current system.
    try:
        probe = subprocess.run(
            [sys.executable, "-m", "pytest", "--version"],
            cwd=str(repo_root),
            capture_output=True,
            text=True,
            timeout=15,
        )
        if probe.returncode == 0:
            return {
                "available": True,
                "runner": "pytest",
                "command": [sys.executable, "-m", "pytest", "-q", *path_args],
                "reason": "pytest_available",
            }
    except Exception:
        pass

    # If repo is node-only, we skip generated python tests rather than hard-failing onboarding.
    if profile.primary_language == "javascript":
        npm = shutil.which("npm")
        if npm:
            return {
                "available": False,
                "runner": "npm_test",
                "command": None,
                "reason": "node_repo_without_pytest_generated_tests_skipped",
            }

    return {
        "available": False,
        "runner": "none",
        "command": None,
        "reason": "pytest_not_available",
    }
