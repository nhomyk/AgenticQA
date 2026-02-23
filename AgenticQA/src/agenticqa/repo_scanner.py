"""Real pre-execution scanning of client repos before agents are invoked.

Runs actual tools (PII regex, flake8/ESLint, pytest+coverage, timing) against the
repo filesystem and feeds true findings into agent input dicts rather than trusting
metadata flags.
"""

from __future__ import annotations

import hashlib
import json
import re
import subprocess
import sys
import tempfile
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

try:
    from .repo_profile import RepoProfile
except ImportError:
    from repo_profile import RepoProfile  # type: ignore


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_SKIP_DIRS = {
    ".git", "node_modules", "__pycache__", ".pytest_cache",
    "venv", ".venv", "dist", "build", ".next", ".tox",
    "coverage", ".mypy_cache", ".ruff_cache", "htmlcov",
}

_SKIP_EXTENSIONS = {
    ".pyc", ".pyo", ".class", ".jar", ".war", ".exe", ".dll",
    ".so", ".dylib", ".png", ".jpg", ".jpeg", ".gif", ".svg",
    ".ico", ".woff", ".woff2", ".ttf", ".otf", ".eot",
    ".pdf", ".zip", ".tar", ".gz", ".bz2", ".xz", ".7z",
    ".lock",  # lockfiles are large/binary-like and rarely contain user PII
}

_MAX_FILE_SIZE = 500_000   # 500 KB
_MAX_FILES = 1_000

_PII_PATTERNS: Dict[str, str] = {
    "email": r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}",
    "ssn": r"\b\d{3}-\d{2}-\d{4}\b",
    "credit_card": r"\b\d{4}[\s\-]?\d{4}[\s\-]?\d{4}[\s\-]?\d{4}\b",
    "private_key": r"-----BEGIN (?:RSA |EC |DSA |OPENSSH )?PRIVATE KEY-----",
    "aws_access_key": r"\bAKIA[0-9A-Z]{16}\b",
    "generic_secret": (
        r"(?i)(?:password|secret|api[_\-]?key|auth[_\-]?token)\s*[=:]\s*"
        r"['\"]?[a-zA-Z0-9_\-\.\/+]{8,}['\"]?"
    ),
}

# Compiled once at module load
_COMPILED_PII = {name: re.compile(pattern) for name, pattern in _PII_PATTERNS.items()}

_LINT_EXCLUDE = "venv,.venv,node_modules,__pycache__,dist,build,.tox,.next"


# ---------------------------------------------------------------------------
# Result dataclasses
# ---------------------------------------------------------------------------

@dataclass
class PiiScanResult:
    has_pii: bool
    has_secrets: bool  # private keys or AWS keys
    pii_findings: List[Dict[str, Any]] = field(default_factory=list)
    files_scanned: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "has_pii": self.has_pii,
            "has_secrets": self.has_secrets,
            "pii_findings": self.pii_findings,
            "files_scanned": self.files_scanned,
        }


@dataclass
class LintResult:
    available: bool
    tool_used: str  # "flake8", "eslint", "none"
    errors: List[Dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "available": self.available,
            "tool_used": self.tool_used,
            "errors": self.errors,
        }


@dataclass
class TestCoverageResult:
    available: bool
    tool_used: str  # "pytest+coverage", "npm_test", "none"
    passed: int = 0
    failed: int = 0
    total: int = 0
    coverage_percent: float = 0.0
    uncovered_files: List[str] = field(default_factory=list)
    duration_ms: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "available": self.available,
            "tool_used": self.tool_used,
            "passed": self.passed,
            "failed": self.failed,
            "total": self.total,
            "coverage_percent": self.coverage_percent,
            "uncovered_files": self.uncovered_files,
            "duration_ms": self.duration_ms,
        }


