"""Tests for SRE Agent Python auto-linting (_run_python_linter).

Validates:
  - flake8 invocation and output parsing
  - Python project auto-detection (setup.py, pyproject.toml, requirements.txt)
  - Graceful handling of missing flake8, timeout, no Python files
  - Integration with execute() auto-detect path
"""
import os
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock

from agents import SREAgent


# ── Helpers ──────────────────────────────────────────────────────────────────

def _make_sre():
    agent = SREAgent.__new__(SREAgent)
    agent.agent_name = "SRE_Agent"
    agent._strategy_selector = None
    agent._outcome_tracker = None
    agent._threshold_calibrator = None
    agent._rag_system = None
    agent.use_rag = False
    agent.rag = None
    agent.use_data_store = False
    agent.data_store = None
    return agent


# ── _run_python_linter tests ─────────────────────────────────────────────────

@pytest.mark.unit
def test_python_linter_parses_flake8_output(tmp_path):
    """Correctly parses flake8 output format into error dicts."""
    agent = _make_sre()
    (tmp_path / "setup.py").write_text("# setup")
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "app.py").write_text("import os\n")

    flake8_output = (
        "src/app.py:1:1:F401:module 'os' imported but unused\n"
        "src/app.py:2:1:W391:blank line at end of file\n"
    )
    mock_proc = MagicMock()
    mock_proc.stdout = flake8_output
    mock_proc.returncode = 1

    with patch("subprocess.run", return_value=mock_proc):
        errors = agent._run_python_linter(str(tmp_path))

    assert len(errors) == 2
    assert errors[0]["rule"] == "F401"
    assert errors[0]["file"] == "src/app.py"
    assert errors[0]["line"] == 1
    assert errors[0]["col"] == 1
    assert "imported but unused" in errors[0]["message"]
    assert errors[1]["rule"] == "W391"


@pytest.mark.unit
def test_python_linter_returns_empty_when_no_python(tmp_path):
    """Returns [] if no Python indicators are present."""
    agent = _make_sre()
    (tmp_path / "index.js").write_text("console.log('hi')")

    errors = agent._run_python_linter(str(tmp_path))
    assert errors == []


@pytest.mark.unit
def test_python_linter_returns_empty_on_flake8_not_found(tmp_path):
    """Returns [] gracefully when flake8 is not installed."""
    agent = _make_sre()
    (tmp_path / "setup.py").write_text("# setup")
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "app.py").write_text("x = 1")

    with patch("subprocess.run", side_effect=FileNotFoundError("flake8 not found")):
        errors = agent._run_python_linter(str(tmp_path))
    assert errors == []


@pytest.mark.unit
def test_python_linter_returns_empty_on_timeout(tmp_path):
    """Returns [] gracefully on subprocess timeout."""
    import subprocess
    agent = _make_sre()
    (tmp_path / "setup.py").write_text("# setup")
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "app.py").write_text("x = 1")

    with patch("subprocess.run", side_effect=subprocess.TimeoutExpired("flake8", 120)):
        errors = agent._run_python_linter(str(tmp_path))
    assert errors == []


@pytest.mark.unit
def test_python_linter_detects_setup_py(tmp_path):
    """Triggers when setup.py is present."""
    agent = _make_sre()
    (tmp_path / "setup.py").write_text("# setup")
    (tmp_path / "mymodule.py").write_text("x=1\n")

    mock_proc = MagicMock()
    mock_proc.stdout = "mymodule.py:1:2:E225:missing whitespace around operator\n"
    mock_proc.returncode = 1

    with patch("subprocess.run", return_value=mock_proc):
        errors = agent._run_python_linter(str(tmp_path))
    assert len(errors) == 1
    assert errors[0]["rule"] == "E225"


