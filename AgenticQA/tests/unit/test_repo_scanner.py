"""Unit tests for RepoScanner — real pre-execution repo scanning."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# Allow import from src/ without install
# ---------------------------------------------------------------------------
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from agenticqa.repo_profile import RepoProfile
from agenticqa.repo_scanner import (
    RepoScanner,
    RepoScanResults,
    _parse_flake8_output,
    _parse_pytest_stdout,
)

pytestmark = pytest.mark.unit


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_profile(primary="python", languages=None, test_runner_hints=None):
    return RepoProfile(
        repo_root="/fake",
        primary_language=primary,
        languages=languages or [primary],
        package_managers=["pip"] if primary == "python" else ["npm"],
        ci_provider="none",
        test_runner_hints=test_runner_hints or (["pytest"] if primary == "python" else ["npm_test"]),
        has_tests_dir=True,
    )


def _ok_proc(stdout="", returncode=0):
    m = MagicMock()
    m.stdout = stdout
    m.stderr = ""
    m.returncode = returncode
    return m


# ---------------------------------------------------------------------------
# 1. PII scan — detects email
# ---------------------------------------------------------------------------

def test_pii_scan_detects_email(tmp_path):
    (tmp_path / "app.py").write_text("user_email = 'john.doe@example.com'\n")
    scanner = RepoScanner()
    result = scanner._scan_pii_secrets(tmp_path)
    assert result.has_pii is True
    assert any(f["type"] == "email" for f in result.pii_findings)


# ---------------------------------------------------------------------------
# 2. PII scan — detects AWS key
# ---------------------------------------------------------------------------

def test_pii_scan_detects_aws_key(tmp_path):
    (tmp_path / "config.py").write_text("AWS_KEY = 'AKIAIOSFODNN7EXAMPLE'\n")
    scanner = RepoScanner()
    result = scanner._scan_pii_secrets(tmp_path)
    assert result.has_pii is True
    assert result.has_secrets is True
    assert any(f["type"] == "aws_access_key" for f in result.pii_findings)


# ---------------------------------------------------------------------------
# 3. PII scan — clean file
# ---------------------------------------------------------------------------

def test_pii_scan_clean_file(tmp_path):
    (tmp_path / "utils.py").write_text("def add(a, b):\n    return a + b\n")
    scanner = RepoScanner()
    result = scanner._scan_pii_secrets(tmp_path)
    assert result.has_pii is False
    assert result.pii_findings == []


# ---------------------------------------------------------------------------
# 4. PII scan — skips .git directory
# ---------------------------------------------------------------------------

def test_pii_scan_skips_git_dir(tmp_path):
    git_dir = tmp_path / ".git" / "config"
    git_dir.parent.mkdir()
    git_dir.write_text("email = admin@secret.com\n")
    scanner = RepoScanner()
    result = scanner._scan_pii_secrets(tmp_path)
    assert result.has_pii is False


# ---------------------------------------------------------------------------
# 5. Linting — parses flake8 output correctly
# ---------------------------------------------------------------------------

def test_linting_python_parses_flake8_output(tmp_path):
    flake8_stdout = (
        "src/foo.py:10:1: E302 expected 2 blank lines, found 1\n"
        "src/bar.py:5:80: W503 line break before binary operator\n"
    )
    profile = _make_profile("python")
    with patch("subprocess.run", return_value=_ok_proc(stdout=flake8_stdout, returncode=1)):
        scanner = RepoScanner()
        result = scanner._run_linting(tmp_path, profile)

    assert result.available is True
    assert result.tool_used == "flake8"
    assert len(result.errors) == 2
    assert result.errors[0]["rule"] == "E302"
    assert result.errors[0]["line"] == 10
    assert result.errors[1]["rule"] == "W503"
    assert result.errors[1]["severity"] == "warning"


# ---------------------------------------------------------------------------
# 6. Linting — unavailable when subprocess raises
# ---------------------------------------------------------------------------

def test_linting_unavailable_when_subprocess_fails(tmp_path):
    profile = _make_profile("python")
    with patch("subprocess.run", side_effect=FileNotFoundError("flake8 not found")):
        scanner = RepoScanner()
        result = scanner._run_linting(tmp_path, profile)

    assert result.available is False
    assert result.tool_used == "flake8"
    assert result.errors == []


# ---------------------------------------------------------------------------
# 7. Tests — parses pytest + coverage output
# ---------------------------------------------------------------------------

def test_tests_parses_pytest_output(tmp_path):
    pytest_stdout = "1 failed, 5 passed in 3.14s\n"
    coverage_json = {
        "totals": {"percent_covered": 72.5},
        "files": {
            str(tmp_path / "src" / "a.py"): {"summary": {"percent_covered": 50.0}},
        },
    }

    cov_json_path = tmp_path / "cov.json"
    cov_json_path.write_text(json.dumps(coverage_json))

    def fake_run(args, **kwargs):
        proc = MagicMock()
        proc.returncode = 0
        args_list = list(args)
        if "pytest" in args_list and "coverage" in args_list:
            proc.stdout = pytest_stdout
            proc.stderr = ""
        elif "json" in args_list and "coverage" in args_list:
            # coverage json -o /path/to/file — find path after "-o"
            out_path = None
            for i, arg in enumerate(args_list):
                if arg == "-o" and i + 1 < len(args_list):
                    out_path = Path(args_list[i + 1])
                    break
            if out_path:
                out_path.parent.mkdir(parents=True, exist_ok=True)
                out_path.write_text(json.dumps(coverage_json))
            proc.stdout = ""
            proc.stderr = ""
        else:
            proc.stdout = "pytest 7.0"
            proc.stderr = ""
        return proc

    profile = _make_profile("python")
    with patch("subprocess.run", side_effect=fake_run):
        scanner = RepoScanner()
        result = scanner._run_tests_with_coverage(tmp_path, profile)

    assert result.available is True
    assert result.tool_used == "pytest+coverage"
    assert result.passed == 5
    assert result.failed == 1
    assert result.total == 6
    assert result.coverage_percent == 72.5
    assert result.duration_ms > 0


# ---------------------------------------------------------------------------
# 8. Tests — unavailable when pytest missing
# ---------------------------------------------------------------------------

def test_tests_unavailable_when_no_test_runner(tmp_path):
    profile = _make_profile("python")
    probe_fail = MagicMock()
    probe_fail.returncode = 1
    probe_fail.stdout = ""
    probe_fail.stderr = ""
    with patch("subprocess.run", return_value=probe_fail):
        scanner = RepoScanner()
        result = scanner._run_tests_with_coverage(tmp_path, profile)

    assert result.available is False


# ---------------------------------------------------------------------------
# 9. to_metadata_patch — PII found → pii_masked=False
# ---------------------------------------------------------------------------

def test_to_metadata_patch_sets_pii_masked(tmp_path):
    (tmp_path / "app.py").write_text("admin = 'admin@corp.com'\n")
    scanner = RepoScanner()
    profile = _make_profile("python")
    pii = scanner._scan_pii_secrets(tmp_path)

    from agenticqa.repo_scanner import LintResult, PerformanceBenchmarkResult, TestCoverageResult
    results = RepoScanResults(
        pii=pii,
        linting=LintResult(available=False, tool_used="none"),
        tests=TestCoverageResult(available=False, tool_used="none"),
        performance=PerformanceBenchmarkResult(available=False, tool_used="none"),
    )
    patch_dict = results.to_metadata_patch()
    assert patch_dict["pii_masked"] is False


# ---------------------------------------------------------------------------
# 10. to_metadata_patch — no PII → pii_masked=True
# ---------------------------------------------------------------------------

def test_to_metadata_patch_no_pii(tmp_path):
    (tmp_path / "app.py").write_text("def greet(): return 'hello'\n")
    scanner = RepoScanner()
    pii = scanner._scan_pii_secrets(tmp_path)

    from agenticqa.repo_scanner import LintResult, PerformanceBenchmarkResult, TestCoverageResult
    results = RepoScanResults(
        pii=pii,
        linting=LintResult(available=False, tool_used="none"),
        tests=TestCoverageResult(available=False, tool_used="none"),
        performance=PerformanceBenchmarkResult(available=False, tool_used="none"),
    )
    patch_dict = results.to_metadata_patch()
    assert patch_dict["pii_masked"] is True


# ---------------------------------------------------------------------------
# 11. Performance — stores and loads baseline
# ---------------------------------------------------------------------------

def test_performance_stores_and_loads_baseline(tmp_path):
    from agenticqa.repo_scanner import TestCoverageResult

    tests = TestCoverageResult(
        available=True, tool_used="pytest+coverage",
        passed=10, failed=0, total=10,
        coverage_percent=90.0, uncovered_files=[],
        duration_ms=1234.5,
    )
    scanner = RepoScanner()
    # First run: no baseline
    result1 = scanner._benchmark_performance(tmp_path, tests)
    assert result1.available is True
    assert result1.baseline_ms is None
    assert result1.duration_ms == 1234.5

    # Second run: baseline should be loaded from first run
    result2 = scanner._benchmark_performance(tmp_path, tests)
    assert result2.baseline_ms == 1234.5


# ---------------------------------------------------------------------------
# 12. Integration — full scan on a real tmp repo
# ---------------------------------------------------------------------------

def test_scan_full_integration(tmp_path):
    # A tiny Python repo with one source file
    (tmp_path / "mymodule.py").write_text(
        "SECRET_KEY = 'AKIAIOSFODNN7EXAMPLE'\n"
        "def compute(x):\n    return x * 2\n"
    )
    (tmp_path / "pyproject.toml").write_text("[tool.pytest.ini_options]\n")

    profile = _make_profile("python")
    scanner = RepoScanner()

    # Only the PII scan runs for real; linting+tests are skipped via mocking
    with patch.object(scanner, "_run_linting") as mock_lint, \
         patch.object(scanner, "_run_tests_with_coverage") as mock_tests:

        from agenticqa.repo_scanner import LintResult, TestCoverageResult
        mock_lint.return_value = LintResult(available=False, tool_used="flake8")
        mock_tests.return_value = TestCoverageResult(available=False, tool_used="pytest+coverage")

        results = scanner.scan(tmp_path, profile)

    assert results.pii.has_pii is True
    assert results.pii.has_secrets is True
    assert results.pii.files_scanned >= 1
    patch_dict = results.to_metadata_patch()
    assert patch_dict["pii_masked"] is False
    assert patch_dict.get("encrypted") is False  # aws key found → secrets present


# ---------------------------------------------------------------------------
# Parse helpers (standalone)
# ---------------------------------------------------------------------------

def test_parse_flake8_output_basic():
    output = "myfile.py:3:1: E302 expected 2 blank lines\nmyfile.py:10:5: W291 trailing whitespace\n"
    errors = _parse_flake8_output(output, Path("/repo"))
    assert len(errors) == 2
    assert errors[0]["rule"] == "E302"
    assert errors[0]["severity"] == "error"
    assert errors[1]["severity"] == "warning"


def test_parse_pytest_stdout_passed_and_failed():
    output = "3 failed, 12 passed in 5.23s"
    passed, failed, total = _parse_pytest_stdout(output)
    assert passed == 12
    assert failed == 3
    assert total == 15


def test_parse_pytest_stdout_all_passed():
    output = "7 passed in 1.01s"
    passed, failed, total = _parse_pytest_stdout(output)
    assert passed == 7
    assert failed == 0
    assert total == 7