@dataclass
class PerformanceBenchmarkResult:
    available: bool
    tool_used: str  # "test_suite_timing", "none"
    duration_ms: float = 0.0
    baseline_ms: Optional[float] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "available": self.available,
            "tool_used": self.tool_used,
            "duration_ms": self.duration_ms,
            "baseline_ms": self.baseline_ms,
        }


@dataclass
class RepoScanResults:
    pii: PiiScanResult
    linting: LintResult
    tests: TestCoverageResult
    performance: PerformanceBenchmarkResult

    def to_metadata_patch(self) -> Dict[str, Any]:
        """Keys to merge into req['metadata'] so downstream agents get real data.

        The PromptOpsOrchestrator reads these exact keys when building agent payloads:
        - compliance: pii_masked, encrypted
        - sdet: coverage_percent, uncovered_files
        """
        patch: Dict[str, Any] = {}

        # Compliance: set based on real scan findings
        patch["pii_masked"] = not self.pii.has_pii
        if self.pii.has_secrets:
            patch["encrypted"] = False   # found unencrypted credentials

        # SDET: real coverage numbers
        if self.tests.available:
            patch["coverage_percent"] = self.tests.coverage_percent
            patch["uncovered_files"] = self.tests.uncovered_files

        return patch

    def to_dict(self) -> Dict[str, Any]:
        return {
            "pii": self.pii.to_dict(),
            "linting": self.linting.to_dict(),
            "tests": self.tests.to_dict(),
            "performance": self.performance.to_dict(),
        }


# ---------------------------------------------------------------------------
# Scanner
# ---------------------------------------------------------------------------

