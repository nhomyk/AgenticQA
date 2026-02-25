"""
Unit tests for TypeScript/oxlint SRE Agent support.

Tests cover:
- normalize_linting_input handles oxlint JSON (dict + flat-array forms)
- _run_typescript_linter returns empty list when no tools available
- _run_typescript_linter prefers oxlint, falls back to eslint
- TS architectural rules are excluded from fix_rate
- oxlint / unicorn rules appear in fix_map
"""
import json
import sys
import os
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from agents import SREAgent, normalize_linting_input


# ---------------------------------------------------------------------------
# normalize_linting_input — oxlint formats
# ---------------------------------------------------------------------------

@pytest.mark.unit
def test_normalize_oxlint_dict_format():
    """oxlint JSON: {"diagnostics": [...], "summary": {...}}"""
    raw = {
        "diagnostics": [
            {
                "severity": "error",
                "message": "Unexpected var",
                "filename": "src/index.ts",
                "rule_id": "no-var",
                "start": {"line": 5, "column": 3},
                "end": {"line": 5, "column": 10},
            }
        ],
        "summary": {"total": 1, "errors": 1, "warnings": 0, "duration_ms": 12},
    }
    result = normalize_linting_input(raw)
    assert len(result["errors"]) == 1
    e = result["errors"][0]
    assert e["rule"] == "no-var"
    assert e["file"] == "src/index.ts"
    assert e["line"] == 5
    assert e["col"] == 3


@pytest.mark.unit
def test_normalize_oxlint_flat_array():
    """oxlint flat-array diagnostic per entry."""
    raw = [
        {
            "filename": "src/foo.ts",
            "message": "Use === instead of ==",
            "rule_id": "eqeqeq",
            "severity": "warning",
            "start": {"line": 10, "column": 7},
            "end": {"line": 10, "column": 9},
        }
    ]
    # flat array is passed as {"results": raw}
    result = normalize_linting_input({"results": raw})
    assert len(result["errors"]) == 1
    assert result["errors"][0]["rule"] == "eqeqeq"
    assert result["errors"][0]["file"] == "src/foo.ts"


@pytest.mark.unit
def test_normalize_eslint_format_unchanged():
    """ESLint JSON format still works after oxlint additions."""
    raw = [
        {
            "filePath": "/app/src/bar.ts",
            "messages": [
                {"ruleId": "no-console", "severity": 1, "message": "Unexpected console", "line": 3},
            ],
        }
    ]
    result = normalize_linting_input(raw)
    assert len(result["errors"]) == 1
    assert result["errors"][0]["rule"] == "no-console"
    assert result["errors"][0]["file"] == "/app/src/bar.ts"


# ---------------------------------------------------------------------------
# _run_typescript_linter
# ---------------------------------------------------------------------------

@pytest.mark.unit
def test_run_typescript_linter_no_tools(tmp_path):
    """Returns empty list when neither oxlint nor eslint is available."""
    agent = SREAgent.__new__(SREAgent)
    agent._strategy_selector = None
    agent.log = MagicMock()

    with patch("subprocess.run", side_effect=FileNotFoundError):
        result = agent._run_typescript_linter(str(tmp_path))

    assert result == []


@pytest.mark.unit
def test_run_typescript_linter_prefers_oxlint(tmp_path):
    """Uses oxlint JSON output when available."""
    agent = SREAgent.__new__(SREAgent)
    agent._strategy_selector = None
    agent.log = MagicMock()

    oxlint_output = json.dumps({
        "diagnostics": [
            {
                "severity": "error",
                "message": "Unexpected var, use let/const",
                "filename": "src/a.ts",
                "rule_id": "no-var",
                "start": {"line": 2, "column": 1},
            }
        ],
        "summary": {"total": 1, "errors": 1, "warnings": 0, "duration_ms": 5},
    })

    mock_result = MagicMock()
    mock_result.stdout = oxlint_output
    mock_result.returncode = 1  # oxlint exits 1 when issues found

    # First call (oxlint local binary) succeeds
    with patch("subprocess.run", return_value=mock_result) as mock_sp:
        errors = agent._run_typescript_linter(str(tmp_path))

    assert len(errors) == 1
    assert errors[0]["rule"] == "no-var"
    assert errors[0]["file"] == "src/a.ts"
    # Should not have tried eslint
    assert mock_sp.call_count == 1


@pytest.mark.unit
def test_run_typescript_linter_falls_back_to_eslint(tmp_path):
    """Falls back to eslint when oxlint is not found."""
    agent = SREAgent.__new__(SREAgent)
    agent._strategy_selector = None
    agent.log = MagicMock()

    eslint_output = json.dumps([
        {
            "filePath": str(tmp_path / "src/b.ts"),
            "messages": [
                {"ruleId": "prefer-const", "severity": 2, "message": "use const", "line": 5},
            ],
        }
    ])

    def side_effect(cmd, **kwargs):
        if "oxlint" in str(cmd):
            raise FileNotFoundError
        r = MagicMock()
        r.stdout = eslint_output
        r.returncode = 1
        return r

    with patch("subprocess.run", side_effect=side_effect):
        errors = agent._run_typescript_linter(str(tmp_path))

    assert len(errors) == 1
    assert errors[0]["rule"] == "prefer-const"


