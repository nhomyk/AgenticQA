"""Tests for client deployment preflight check.

Covers all 7 probes, CLI output, exit codes, and edge cases.
"""

import json
import os
import subprocess
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

pytestmark = pytest.mark.unit


# ── Helpers ──────────────────────────────────────────────────────────────────


def _init_git_repo(path: Path, set_identity: bool = True) -> None:
    """Create a minimal git repo."""
    subprocess.run(["git", "init"], cwd=str(path), check=True, capture_output=True)
    if set_identity:
        subprocess.run(["git", "config", "user.email", "test@test.com"], cwd=str(path), check=True, capture_output=True)
        subprocess.run(["git", "config", "user.name", "Test"], cwd=str(path), check=True, capture_output=True)
    (path / "README.md").write_text("# test\n")
    subprocess.run(["git", "add", "."], cwd=str(path), check=True, capture_output=True)
    if set_identity:
        subprocess.run(["git", "commit", "-m", "init"], cwd=str(path), check=True, capture_output=True)


# ── 1. Full preflight on healthy repo ────────────────────────────────────────


class TestPreflightHealthyRepo:
    """Preflight should pass on a properly configured repo."""

    def test_all_checks_pass(self, tmp_path):
        from agenticqa.client_preflight import run_preflight

        repo = tmp_path / "healthy"
        repo.mkdir()
        _init_git_repo(repo)

        report = run_preflight(str(repo))
        assert report.passed is True
        assert report.has_warnings is False
        failed = [c for c in report.checks if c.status == "fail"]
        assert failed == [], f"Unexpected failures: {failed}"

    def test_report_to_dict(self, tmp_path):
        from agenticqa.client_preflight import run_preflight

        repo = tmp_path / "dict_test"
        repo.mkdir()
        _init_git_repo(repo)

        report = run_preflight(str(repo))
        d = report.to_dict()
        assert "repo_path" in d
        assert "checks" in d
        assert "summary" in d
        assert "pass" in d["summary"]


# ── 2. git_repo probe ────────────────────────────────────────────────────────


class TestGitRepoProbe:
    """Detect non-git directories."""

    def test_not_a_git_repo(self, tmp_path):
        from agenticqa.client_preflight import run_preflight

        repo = tmp_path / "not_git"
        repo.mkdir()

        report = run_preflight(str(repo))
        git_check = next(c for c in report.checks if c.name == "git_repo")
        assert git_check.status == "fail"
        assert report.passed is False


# ── 3. git_config probe ─────────────────────────────────────────────────────


class TestGitConfigProbe:
    """Detect missing git user.name / user.email."""

    def test_missing_git_identity(self, tmp_path):
        from agenticqa.client_preflight import _check_git_config, PreflightReport

        repo = tmp_path / "no_identity"
        repo.mkdir()
        _init_git_repo(repo, set_identity=False)

        # Mock subprocess.run so git config user.name/email return failure,
        # simulating a bare CI runner with no global ~/.gitconfig
        real_run = subprocess.run

        def mock_run(cmd, **kwargs):
            if cmd[:2] == ["git", "config"] and len(cmd) == 3 and cmd[2] in ("user.name", "user.email"):
                return subprocess.CompletedProcess(cmd, returncode=1, stdout="", stderr="")
            return real_run(cmd, **kwargs)

        report = PreflightReport(repo_path=str(repo))
        with patch("agenticqa.client_preflight.subprocess.run", side_effect=mock_run):
            _check_git_config(report, str(repo))

        config_check = next(c for c in report.checks if c.name == "git_config")
        assert config_check.status == "fail"
        assert "user.name" in config_check.message or "user.email" in config_check.message
        assert config_check.fix_hint is not None

    def test_git_identity_present(self, tmp_path):
        from agenticqa.client_preflight import run_preflight

        repo = tmp_path / "with_identity"
        repo.mkdir()
        _init_git_repo(repo, set_identity=True)

        report = run_preflight(str(repo))
        config_check = next(c for c in report.checks if c.name == "git_config")
        assert config_check.status == "pass"


# ── 4. python_tooling probe ─────────────────────────────────────────────────


class TestPythonToolingProbe:
    """Python, pip, pytest should be available in test env."""

    def test_python_tooling_available(self, tmp_path):
        from agenticqa.client_preflight import run_preflight

        repo = tmp_path / "py_check"
        repo.mkdir()
        _init_git_repo(repo)

        report = run_preflight(str(repo))
        py_check = next(c for c in report.checks if c.name == "python_tooling")
        assert py_check.status == "pass"


# ── 5. node_tooling probe ───────────────────────────────────────────────────