class RepoScanner:
    """Runs real tool-based scans against a local repo path."""

    def scan(self, repo_path: Path, profile: RepoProfile) -> RepoScanResults:
        pii = self._scan_pii_secrets(repo_path)
        linting = self._run_linting(repo_path, profile)
        tests = self._run_tests_with_coverage(repo_path, profile)
        performance = self._benchmark_performance(repo_path, tests)
        return RepoScanResults(
            pii=pii,
            linting=linting,
            tests=tests,
            performance=performance,
        )

    # ------------------------------------------------------------------
    # 1. PII / Secrets scanning
    # ------------------------------------------------------------------

    def _scan_pii_secrets(self, repo_path: Path) -> PiiScanResult:
        findings: List[Dict[str, Any]] = []
        files_scanned = 0
        secret_types = {"private_key", "aws_access_key"}

        for file_path in self._iter_text_files(repo_path):
            if files_scanned >= _MAX_FILES:
                break
            try:
                text = file_path.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue

            files_scanned += 1
            rel = str(file_path.relative_to(repo_path))

            for line_no, line in enumerate(text.splitlines(), start=1):
                for pii_type, pattern in _COMPILED_PII.items():
                    match = pattern.search(line)
                    if match:
                        snippet = line.strip()[:120]
                        findings.append({
                            "file": rel,
                            "line": line_no,
                            "type": pii_type,
                            "snippet": snippet,
                        })

        has_pii = bool(findings)
        has_secrets = any(f["type"] in secret_types for f in findings)
        return PiiScanResult(
            has_pii=has_pii,
            has_secrets=has_secrets,
            pii_findings=findings,
            files_scanned=files_scanned,
        )

    def _iter_text_files(self, repo_path: Path):
        """Yield text files under repo_path, respecting skip rules."""
        for item in repo_path.rglob("*"):
            if not item.is_file():
                continue
            # Skip if any parent component is a skip dir
            try:
                parts = item.relative_to(repo_path).parts
            except ValueError:
                continue
            if any(p in _SKIP_DIRS for p in parts):
                continue
            if item.suffix.lower() in _SKIP_EXTENSIONS:
                continue
            try:
                if item.stat().st_size > _MAX_FILE_SIZE:
                    continue
            except OSError:
                continue
            yield item

    # ------------------------------------------------------------------
    # 2. Linting
    # ------------------------------------------------------------------

    def _run_linting(self, repo_path: Path, profile: RepoProfile) -> LintResult:
        if profile.primary_language == "python":
            return self._run_flake8(repo_path)
        if profile.primary_language == "javascript":
            return self._run_eslint(repo_path)
        return LintResult(available=False, tool_used="none")

    def _run_flake8(self, repo_path: Path) -> LintResult:
        try:
            result = subprocess.run(
                [
                    sys.executable, "-m", "flake8", ".",
                    "--format=default",
                    f"--max-line-length=120",
                    f"--exclude={_LINT_EXCLUDE}",
                ],
                cwd=str(repo_path),
                capture_output=True,
                text=True,
                timeout=60,
            )
        except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
            return LintResult(available=False, tool_used="flake8")

        # flake8 exits 1 when there are errors — that is expected
        errors = _parse_flake8_output(result.stdout + result.stderr, repo_path)
        return LintResult(available=True, tool_used="flake8", errors=errors)

    def _run_eslint(self, repo_path: Path) -> LintResult:
        eslint_bin = repo_path / "node_modules" / ".bin" / "eslint"
        if not eslint_bin.exists():
            return LintResult(available=False, tool_used="eslint")
        try:
            result = subprocess.run(
                [str(eslint_bin), "--format", "json", "."],
                cwd=str(repo_path),
                capture_output=True,
                text=True,
                timeout=60,
            )
        except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
            return LintResult(available=False, tool_used="eslint")

        try:
            data = json.loads(result.stdout)
            errors = _parse_eslint_json(data, repo_path)
        except (json.JSONDecodeError, Exception):
            errors = []

        return LintResult(available=True, tool_used="eslint", errors=errors)

    # ------------------------------------------------------------------
    # 3. Test suite + coverage
    # ------------------------------------------------------------------

    def _run_tests_with_coverage(self, repo_path: Path, profile: RepoProfile) -> TestCoverageResult:
        if profile.primary_language == "python":
            return self._run_pytest_coverage(repo_path)
        if profile.primary_language == "javascript":
            return self._run_npm_test_coverage(repo_path, profile)
        return TestCoverageResult(available=False, tool_used="none")

    def _run_pytest_coverage(self, repo_path: Path) -> TestCoverageResult:
        # Check pytest is available
        try:
            probe = subprocess.run(
                [sys.executable, "-m", "pytest", "--version"],
                cwd=str(repo_path),
                capture_output=True,
                text=True,
                timeout=15,
            )
            if probe.returncode != 0:
                return TestCoverageResult(available=False, tool_used="pytest+coverage")
        except Exception:
            return TestCoverageResult(available=False, tool_used="pytest+coverage")

        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as tmp:
            coverage_json_path = Path(tmp.name)

        t0 = time.perf_counter()
        try:
            run_result = subprocess.run(
                [
                    sys.executable, "-m", "coverage", "run",
                    "-m", "pytest", "-q", "--tb=no", "--no-header",
                    f"--ignore={repo_path / '.agenticqa'}",
                ],
                cwd=str(repo_path),
                capture_output=True,
                text=True,
                timeout=180,
            )
        except subprocess.TimeoutExpired:
            return TestCoverageResult(available=False, tool_used="pytest+coverage")
        except Exception:
            return TestCoverageResult(available=False, tool_used="pytest+coverage")

        duration_ms = (time.perf_counter() - t0) * 1000

        passed, failed, total = _parse_pytest_stdout(run_result.stdout + run_result.stderr)

        # Generate coverage JSON
        coverage_percent = 0.0
        uncovered_files: List[str] = []
        try:
            subprocess.run(
                [sys.executable, "-m", "coverage", "json", "-o", str(coverage_json_path)],
                cwd=str(repo_path),
                capture_output=True,
                text=True,
                timeout=30,
            )
            if coverage_json_path.exists():
                cov_data = json.loads(coverage_json_path.read_text())
                totals = cov_data.get("totals", {})
                coverage_percent = float(totals.get("percent_covered", 0.0))
                uncovered_files = _extract_uncovered_files(cov_data, repo_path)
        except Exception:
            pass
        finally:
            try:
                coverage_json_path.unlink(missing_ok=True)
            except Exception:
                pass

        return TestCoverageResult(
            available=True,
            tool_used="pytest+coverage",
            passed=passed,
            failed=failed,
            total=total,
            coverage_percent=round(coverage_percent, 2),
            uncovered_files=uncovered_files,
            duration_ms=round(duration_ms, 1),
        )

    def _run_npm_test_coverage(self, repo_path: Path, profile: RepoProfile) -> TestCoverageResult:
        if "npm_test" not in profile.test_runner_hints:
            return TestCoverageResult(available=False, tool_used="npm_test")

        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as tmp:
            output_file = Path(tmp.name)

        t0 = time.perf_counter()
        try:
            result = subprocess.run(
                [
                    "npm", "test", "--",
                    "--coverage", "--watchAll=false",
                    "--json", f"--outputFile={output_file}",
                ],
                cwd=str(repo_path),
                capture_output=True,
                text=True,
                timeout=180,
            )
        except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
            return TestCoverageResult(available=False, tool_used="npm_test")
        finally:
            pass

        duration_ms = (time.perf_counter() - t0) * 1000

        passed = failed = total = 0
        coverage_percent = 0.0
        uncovered_files: List[str] = []

        try:
            if output_file.exists():
                jest_data = json.loads(output_file.read_text())
                passed = jest_data.get("numPassedTests", 0)
                failed = jest_data.get("numFailedTests", 0)
                total = jest_data.get("numTotalTests", 0)
                cov = jest_data.get("coverageMap") or {}
                if cov:
                    coverage_percent, uncovered_files = _parse_jest_coverage(cov, repo_path)
        except Exception:
            pass
        finally:
            try:
                output_file.unlink(missing_ok=True)
            except Exception:
                pass

        return TestCoverageResult(
            available=True,
            tool_used="npm_test",
            passed=passed,
            failed=failed,
            total=total,
            coverage_percent=round(coverage_percent, 2),
            uncovered_files=uncovered_files,
            duration_ms=round(duration_ms, 1),
        )

    # ------------------------------------------------------------------
    # 4. Performance benchmarking
    # ------------------------------------------------------------------

    def _benchmark_performance(
        self, repo_path: Path, tests: TestCoverageResult
    ) -> PerformanceBenchmarkResult:
        if not tests.available or tests.duration_ms == 0.0:
            return PerformanceBenchmarkResult(available=False, tool_used="none")

        duration_ms = tests.duration_ms
        baseline_ms = self._load_baseline(repo_path)
        self._save_baseline(repo_path, duration_ms)

        return PerformanceBenchmarkResult(
            available=True,
            tool_used="test_suite_timing",
            duration_ms=duration_ms,
            baseline_ms=baseline_ms,
        )

    def _baseline_path(self, repo_path: Path) -> Path:
        return repo_path / ".agenticqa" / "perf_baselines.json"

    def _repo_key(self, repo_path: Path) -> str:
        return hashlib.md5(str(repo_path).encode()).hexdigest()[:12]

    def _load_baseline(self, repo_path: Path) -> Optional[float]:
        try:
            data = json.loads(self._baseline_path(repo_path).read_text())
            value = data.get(self._repo_key(repo_path))
            return float(value) if value is not None else None
        except Exception:
            return None

    def _save_baseline(self, repo_path: Path, duration_ms: float) -> None:
        try:
            bp = self._baseline_path(repo_path)
            bp.parent.mkdir(parents=True, exist_ok=True)
            try:
                existing = json.loads(bp.read_text())
            except Exception:
                existing = {}
            existing[self._repo_key(repo_path)] = duration_ms
            bp.write_text(json.dumps(existing, indent=2))
        except Exception:
            pass


