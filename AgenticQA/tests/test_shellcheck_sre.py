"""Unit tests for SREAgent shellcheck integration."""
import json
import subprocess
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from agents import SREAgent


# ---------------------------------------------------------------------------
# _run_shell_linter — no .sh files
# ---------------------------------------------------------------------------

@pytest.mark.unit
def test_run_shell_linter_no_sh_files(tmp_path):
    """Returns [] when no .sh files exist."""
    agent = SREAgent.__new__(SREAgent)
    agent._strategy_selector = None
    agent.log = MagicMock()
    result = agent._run_shell_linter(str(tmp_path))
    assert result == []


# ---------------------------------------------------------------------------
# _run_shell_linter — shellcheck not installed
# ---------------------------------------------------------------------------

@pytest.mark.unit
def test_run_shell_linter_no_shellcheck(tmp_path):
    """Returns [] gracefully when shellcheck is not installed."""
    (tmp_path / "deploy.sh").write_text("#!/bin/bash\necho $VAR\n")
    agent = SREAgent.__new__(SREAgent)
    agent._strategy_selector = None
    agent.log = MagicMock()
    with patch("subprocess.run", side_effect=FileNotFoundError):
        result = agent._run_shell_linter(str(tmp_path))
    assert result == []


# ---------------------------------------------------------------------------
# _run_shell_linter — shellcheck timeout
# ---------------------------------------------------------------------------

@pytest.mark.unit
def test_run_shell_linter_timeout(tmp_path):
    """Returns [] gracefully on timeout."""
    (tmp_path / "slow.sh").write_text("#!/bin/bash\necho hi\n")
    agent = SREAgent.__new__(SREAgent)
    agent._strategy_selector = None
    agent.log = MagicMock()
    with patch("subprocess.run", side_effect=subprocess.TimeoutExpired("shellcheck", 60)):
        result = agent._run_shell_linter(str(tmp_path))
    assert result == []


# ---------------------------------------------------------------------------
# _run_shell_linter — parses shellcheck JSON output
# ---------------------------------------------------------------------------

@pytest.mark.unit
def test_run_shell_linter_parses_output(tmp_path):
    """Correctly parses shellcheck JSON into normalized error dicts."""
    (tmp_path / "test.sh").write_text("#!/bin/bash\necho $UNQUOTED\n")
    agent = SREAgent.__new__(SREAgent)
    agent._strategy_selector = None
    agent.log = MagicMock()

    shellcheck_json = json.dumps([
        {
            "file": str(tmp_path / "test.sh"),
            "line": 2,
            "endLine": 2,
            "column": 6,
            "endColumn": 14,
            "level": "warning",
            "code": 2086,
            "message": "Double quote to prevent globbing and word splitting.",
            "fix": None,
        }
    ])
    mock_result = MagicMock()
    mock_result.stdout = shellcheck_json
    mock_result.returncode = 1

    with patch("subprocess.run", return_value=mock_result):
        errors = agent._run_shell_linter(str(tmp_path))

    assert len(errors) == 1
    assert errors[0]["rule"] == "SC2086"
    assert errors[0]["line"] == 2
    assert errors[0]["col"] == 6
    assert "globbing" in errors[0]["message"]


# ---------------------------------------------------------------------------
# _run_shell_linter — multiple files
# ---------------------------------------------------------------------------

@pytest.mark.unit
def test_run_shell_linter_multiple_files(tmp_path):
    """Aggregates findings from multiple shell files."""
    (tmp_path / "a.sh").write_text("#!/bin/bash\necho $A\n")
    (tmp_path / "b.sh").write_text("#!/bin/bash\necho $B\n")
    agent = SREAgent.__new__(SREAgent)
    agent._strategy_selector = None
    agent.log = MagicMock()

    shellcheck_json = json.dumps([
        {"file": str(tmp_path / "a.sh"), "line": 2, "column": 6,
         "level": "warning", "code": 2086, "message": "SC2086 on a.sh"},
        {"file": str(tmp_path / "b.sh"), "line": 2, "column": 6,
         "level": "warning", "code": 2086, "message": "SC2086 on b.sh"},
    ])
    mock = MagicMock()
    mock.stdout = shellcheck_json
    with patch("subprocess.run", return_value=mock):
        errors = agent._run_shell_linter(str(tmp_path))

    assert len(errors) == 2
    files = {e["file"] for e in errors}
    assert any("a.sh" in f for f in files)
    assert any("b.sh" in f for f in files)


# ---------------------------------------------------------------------------
# execute() — shell_errors in result
# ---------------------------------------------------------------------------

@pytest.mark.unit
def test_execute_includes_shell_errors(tmp_path):
    """execute() populates shell_errors and shell_error_count in result."""
    (tmp_path / "run.sh").write_text("#!/bin/bash\necho $X\n")
    agent = SREAgent.__new__(SREAgent)
    agent._strategy_selector = None
    agent.agent_name = "SRE_Agent"
    agent.use_data_store = False
    agent.use_rag = False
    agent.rag = None
    agent.pattern_analyzer = None
    agent.repo_profile = None
    agent.agent_registry = None
    agent._delegation_depth = 0
    agent._record_execution = MagicMock()
    agent.log = MagicMock()

    shell_findings = [{"rule": "SC2086", "file": "run.sh", "line": 2,
                       "col": 6, "message": "quote vars", "severity": "warning"}]

    with patch.object(agent, "_augment_with_rag",
                      return_value={"rag_insights_count": 0, "rag_recommendations": []}), \
         patch.object(agent, "_get_execution_strategy",
                      return_value={"known_failure_types": []}), \
         patch.object(agent, "_run_shell_linter", return_value=shell_findings):
        result = agent.execute({"errors": [], "repo_path": str(tmp_path)})

    assert result["shell_error_count"] == 1
    assert result["shell_errors"][0]["rule"] == "SC2086"


# ---------------------------------------------------------------------------
# SC architectural rules excluded correctly
# ---------------------------------------------------------------------------

@pytest.mark.unit
def test_sc_architectural_rules_in_frozenset():
    """SC2046 and SC2206 are in ARCHITECTURAL_RULES."""
    assert "SC2046" in SREAgent.ARCHITECTURAL_RULES
    assert "SC2206" in SREAgent.ARCHITECTURAL_RULES


@pytest.mark.unit
def test_sc_security_frozenset():
    """SC2086 is in _SC_SECURITY."""
    assert "SC2086" in SREAgent._SC_SECURITY
