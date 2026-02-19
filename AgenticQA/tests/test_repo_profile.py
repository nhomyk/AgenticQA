"""Tests for repository profiling and generated-test command resolution."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

from agenticqa.repo_profile import detect_repo_profile, resolve_generated_test_command


def test_detect_repo_profile_python_repo(tmp_path: Path):
    (tmp_path / "pyproject.toml").write_text("[project]\nname='demo'\n", encoding="utf-8")
    (tmp_path / "pytest.ini").write_text("[pytest]\n", encoding="utf-8")
    (tmp_path / ".github" / "workflows").mkdir(parents=True, exist_ok=True)

    profile = detect_repo_profile(tmp_path)

    assert profile.primary_language == "python"
    assert "python" in profile.languages
    assert "pip" in profile.package_managers
    assert profile.ci_provider == "github_actions"
    assert "pytest" in profile.test_runner_hints


def test_detect_repo_profile_node_repo(tmp_path: Path):
    package_json = {
        "name": "demo-node",
        "scripts": {"test": "jest"},
    }
    (tmp_path / "package.json").write_text(json.dumps(package_json), encoding="utf-8")

    profile = detect_repo_profile(tmp_path)

    assert profile.primary_language == "javascript"
    assert "javascript" in profile.languages
    assert "npm" in profile.package_managers
    assert "npm_test" in profile.test_runner_hints


def test_resolve_generated_test_command_handles_missing_pytest(tmp_path: Path):
    package_json = {
        "name": "demo-node",
        "scripts": {"test": "jest"},
    }
    (tmp_path / "package.json").write_text(json.dumps(package_json), encoding="utf-8")

    profile = detect_repo_profile(tmp_path)
    with patch("agenticqa.repo_profile.subprocess.run", side_effect=RuntimeError("pytest probe unavailable")):
        resolved = resolve_generated_test_command(
            repo_root=tmp_path,
            profile=profile,
            test_paths=[tmp_path / "tests" / "generated" / "test_demo.py"],
        )

    assert resolved["available"] is False
    assert resolved["reason"] in {
        "node_repo_without_pytest_generated_tests_skipped",
        "pytest_not_available",
    }