@pytest.mark.unit
def test_run_typescript_linter_timeout_continues(tmp_path):
    """TimeoutExpired on oxlint falls through to eslint attempt."""
    import subprocess
    agent = SREAgent.__new__(SREAgent)
    agent._strategy_selector = None
    agent.log = MagicMock()

    call_count = [0]

    def side_effect(cmd, **kwargs):
        call_count[0] += 1
        if call_count[0] <= 2:  # oxlint binary + oxlint path
            raise subprocess.TimeoutExpired(cmd, 90)
        raise FileNotFoundError  # eslint also not found

    with patch("subprocess.run", side_effect=side_effect):
        errors = agent._run_typescript_linter(str(tmp_path))

    assert errors == []


# ---------------------------------------------------------------------------
# TS architectural rules
# ---------------------------------------------------------------------------

@pytest.mark.unit
def test_ts_architectural_rules_present():
    """typescript/no-explicit-any and related rules are in ARCHITECTURAL_RULES."""
    assert "typescript/no-explicit-any" in SREAgent.ARCHITECTURAL_RULES
    assert "@typescript-eslint/no-explicit-any" in SREAgent.ARCHITECTURAL_RULES
    assert "no-shadow" in SREAgent.ARCHITECTURAL_RULES
    assert "import/no-cycle" in SREAgent.ARCHITECTURAL_RULES


@pytest.mark.unit
def test_ts_architectural_errors_excluded_from_fix_rate():
    """typescript/no-explicit-any goes into architectural_violations, not fix_rate denominator."""
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

    errors = [
        {"rule": "typescript/no-explicit-any", "file": "src/a.ts", "line": 1, "message": "no any"},
        {"rule": "no-var", "file": "src/b.ts", "line": 2, "message": "use let/const"},
    ]

    with patch.object(agent, "_augment_with_rag", return_value={"rag_insights_count": 0, "rag_recommendations": []}), \
         patch.object(agent, "_get_execution_strategy", return_value={"known_failure_types": []}), \
         patch.object(agent, "_apply_linting_fix", return_value={"rule": "no-var", "fix_applied": "Replaced var with let"}):
        result = agent.execute({"errors": errors, "repo_path": "."})

    assert result["architectural_violations"] == 1
    assert result["fixable_errors"] == 1  # only no-var
    assert "typescript/no-explicit-any" in result["architectural_violations_by_rule"]


# ---------------------------------------------------------------------------
# Fix map — TS and unicorn rules
# ---------------------------------------------------------------------------

@pytest.mark.unit
@pytest.mark.parametrize("rule", [
    "no-var", "prefer-const", "eqeqeq", "no-debugger",
    "curly", "prefer-template", "no-else-return",
    "unicorn/prefer-includes", "unicorn/no-array-for-each",
    "unicorn/throw-new-error",
    "typescript/no-unused-vars", "typescript/prefer-as-const",
])
def test_ts_rules_in_fix_map(rule):
    """Key TS/unicorn rules appear in _apply_linting_fix fix_map."""
    agent = SREAgent.__new__(SREAgent)
    agent._strategy_selector = None
    agent.log = MagicMock()

    error = {"rule": rule, "file": "src/a.ts", "line": 1, "message": "test"}
    with patch.object(agent, "_apply_fix_to_file", return_value=False), \
         patch.object(agent, "_generate_ci_patch", return_value=None):
        fix = agent._apply_linting_fix(error, None)

    assert fix is not None, f"Rule {rule!r} should produce a fix entry"
    assert fix["rule"] == rule


# ---------------------------------------------------------------------------
# Auto-detection: tsconfig.json present → TS linter runs
# ---------------------------------------------------------------------------

@pytest.mark.unit
def test_auto_detect_ts_repo_on_empty_errors(tmp_path):
    """When no errors supplied and tsconfig.json exists, _run_typescript_linter is called."""
    (tmp_path / "tsconfig.json").write_text("{}")
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

    with patch.object(agent, "_run_typescript_linter", return_value=[]) as mock_ts, \
         patch.object(agent, "_augment_with_rag", return_value={"rag_insights_count": 0, "rag_recommendations": []}), \
         patch.object(agent, "_get_execution_strategy", return_value={"known_failure_types": []}):
        agent.execute({"repo_path": str(tmp_path)})

    mock_ts.assert_called_once_with(str(tmp_path))


@pytest.mark.unit
def test_explicit_ts_language_triggers_linter(tmp_path):
    """language='typescript' triggers _run_typescript_linter even without tsconfig."""
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

    with patch.object(agent, "_run_typescript_linter", return_value=[]) as mock_ts, \
         patch.object(agent, "_augment_with_rag", return_value={"rag_insights_count": 0, "rag_recommendations": []}), \
         patch.object(agent, "_get_execution_strategy", return_value={"known_failure_types": []}):
        agent.execute({"repo_path": str(tmp_path), "language": "typescript"})

    mock_ts.assert_called_once_with(str(tmp_path))