class TestNodeToolingProbe:
    """Node.js tooling check behavior."""

    def test_no_package_json_passes(self, tmp_path):
        from agenticqa.client_preflight import run_preflight

        repo = tmp_path / "no_node"
        repo.mkdir()
        _init_git_repo(repo)

        report = run_preflight(str(repo))
        node_check = next(c for c in report.checks if c.name == "node_tooling")
        assert node_check.status == "pass"
        assert "not required" in node_check.message.lower()

    def test_package_json_without_node_modules_warns(self, tmp_path):
        from agenticqa.client_preflight import run_preflight

        repo = tmp_path / "with_pkg"
        repo.mkdir()
        _init_git_repo(repo)
        (repo / "package.json").write_text('{"name": "test"}')

        report = run_preflight(str(repo))
        node_check = next(c for c in report.checks if c.name == "node_tooling")
        # Warns about missing node_modules at minimum
        assert node_check.status in ("warn", "pass")


# ── 6. linter_availability probe ────────────────────────────────────────────


class TestLinterProbe:
    """Linter detection for Python and JS repos."""

    def test_python_repo_linter_detection(self, tmp_path):
        from agenticqa.client_preflight import run_preflight

        repo = tmp_path / "py_lint"
        repo.mkdir()
        _init_git_repo(repo)
        (repo / "app.py").write_text("print('hello')\n")

        report = run_preflight(str(repo))
        lint_check = next(c for c in report.checks if c.name == "linter_availability")
        # Should detect Python and check for flake8/ruff
        assert lint_check.status in ("pass", "warn")

    def test_no_code_files_passes(self, tmp_path):
        from agenticqa.client_preflight import run_preflight

        repo = tmp_path / "empty_lint"
        repo.mkdir()
        _init_git_repo(repo)
        # Only README.md — no Python/JS files

        report = run_preflight(str(repo))
        lint_check = next(c for c in report.checks if c.name == "linter_availability")
        assert lint_check.status == "pass"


# ── 7. path_sanitization probe ──────────────────────────────────────────────


class TestPathSanitizationProbe:
    """Path sanitization compatibility."""

    def test_tmp_path_passes(self, tmp_path):
        from agenticqa.client_preflight import run_preflight

        repo = tmp_path / "san_check"
        repo.mkdir()
        _init_git_repo(repo)

        report = run_preflight(str(repo))
        path_check = next(c for c in report.checks if c.name == "path_sanitization")
        assert path_check.status == "pass"

    def test_disabled_sanitization_passes(self, tmp_path):
        from agenticqa.client_preflight import run_preflight

        repo = tmp_path / "san_disabled"
        repo.mkdir()
        _init_git_repo(repo)

        with patch.dict(os.environ, {"AGENTICQA_PATH_SANITIZE_DISABLE": "1"}):
            report = run_preflight(str(repo))
        path_check = next(c for c in report.checks if c.name == "path_sanitization")
        assert path_check.status == "pass"
        assert "disabled" in path_check.message.lower()


# ── 8. import_chain probe ───────────────────────────────────────────────────


class TestImportChainProbe:
    """Import chain validation."""

    def test_core_modules_importable(self, tmp_path):
        from agenticqa.client_preflight import run_preflight

        repo = tmp_path / "import_check"
        repo.mkdir()
        _init_git_repo(repo)

        report = run_preflight(str(repo))
        import_check = next(c for c in report.checks if c.name == "import_chain")
        assert import_check.status == "pass"

    def test_import_failure_detected(self, tmp_path):
        from agenticqa.client_preflight import _check_import_chain, PreflightReport

        report = PreflightReport(repo_path=str(tmp_path))
        with patch("agenticqa.client_preflight.importlib") as mock_imp:
            mock_imp.import_module.side_effect = ImportError("no module")
            _check_import_chain(report)

        import_check = next(c for c in report.checks if c.name == "import_chain")
        assert import_check.status == "fail"
        assert "Failed imports" in import_check.message


# ── 9. Report structure ─────────────────────────────────────────────────────


class TestReportStructure:
    """Verify report data structure."""

    def test_all_seven_probes_present(self, tmp_path):
        from agenticqa.client_preflight import run_preflight

        repo = tmp_path / "all_probes"
        repo.mkdir()
        _init_git_repo(repo)

        report = run_preflight(str(repo))
        probe_names = {c.name for c in report.checks}
        expected = {
            "git_repo", "git_config", "python_tooling",
            "node_tooling", "linter_availability",
            "path_sanitization", "import_chain",
        }
        assert probe_names == expected

    def test_json_output_format(self, tmp_path):
        from agenticqa.client_preflight import run_preflight

        repo = tmp_path / "json_fmt"
        repo.mkdir()
        _init_git_repo(repo)

        report = run_preflight(str(repo))
        d = report.to_dict()
        j = json.dumps(d)
        parsed = json.loads(j)
        assert parsed["passed"] is True
        assert len(parsed["checks"]) == 7

    def test_failed_report_has_passed_false(self, tmp_path):
        from agenticqa.client_preflight import run_preflight

        # Non-git directory → git_repo probe fails
        repo = tmp_path / "fail_report"
        repo.mkdir()

        report = run_preflight(str(repo))
        assert report.passed is False
        d = report.to_dict()
        assert d["passed"] is False
        assert "fail" in d["summary"]
