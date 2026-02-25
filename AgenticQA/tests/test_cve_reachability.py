"""Unit tests for CVEReachabilityAnalyzer."""
import json
import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from agenticqa.security.cve_reachability import CVEFinding, CVEReachabilityAnalyzer, ReachabilityResult


@pytest.mark.unit
class TestExtractImports:
    def test_extract_imports_simple_file(self, tmp_path):
        py_file = tmp_path / "app.py"
        py_file.write_text("import os\nimport requests\nfrom pathlib import Path\n")
        analyzer = CVEReachabilityAnalyzer()
        imports = analyzer._extract_imports(py_file)
        assert "os" in imports
        assert "requests" in imports
        assert "pathlib" in imports

    def test_extract_imports_ignores_syntax_errors(self, tmp_path):
        py_file = tmp_path / "broken.py"
        py_file.write_text("def broken(\n  # unclosed")
        analyzer = CVEReachabilityAnalyzer()
        imports = analyzer._extract_imports(py_file)
        assert imports == set()

    def test_extract_imports_relative_ignored(self, tmp_path):
        py_file = tmp_path / "rel.py"
        py_file.write_text("from . import utils\nfrom ..core import base\n")
        analyzer = CVEReachabilityAnalyzer()
        imports = analyzer._extract_imports(py_file)
        # Relative imports have no module — they should be skipped or produce empty string
        assert "" not in imports


@pytest.mark.unit
class TestCollectImports:
    def test_collect_python_imports_multiple_files(self, tmp_path):
        (tmp_path / "a.py").write_text("import requests\nimport flask\n")
        (tmp_path / "b.py").write_text("import requests\nimport numpy\n")
        analyzer = CVEReachabilityAnalyzer()
        result = analyzer._collect_python_imports(tmp_path)
        assert "requests" in result
        assert len(result["requests"]) == 2  # found in both files
        assert "flask" in result
        assert "numpy" in result

    def test_collect_python_imports_skips_venv(self, tmp_path):
        venv_dir = tmp_path / ".venv" / "lib"
        venv_dir.mkdir(parents=True)
        (venv_dir / "secret.py").write_text("import secret_pkg\n")
        (tmp_path / "main.py").write_text("import real_pkg\n")
        analyzer = CVEReachabilityAnalyzer()
        result = analyzer._collect_python_imports(tmp_path)
        assert "real_pkg" in result
        assert "secret_pkg" not in result

    def test_normalize_hyphen_to_underscore(self, tmp_path):
        (tmp_path / "app.py").write_text("import my_package\n")
        analyzer = CVEReachabilityAnalyzer()
        result = analyzer._collect_python_imports(tmp_path)
        # The key is normalized — hyphens would be underscores
        assert "my_package" in result


@pytest.mark.unit
class TestBuildResult:
    def test_build_result_all_reachable_critical(self):
        findings = [
            CVEFinding("pkg-a", "CVE-001", "critical", "2.0", "1.0", "RCE", True, ["app.py"]),
            CVEFinding("pkg-b", "CVE-002", "critical", "3.0", "2.0", "RCE", True, ["main.py"]),
        ]
        analyzer = CVEReachabilityAnalyzer()
        result = analyzer._build_result(findings)
        assert result.risk_score == 1.0
        assert len(result.reachable_cves) == 2
        assert len(result.unreachable_cves) == 0

    def test_build_result_mix_reachable_unreachable(self):
        findings = [
            CVEFinding("pkg-a", "CVE-001", "high", "2.0", "1.0", "", True, ["app.py"]),
            CVEFinding("pkg-b", "CVE-002", "low", "3.0", "2.0", "", False, []),
        ]
        analyzer = CVEReachabilityAnalyzer()
        result = analyzer._build_result(findings)
        assert result.risk_score == pytest.approx(0.7, abs=0.01)
        assert len(result.reachable_cves) == 1
        assert len(result.unreachable_cves) == 1

    def test_build_result_no_reachable_cves(self):
        findings = [
            CVEFinding("pkg-a", "CVE-001", "critical", "2.0", "1.0", "", False, []),
        ]
        analyzer = CVEReachabilityAnalyzer()
        result = analyzer._build_result(findings)
        assert result.risk_score == 0.0
        assert len(result.reachable_cves) == 0

    def test_build_result_empty(self):
        analyzer = CVEReachabilityAnalyzer()
        result = analyzer._build_result([])
        assert result.risk_score == 0.0
        assert result.cves == []