# ---------------------------------------------------------------------------
# Parse helpers
# ---------------------------------------------------------------------------

def _parse_flake8_output(output: str, repo_path: Path) -> List[Dict[str, Any]]:
    """Parse flake8 default format: path:line:col: CODE message"""
    errors = []
    pattern = re.compile(r"^(.+?):(\d+):(\d+):\s+([A-Z]\d+)\s+(.+)$")
    for line in output.splitlines():
        m = pattern.match(line.strip())
        if not m:
            continue
        file_path, lineno, _col, code, message = m.groups()
        try:
            rel = str(Path(file_path).relative_to(repo_path))
        except ValueError:
            rel = file_path
        severity = "error" if code.startswith("E") else "warning"
        errors.append({
            "rule": code,
            "message": message.strip(),
            "file_path": rel,
            "line": int(lineno),
            "severity": severity,
        })
    return errors


def _parse_eslint_json(data: Any, repo_path: Path) -> List[Dict[str, Any]]:
    """Parse ESLint JSON format into the SREAgent error dict shape."""
    errors = []
    if not isinstance(data, list):
        return errors
    for file_result in data:
        file_path = file_result.get("filePath", "")
        try:
            rel = str(Path(file_path).relative_to(repo_path))
        except ValueError:
            rel = file_path
        for msg in file_result.get("messages", []):
            severity = "error" if msg.get("severity") == 2 else "warning"
            errors.append({
                "rule": msg.get("ruleId") or "unknown",
                "message": msg.get("message", ""),
                "file_path": rel,
                "line": msg.get("line", 0),
                "severity": severity,
            })
    return errors


