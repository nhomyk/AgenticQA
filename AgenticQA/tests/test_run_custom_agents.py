"""Unit tests for run_custom_agents.py."""
import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# Import functions from the top-level script
import sys
sys.path.insert(0, str(Path(__file__).parent.parent))
from run_custom_agents import discover_agents, load_agent_module, run_agent, ingest_result


@pytest.mark.unit
class TestDiscoverAgents:
    def test_discover_empty_dir(self, tmp_path):
        result = discover_agents(tmp_path)
        assert result == []

    def test_discover_returns_only_py_files(self, tmp_path):
        (tmp_path / "agent_a.py").write_text("# agent")
        (tmp_path / "readme.md").write_text("# readme")
        (tmp_path / "config.json").write_text("{}")
        result = discover_agents(tmp_path)
        assert len(result) == 1
        assert result[0].name == "agent_a.py"

    def test_discover_sorted(self, tmp_path):
        (tmp_path / "zzz_agent.py").write_text("# z")
        (tmp_path / "aaa_agent.py").write_text("# a")
        (tmp_path / "mmm_agent.py").write_text("# m")
        result = discover_agents(tmp_path)
        names = [r.name for r in result]
        assert names == sorted(names)

    def test_discover_nonexistent_dir(self, tmp_path):
        missing = tmp_path / "nonexistent"
        result = discover_agents(missing)
        assert result == []


@pytest.mark.unit
class TestLoadAgentModule:
    def test_load_valid_module(self, tmp_path):
        agent_file = tmp_path / "my_agent.py"
        agent_file.write_text("def run(ctx): return {'ok': True}\n")
        module = load_agent_module(agent_file)
        assert module is not None
        assert hasattr(module, "run")

    def test_load_module_with_syntax_error(self, tmp_path, capsys):
        agent_file = tmp_path / "broken.py"
        agent_file.write_text("def broken(\n  # unclosed")
        module = load_agent_module(agent_file)
        assert module is None
        captured = capsys.readouterr()
        assert "WARN" in captured.out

    def test_load_module_with_import_error(self, tmp_path, capsys):
        agent_file = tmp_path / "bad_import.py"
        agent_file.write_text("import nonexistent_package_xyz123\n")
        module = load_agent_module(agent_file)
        assert module is None


@pytest.mark.unit
class TestRunAgent:
    def test_run_agent_success(self, tmp_path):
        agent_file = tmp_path / "good_agent.py"
        agent_file.write_text(
            "def run(ctx):\n    return {'status': 'ok', 'processed': ctx.get('run_id')}\n"
        )
        result = run_agent(agent_file, {"run_id": "test-123"})
        assert result["status"] == "success"
        assert result["output"]["status"] == "ok"
        assert result["output"]["processed"] == "test-123"
        assert result["error"] is None
        assert result["duration_ms"] >= 0

    def test_run_agent_exception_captured(self, tmp_path):
        agent_file = tmp_path / "failing_agent.py"
        agent_file.write_text(
            "def run(ctx):\n    raise ValueError('deliberate test error')\n"
        )
        result = run_agent(agent_file, {})
        assert result["status"] == "error"
        assert result["error"] is not None
        assert "deliberate test error" in result["error"]

    def test_run_agent_missing_run_function(self, tmp_path):
        agent_file = tmp_path / "no_run.py"
        agent_file.write_text("def process(ctx): return {}\n")
        result = run_agent(agent_file, {})
        assert result["status"] == "error"
        assert "run" in result["error"].lower()

    def test_run_agent_invoke_only_warning(self, tmp_path):
        agent_file = tmp_path / "invoke_agent.py"
        agent_file.write_text("def invoke(input): return {}\n")
        result = run_agent(agent_file, {})
        assert result["status"] == "error"
        assert "invoke" in result["error"].lower()

    def test_run_agent_import_failure(self, tmp_path):
        agent_file = tmp_path / "bad_import.py"
        agent_file.write_text("import nonexistent_pkg_xyz\ndef run(ctx): return {}\n")
        result = run_agent(agent_file, {})
        assert result["status"] == "error"

    def test_run_agent_non_dict_output_wrapped(self, tmp_path):
        agent_file = tmp_path / "str_agent.py"
        agent_file.write_text("def run(ctx): return 'just a string'\n")
        result = run_agent(agent_file, {})
        assert result["status"] == "success"
        assert result["output"] == {"result": "just a string"}

    def test_run_agent_includes_agent_name(self, tmp_path):
        agent_file = tmp_path / "named_agent.py"
        agent_file.write_text("def run(ctx): return {}\n")
        result = run_agent(agent_file, {})
        assert result["agent_name"] == "named_agent"


@pytest.mark.unit
class TestIngestResult:
    def test_ingest_result_calls_store(self, tmp_path):
        mock_store = MagicMock()
        result = {
            "agent_name": "test_agent",
            "status": "success",
            "output": {"ok": True},
            "error": None,
            "duration_ms": 42,
            "agent_file": "test_agent.py",
        }
        # TestArtifactStore is lazily imported inside ingest_result — patch at source
        with patch("data_store.artifact_store.TestArtifactStore", return_value=mock_store):
            ingest_result(result, "run-123")
        mock_store.store_artifact.assert_called_once()
        call_kwargs = mock_store.store_artifact.call_args[1]
        assert call_kwargs["source"] == "test_agent"
        assert "custom_agent" in call_kwargs["tags"]

    def test_ingest_result_handles_store_exception(self):
        result = {
            "agent_name": "test_agent",
            "status": "success",
            "output": {},
            "error": None,
            "duration_ms": 10,
            "agent_file": "test_agent.py",
        }
        # Should not raise even if store fails
        with patch("data_store.artifact_store.TestArtifactStore", side_effect=Exception("store down")):
            ingest_result(result, "run-123")  # no exception
