"""Unit tests for SDETAgent._generate_tests_for_gap()."""
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest


def _make_sdet_agent():
    """
    Instantiate SDETAgent without triggering __init__ (avoids Weaviate/DB connections).
    Per MEMORY.md: tests using __new__() must manually set _strategy_selector = None.
    """
    from agents import SDETAgent
    agent = SDETAgent.__new__(SDETAgent)
    agent.agent_name = "SDET_Agent"
    agent.use_data_store = False
    agent.use_rag = False
    agent.rag = None
    agent.pipeline = None
    agent.pattern_analyzer = None
    agent.repo_profile = None
    agent.feedback = MagicMock()
    agent.outcome_tracker = MagicMock()
    agent._threshold_calibrator = MagicMock()
    agent._strategy_selector = None
    agent.agent_registry = None
    agent._delegation_depth = 0
    agent._last_retrieved_doc_ids = []
    agent.execution_history = []
    return agent


@pytest.mark.unit
class TestGenerateTestsForGap:
    def test_no_source_file_in_gap(self, tmp_path):
        agent = _make_sdet_agent()
        result = agent._generate_tests_for_gap({"file": "", "priority": "high"}, str(tmp_path))
        assert result["generated"] is False
        assert "no source file" in result["error"]

    def test_source_file_not_found(self, tmp_path):
        agent = _make_sdet_agent()
        gap = {"file": "src/missing_module.py", "priority": "high"}
        result = agent._generate_tests_for_gap(gap, str(tmp_path))
        assert result["generated"] is False
        assert "not found" in result["error"] or "not Python" in result["error"]

    def test_source_file_not_python(self, tmp_path):
        (tmp_path / "app.js").write_text("console.log('hello')")
        gap = {"file": "app.js", "priority": "high"}
        agent = _make_sdet_agent()
        result = agent._generate_tests_for_gap(gap, str(tmp_path))
        assert result["generated"] is False

    def test_llm_unavailable(self, tmp_path):
        (tmp_path / "app.py").write_text("def add(a, b): return a + b\n")
        gap = {"file": "app.py", "priority": "high"}
        agent = _make_sdet_agent()
        # Simulate anthropic not installed / import error
        with patch.dict(sys.modules, {"anthropic": None}):
            result = agent._generate_tests_for_gap(gap, str(tmp_path))
        assert result["generated"] is False
        assert "LLM unavailable" in result["error"]

    def test_syntax_error_in_generated_code(self, tmp_path):
        (tmp_path / "calc.py").write_text("def add(a, b): return a + b\n")
        gap = {"file": "calc.py", "priority": "high"}
        agent = _make_sdet_agent()

        # Mock LLM to return syntactically invalid Python
        mock_client = MagicMock()
        mock_client.messages.create.return_value.content = [
            SimpleNamespace(text="def test_add(\n  # unclosed paren")
        ]
        mock_anthropic = MagicMock()
        mock_anthropic.Anthropic.return_value = mock_client
        with patch.dict(sys.modules, {"anthropic": mock_anthropic}):
            result = agent._generate_tests_for_gap(gap, str(tmp_path))
        assert result["generated"] is False
        assert "Syntax error" in result["error"]

    def test_no_overwrite_existing_file(self, tmp_path):
        (tmp_path / "calc.py").write_text("def add(a, b): return a + b\n")
        gap = {"file": "calc.py", "priority": "high"}
        agent = _make_sdet_agent()

        # Pre-create the output file
        gen_dir = tmp_path / ".agenticqa" / "generated_tests"
        gen_dir.mkdir(parents=True)
        (gen_dir / "test_calc.py").write_text("# existing test\n")

        # Mock LLM to return valid code (shouldn't reach disk write anyway)
        mock_client = MagicMock()
        mock_client.messages.create.return_value.content = [
            SimpleNamespace(text="def test_something(): assert True\n")
        ]
        mock_anthropic = MagicMock()
        mock_anthropic.Anthropic.return_value = mock_client
        with patch.dict(sys.modules, {"anthropic": mock_anthropic}):
            result = agent._generate_tests_for_gap(gap, str(tmp_path))
        assert result["generated"] is False
        assert "already exists" in result["error"]

    def test_collection_failure_prevents_write(self, tmp_path):
        (tmp_path / "calc.py").write_text("def add(a, b): return a + b\n")
        gap = {"file": "calc.py", "priority": "high"}
        agent = _make_sdet_agent()

        valid_test_code = (
            "# valid Python but no test functions\n"
            "def not_a_test(): pass\n"
        )
        mock_client = MagicMock()
        mock_client.messages.create.return_value.content = [
            SimpleNamespace(text=valid_test_code)
        ]
        mock_anthropic = MagicMock()
        mock_anthropic.Anthropic.return_value = mock_client

        mock_proc = MagicMock()
        mock_proc.returncode = 4  # pytest exit code for "no tests collected"

        with patch.dict(sys.modules, {"anthropic": mock_anthropic}):
            with patch("subprocess.run", return_value=mock_proc):
                result = agent._generate_tests_for_gap(gap, str(tmp_path))
        assert result["generated"] is False
        assert "collection" in result["error"].lower() or "failed" in result["error"].lower()
        # Output file should NOT have been created
        out_path = tmp_path / ".agenticqa" / "generated_tests" / "test_calc.py"
        assert not out_path.exists()

    def test_successful_generation(self, tmp_path):
        (tmp_path / "calc.py").write_text("def add(a, b): return a + b\n")
        gap = {"file": "calc.py", "priority": "high"}
        agent = _make_sdet_agent()

        valid_test_code = (
            "def test_add_positive(): assert 1 + 1 == 2\n"
            "def test_add_zero(): assert 0 + 0 == 0\n"
            "def test_add_negative(): assert -1 + 1 == 0\n"
        )
        mock_client = MagicMock()
        mock_client.messages.create.return_value.content = [
            SimpleNamespace(text=valid_test_code)
        ]
        mock_anthropic = MagicMock()
        mock_anthropic.Anthropic.return_value = mock_client

        mock_proc = MagicMock()
        mock_proc.returncode = 0  # successful collection

        with patch.dict(sys.modules, {"anthropic": mock_anthropic}):
            with patch("subprocess.run", return_value=mock_proc):
                result = agent._generate_tests_for_gap(gap, str(tmp_path))
        assert result["generated"] is True
        assert result["file_path"].endswith("test_calc.py")
        # Verify file was written
        out_path = Path(result["file_path"])
        assert out_path.exists()
        assert "test_add_positive" in out_path.read_text()

    def test_strips_markdown_fences(self, tmp_path):
        (tmp_path / "calc.py").write_text("def add(a, b): return a + b\n")
        gap = {"file": "calc.py", "priority": "high"}
        agent = _make_sdet_agent()

        fenced_code = (
            "```python\n"
            "def test_add(): assert 1 + 1 == 2\n"
            "```"
        )
        mock_client = MagicMock()
        mock_client.messages.create.return_value.content = [
            SimpleNamespace(text=fenced_code)
        ]
        mock_anthropic = MagicMock()
        mock_anthropic.Anthropic.return_value = mock_client

        mock_proc = MagicMock()
        mock_proc.returncode = 0

        with patch.dict(sys.modules, {"anthropic": mock_anthropic}):
            with patch("subprocess.run", return_value=mock_proc):
                result = agent._generate_tests_for_gap(gap, str(tmp_path))
        assert result["generated"] is True
        # No fences in written file
        written = Path(result["file_path"]).read_text()
        assert "```" not in written