def _parse_pytest_stdout(output: str) -> tuple[int, int, int]:
    """Extract passed/failed/total from pytest -q output.

    Handles both orderings: "1 failed, 5 passed" and "5 passed, 1 failed".
    """
    passed = failed = 0
    failed_pat = re.compile(r"(\d+)\s+failed", re.IGNORECASE)
    passed_pat = re.compile(r"(\d+)\s+passed", re.IGNORECASE)
    for line in reversed(output.splitlines()):
        line = line.strip()
        if not line or ("passed" not in line.lower() and "failed" not in line.lower()):
            continue
        fm = failed_pat.search(line)
        pm = passed_pat.search(line)
        if fm or pm:
            failed = int(fm.group(1)) if fm else 0
            passed = int(pm.group(1)) if pm else 0
            break
    total = passed + failed
    return passed, failed, total


def _extract_uncovered_files(cov_data: Dict, repo_path: Path) -> List[str]:
    """Return list of files with < 100% line coverage."""
    uncovered = []
    for file_path, file_info in cov_data.get("files", {}).items():
        summary = file_info.get("summary", {})
        pct = summary.get("percent_covered", 100.0)
        if pct < 100.0:
            try:
                rel = str(Path(file_path).relative_to(repo_path))
            except ValueError:
                rel = file_path
            uncovered.append(rel)
    return uncovered


def _parse_jest_coverage(coverage_map: Dict, repo_path: Path) -> tuple[float, List[str]]:
    """Parse Jest coverageMap into (percent, uncovered_files)."""
    total_stmts = covered_stmts = 0
    uncovered: List[str] = []
    for file_path, cov in coverage_map.items():
        s = cov.get("s", {})
        stmt_count = len(s)
        covered = sum(1 for v in s.values() if v > 0)
        total_stmts += stmt_count
        covered_stmts += covered
        if stmt_count > 0 and covered < stmt_count:
            try:
                rel = str(Path(file_path).relative_to(repo_path))
            except ValueError:
                rel = file_path
            uncovered.append(rel)
    pct = (covered_stmts / total_stmts * 100) if total_stmts > 0 else 0.0
    return round(pct, 2), uncovered