@pytest.mark.unit
def test_python_linter_detects_pyproject_toml(tmp_path):
    """Triggers when pyproject.toml is present."""
    agent = _make_sre()
    (tmp_path / "pyproject.toml").write_text("[project]\nname='test'\n")
    (tmp_path / "app.py").write_text("x=1\n")

    mock_proc = MagicMock()
    mock_proc.stdout = ""
    mock_proc.returncode = 0

    with patch("subprocess.run", return_value=mock_proc):
        errors = agent._run_python_linter(str(tmp_path))
    assert errors == []


@pytest.mark.unit
def test_python_linter_detects_requirements_txt(tmp_path):
    """Triggers when requirements.txt is present."""
    agent = _make_sre()
    (tmp_path / "requirements.txt").write_text("flask\n")
    (tmp_path / "app.py").write_text("x=1\n")

    mock_proc = MagicMock()
    mock_proc.stdout = ""
    mock_proc.returncode = 0

    with patch("subprocess.run", return_value=mock_proc):
        errors = agent._run_python_linter(str(tmp_path))
    assert errors == []


@pytest.mark.unit
def test_python_linter_prefers_src_dir(tmp_path):
    """Scans 'src/' directory when present."""
    agent = _make_sre()
    (tmp_path / "setup.py").write_text("# setup")
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "main.py").write_text("x=1\n")

    mock_proc = MagicMock()
    mock_proc.stdout = ""
    mock_proc.returncode = 0

    with patch("subprocess.run", return_value=mock_proc) as mock_run:
        agent._run_python_linter(str(tmp_path))
    # Check that "src" was in the command args
    call_args = mock_run.call_args[0][0]
    assert "src" in call_args


@pytest.mark.unit
def test_python_linter_handles_malformed_lines(tmp_path):
    """Skips lines that don't match the expected format."""
    agent = _make_sre()
    (tmp_path / "setup.py").write_text("# setup")
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "app.py").write_text("x=1\n")

    flake8_output = (
        "src/app.py:1:1:E225:missing whitespace\n"
        "some garbage line\n"
        "3\n"
        "src/app.py:2:1:W291:trailing whitespace\n"
    )
    mock_proc = MagicMock()
    mock_proc.stdout = flake8_output
    mock_proc.returncode = 1

    with patch("subprocess.run", return_value=mock_proc):
        errors = agent._run_python_linter(str(tmp_path))
    assert len(errors) == 2


# ── execute() auto-detect Python ─────────────────────────────────────────────

@pytest.mark.unit
def test_execute_autodetects_python_language(tmp_path):
    """execute() with language='python' and no errors triggers _run_python_linter."""
    agent = _make_sre()
    agent._record_execution = MagicMock()

    mock_errors = [{"file": "app.py", "line": 1, "col": 1, "rule": "E225", "message": "test"}]
    with patch.object(agent, "_run_python_linter", return_value=mock_errors) as mock_lint:
        result = agent.execute({
            "repo_path": str(tmp_path),
            "language": "python",
            "errors": [],
        })
    mock_lint.assert_called_once_with(str(tmp_path))
    assert result["total_errors"] == 1


@pytest.mark.unit
def test_execute_autodetects_python_from_files(tmp_path):
    """execute() with no language auto-detects Python from setup.py."""
    agent = _make_sre()
    agent._record_execution = MagicMock()
    (tmp_path / "setup.py").write_text("# setup")

    mock_errors = [{"file": "app.py", "line": 1, "col": 1, "rule": "W291", "message": "trailing ws"}]
    with patch.object(agent, "_run_python_linter", return_value=mock_errors) as mock_lint:
        result = agent.execute({
            "repo_path": str(tmp_path),
            "errors": [],
        })
    mock_lint.assert_called_once_with(str(tmp_path))
    assert result["total_errors"] == 1


@pytest.mark.unit
def test_execute_does_not_autodetect_when_errors_supplied():
    """execute() with pre-supplied errors does NOT trigger auto-detect."""
    agent = _make_sre()
    agent._record_execution = MagicMock()

    result = agent.execute({
        "language": "python",
        "errors": [{"rule": "E225", "message": "test", "file": "a.py", "line": 1}],
    })
    assert result["total_errors"] == 1