@pytest.mark.unit
class TestSDETExecuteTestGenIntegration:
    def test_execute_adds_tests_generated_keys(self, tmp_path):
        """
        Verify that execute() returns tests_generated and generated_test_files keys.
        """
        from agents import SDETAgent
        agent = SDETAgent.__new__(SDETAgent)
        agent.agent_name = "SDET_Agent"
        agent.use_data_store = False
        agent.use_rag = False
        agent.rag = None
        agent.pipeline = None
        agent.pattern_analyzer = None
        agent.repo_profile = None
        agent.feedback = MagicMock()
        agent.outcome_tracker = MagicMock()
        agent._threshold_calibrator = MagicMock()
        agent._threshold_calibrator.get_threshold.return_value = 80
        agent._strategy_selector = None
        agent.agent_registry = None
        agent._delegation_depth = 0
        agent._last_retrieved_doc_ids = []
        agent.execution_history = []

        # Patch out _augment_with_rag and _record_execution to avoid infra calls
        agent._augment_with_rag = MagicMock(return_value={
            "rag_recommendations": [],
            "rag_insights_count": 0,
        })
        agent._record_execution = MagicMock()
        agent.log = MagicMock()

        # Input with adequate coverage → no gaps → no test generation
        coverage_data = {
            "coverage_percent": 90,
            "uncovered_files": [],
            "repo_path": str(tmp_path),
        }
        result = agent.execute(coverage_data)
        assert "tests_generated" in result
        assert "generated_test_files" in result
        assert result["tests_generated"] == 0
        assert result["generated_test_files"] == []
