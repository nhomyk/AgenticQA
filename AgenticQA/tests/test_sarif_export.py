"""Unit tests for SARIF 2.1.0 export."""
import json
import sys
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from agenticqa.export.sarif import SARIFExporter, _rule_level, _make_rule


# ---------------------------------------------------------------------------
# _rule_level helper
# ---------------------------------------------------------------------------

@pytest.mark.unit
@pytest.mark.parametrize("rule,severity,expected", [
    ("F401", "", "warning"),
    ("E501", "", "note"),
    ("SC2086", "warning", "warning"),
    ("B602", "error", "error"),
    ("UNKNOWN", "note", "note"),
    ("UNKNOWN", "", "warning"),  # default
])
def test_rule_level(rule, severity, expected):
    assert _rule_level(rule, severity) == expected


# ---------------------------------------------------------------------------
# _make_rule
# ---------------------------------------------------------------------------

@pytest.mark.unit
def test_make_rule_security_severity_for_sc2086():
    rule = _make_rule("SC2086", "double quote variable")
    assert rule["id"] == "SC2086"
    assert "security-severity" in rule.get("properties", {})
    assert float(rule["properties"]["security-severity"]) >= 4.0


@pytest.mark.unit
def test_make_rule_no_security_severity_for_e501():
    rule = _make_rule("E501", "line too long")
    assert "properties" not in rule or "security-severity" not in rule.get("properties", {})


# ---------------------------------------------------------------------------
# SARIFExporter.add_sre_result
# ---------------------------------------------------------------------------

@pytest.mark.unit
def test_add_sre_result_basic(tmp_path):
    exporter = SARIFExporter(repo_root=str(tmp_path))
    sre = {
        "fixes": [
            {"rule": "F401", "file": "src/foo.py", "line": 5, "fix_applied": "Removed unused import"},
        ],
        "architectural_violations_by_rule": {"F403": 2},
        "shell_errors": [],
    }
    n = exporter.add_sre_result(sre)
    assert n == 2  # 1 fix + 1 arch violation
    assert len(exporter._results) == 2
    assert "F401" in exporter._rules
    assert "F403" in exporter._rules


@pytest.mark.unit
def test_add_sre_result_shell_errors(tmp_path):
    exporter = SARIFExporter(repo_root=str(tmp_path))
    sre = {
        "fixes": [],
        "architectural_violations_by_rule": {},
        "shell_errors": [
            {"rule": "SC2086", "file": "deploy.sh", "line": 12, "col": 5,
             "message": "Double quote to prevent globbing", "severity": "warning"},
            {"rule": "SC2034", "file": "init.sh", "line": 3, "col": 1,
             "message": "Unused variable", "severity": "warning"},
        ],
    }
    n = exporter.add_sre_result(sre)
    assert n == 2
    assert "SC2086" in exporter._rules
    # SC2086 should have a help_uri pointing to shellcheck wiki
    assert "shellcheck.net" in exporter._rules["SC2086"].get("helpUri", "")


# ---------------------------------------------------------------------------
# SARIFExporter.add_compliance_result
# ---------------------------------------------------------------------------

@pytest.mark.unit
def test_add_compliance_violations(tmp_path):
    exporter = SARIFExporter(repo_root=str(tmp_path))
    comp = {
        "violations": [
            {"type": "missing_encryption", "description": "Data not encrypted at rest",
             "file": "config.py", "line": 10},
        ],
        "cve_findings": [],
    }
    n = exporter.add_compliance_result(comp)
    assert n == 1
    assert exporter._results[0]["ruleId"] == "missing_encryption"


@pytest.mark.unit
def test_add_cve_findings(tmp_path):
    exporter = SARIFExporter(repo_root=str(tmp_path))
    comp = {
        "violations": [],
        "cve_findings": [
            {
                "cve_id": "CVE-2024-1234",
                "package": "requests",
                "severity": "high",
                "reachable_via": ["src/api.py", "src/client.py"],
            }
        ],
    }
    n = exporter.add_compliance_result(comp)
    assert n == 1
    r = exporter._rules.get("reachable_cve", {})
    assert r.get("properties", {}).get("security-severity") == "9.0"
    assert "CVE-2024-1234" in exporter._results[0]["message"]["text"]


# ---------------------------------------------------------------------------
# SARIFExporter.add_redteam_result
# ---------------------------------------------------------------------------

@pytest.mark.unit
def test_add_redteam_bypass(tmp_path):
    exporter = SARIFExporter(repo_root=str(tmp_path))
    rt = {
        "bypass_details": [
            {"technique_id": "T1-002", "technique": "Unicode homoglyph",
             "description": "Scanner missed homoglyph substitution"},
        ],
        "scanner_weaknesses": ["Pattern X not detected"],
    }
    n = exporter.add_redteam_result(rt)
    assert n == 2
    rule_ids = list(exporter._rules.keys())
    assert "T1-002" in rule_ids
    assert "RT-SCANNER" in rule_ids


# ---------------------------------------------------------------------------
# to_dict schema compliance
# ---------------------------------------------------------------------------

@pytest.mark.unit
def test_sarif_schema_structure(tmp_path):
    exporter = SARIFExporter(repo_root=str(tmp_path))
    exporter.add_sre_result({
        "fixes": [{"rule": "E501", "file": "a.py", "line": 1, "fix_applied": "ok"}],
        "architectural_violations_by_rule": {},
        "shell_errors": [],
    })
    d = exporter.to_dict()
    assert d["version"] == "2.1.0"
    assert "$schema" in d
    runs = d["runs"]
    assert len(runs) == 1
    driver = runs[0]["tool"]["driver"]
    assert driver["name"] == "AgenticQA"
    assert len(driver["rules"]) >= 1
    assert len(runs[0]["results"]) >= 1
    # Must be JSON-serializable
    json.dumps(d)


# ---------------------------------------------------------------------------
# write() to disk
# ---------------------------------------------------------------------------

@pytest.mark.unit
def test_write_creates_file(tmp_path):
    exporter = SARIFExporter(repo_root=str(tmp_path))
    exporter.add_sre_result({
        "fixes": [{"rule": "W291", "file": "b.py", "line": 3, "fix_applied": "trailing ws"}],
        "architectural_violations_by_rule": {},
        "shell_errors": [],
    })
    out = str(tmp_path / "out.sarif")
    n = exporter.write(out)
    assert n == 1
    assert Path(out).exists()
    parsed = json.loads(Path(out).read_text())
    assert parsed["version"] == "2.1.0"


# ---------------------------------------------------------------------------
# relative path helper
# ---------------------------------------------------------------------------

@pytest.mark.unit
def test_rel_path_strips_repo_root(tmp_path):
    exporter = SARIFExporter(repo_root=str(tmp_path))
    abs_path = str(tmp_path / "src" / "foo.py")
    assert exporter._rel(abs_path) == "src/foo.py"


@pytest.mark.unit
def test_rel_path_outside_root(tmp_path):
    exporter = SARIFExporter(repo_root=str(tmp_path))
    result = exporter._rel("/completely/different/path.py")
    assert "completely/different/path.py" in result