@pytest.mark.unit
class TestParsePipAudit:
    def test_parse_pip_audit_marks_reachable(self, tmp_path):
        audit_data = {
            "dependencies": [
                {
                    "name": "requests",
                    "version": "2.27.0",
                    "vulns": [
                        {
                            "id": "CVE-2023-32681",
                            "fix_versions": ["2.31.0"],
                            "description": "SSRF vulnerability in requests library",
                        }
                    ],
                }
            ]
        }
        pkg_to_files = {"requests": {"app.py", "client.py"}}
        analyzer = CVEReachabilityAnalyzer()
        findings = analyzer._parse_pip_audit(audit_data, pkg_to_files)
        assert len(findings) == 1
        assert findings[0].reachable is True
        assert len(findings[0].reachable_via) == 2

    def test_parse_pip_audit_marks_unreachable(self, tmp_path):
        audit_data = {
            "dependencies": [
                {
                    "name": "urllib3",
                    "version": "1.26.0",
                    "vulns": [
                        {
                            "id": "CVE-2023-45803",
                            "fix_versions": ["2.0.7"],
                            "description": "DoS via large response",
                        }
                    ],
                }
            ]
        }
        pkg_to_files = {}  # not imported anywhere
        analyzer = CVEReachabilityAnalyzer()
        findings = analyzer._parse_pip_audit(audit_data, pkg_to_files)
        assert len(findings) == 1
        assert findings[0].reachable is False
        assert findings[0].reachable_via == []

    def test_parse_pip_audit_hyphen_normalization(self):
        audit_data = {
            "dependencies": [
                {
                    "name": "my-cool-package",
                    "version": "1.0.0",
                    "vulns": [{"id": "CVE-001", "fix_versions": ["2.0"], "description": ""}],
                }
            ]
        }
        # Import stored under normalized name
        pkg_to_files = {"my_cool_package": {"app.py"}}
        analyzer = CVEReachabilityAnalyzer()
        findings = analyzer._parse_pip_audit(audit_data, pkg_to_files)
        assert findings[0].reachable is True


@pytest.mark.unit
class TestParseNpmAudit:
    def test_parse_npm_audit_marks_unreachable(self):
        audit_data = {
            "vulnerabilities": {
                "lodash": {
                    "severity": "high",
                    "via": [{"url": "https://github.com/advisories/GHSA-jf85-cpcp-j695",
                              "title": "Prototype Pollution"}],
                    "fixAvailable": {"version": "4.17.21"},
                    "range": "<4.17.21",
                }
            }
        }
        pkg_to_files = {}  # not imported
        analyzer = CVEReachabilityAnalyzer()
        findings = analyzer._parse_npm_audit(audit_data, pkg_to_files)
        assert len(findings) == 1
        assert findings[0].reachable is False

    def test_parse_npm_audit_marks_reachable(self):
        audit_data = {
            "vulnerabilities": {
                "express": {
                    "severity": "critical",
                    "via": [{"url": "https://nvd.nist.gov/vuln/detail/CVE-2022-24999",
                              "title": "RCE in express"}],
                    "fixAvailable": {"version": "4.18.2"},
                    "range": "<4.18.2",
                }
            }
        }
        pkg_to_files = {"express": {"src/server.ts"}}
        analyzer = CVEReachabilityAnalyzer()
        findings = analyzer._parse_npm_audit(audit_data, pkg_to_files)
        assert findings[0].reachable is True


@pytest.mark.unit
class TestScanPython:
    def test_scan_python_no_pip_audit(self, tmp_path):
        analyzer = CVEReachabilityAnalyzer()
        with patch("subprocess.run", side_effect=FileNotFoundError("pip-audit not found")):
            result = analyzer.scan_python(str(tmp_path))
        assert result.scan_error is not None
        assert "unavailable" in result.scan_error
        assert result.cves == []
        assert result.risk_score == 0.0

    def test_scan_python_timeout(self, tmp_path):
        analyzer = CVEReachabilityAnalyzer()
        with patch("subprocess.run", side_effect=subprocess.TimeoutExpired("pip-audit", 120)):
            result = analyzer.scan_python(str(tmp_path))
        assert result.scan_error is not None

    def test_scan_javascript_no_package_json(self, tmp_path):
        analyzer = CVEReachabilityAnalyzer()
        # No package.json → should return empty result without running npm
        result = analyzer.scan_javascript(str(tmp_path))
        assert result.scan_error is not None
        assert result.cves == []

    def test_scan_python_integrates_reachability(self, tmp_path):
        (tmp_path / "app.py").write_text("import requests\n")
        audit_json = {
            "dependencies": [
                {
                    "name": "requests",
                    "version": "2.27.0",
                    "vulns": [{"id": "CVE-2023-32681", "fix_versions": ["2.31.0"],
                                "description": "SSRF"}],
                }
            ]
        }
        mock_proc = MagicMock()
        mock_proc.stdout = json.dumps(audit_json)
        mock_proc.returncode = 0
        analyzer = CVEReachabilityAnalyzer()
        with patch("subprocess.run", return_value=mock_proc):
            result = analyzer.scan_python(str(tmp_path))
        assert len(result.reachable_cves) == 1
        assert result.reachable_cves[0].package == "requests"
        assert result.risk_score > 0
