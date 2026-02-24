"""
Unit tests for Red Team Agent — AdversarialGenerator, PatternPatcher,
OutputScanner red-team-pattern loading, and RedTeamAgent.execute().
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

pytest.importorskip("agenticqa.redteam")

from agenticqa.redteam.adversarial_generator import AdversarialGenerator, BYPASS_TECHNIQUES
from agenticqa.redteam.pattern_patcher import PatternPatcher
from agenticqa.factory.sandbox.output_scanner import OutputScanner


# ---------------------------------------------------------------------------
# TestAdversarialGenerator
# ---------------------------------------------------------------------------

@pytest.mark.unit
class TestAdversarialGenerator:
    def test_generate_fast_returns_list(self):
        gen = AdversarialGenerator()
        result = gen.generate(mode="fast")
        assert isinstance(result, list)
        assert len(result) > 0

    def test_all_techniques_have_required_keys(self):
        gen = AdversarialGenerator()
        for technique in gen.generate(mode="fast"):
            assert "name" in technique, f"missing 'name' in {technique}"
            assert "category" in technique, f"missing 'category' in {technique}"
            assert "description" in technique, f"missing 'description' in {technique}"

    def test_categories_cover_four_domains(self):
        gen = AdversarialGenerator()
        categories = {t["category"] for t in gen.generate(mode="fast")}
        assert "credential_obfuscation" in categories
        assert "shell_injection" in categories
        assert "path_traversal" in categories
        assert "constitutional_gate" in categories

    def test_generate_thorough_falls_back_gracefully(self):
        """thorough mode with anthropic unavailable should still return built-in list."""
        gen = AdversarialGenerator()
        with patch.dict(sys.modules, {"anthropic": None}):
            result = gen.generate(mode="thorough")
        assert isinstance(result, list)
        assert len(result) >= len(BYPASS_TECHNIQUES)


# ---------------------------------------------------------------------------
# TestPatternPatcher
# ---------------------------------------------------------------------------

@pytest.mark.unit
class TestPatternPatcher:
    def test_patch_scanner_writes_json_file(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        patcher = PatternPatcher()
        technique = {
            "name": "test_bypass",
            "category": "credential_obfuscation",
            "description": "test",
            "output": {"token": "sk-ant-fakekey12345678901234"},
        }
        # Use a regex we know will match the output and not match benign
        result = patcher.patch_scanner(technique, r"sk-ant-fake")
        assert result is True
        pattern_file = tmp_path / ".agenticqa" / "red_team_patterns.json"
        assert pattern_file.exists()
        data = json.loads(pattern_file.read_text())
        assert len(data["patterns"]) == 1
        assert data["patterns"][0]["label"] == "red_team_test_bypass"

    def test_patch_scanner_appends_not_overwrites(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        patcher = PatternPatcher()
        t1 = {
            "name": "bypass_one",
            "category": "credential_obfuscation",
            "output": {"token": "sk-ant-fakeone1234567890"},
        }
        t2 = {
            "name": "bypass_two",
            "category": "shell_injection",
            "output": {"cmd": "rm -rf /target"},
        }
        patcher.patch_scanner(t1, r"sk-ant-fakeone")
        patcher.patch_scanner(t2, r"rm\s+-rf\s+/target")
        data = json.loads((tmp_path / ".agenticqa/red_team_patterns.json").read_text())
        assert len(data["patterns"]) == 2

    def test_load_existing_patches_returns_empty_when_no_file(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        patcher = PatternPatcher()
        data = patcher.load_existing_patches()
        assert data == {"version": 1, "patterns": []}

    def test_propose_constitutional_amendment_writes_proposal(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        patcher = PatternPatcher()
        technique = {
            "name": "deploy_alias_release",
            "category": "constitutional_gate",
            "description": "'release' bypasses T2-001 deploy gate",
        }
        proposal_id = patcher.propose_constitutional_amendment(technique, "release")
        assert proposal_id.startswith("prop-")
        proposals_file = tmp_path / ".agenticqa" / "constitutional_proposals.json"
        assert proposals_file.exists()
        data = json.loads(proposals_file.read_text())
        assert len(data["proposals"]) == 1
        assert data["proposals"][0]["proposal_id"] == proposal_id

    def test_generate_regex_returns_none_on_bad_pattern(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        patcher = PatternPatcher()
        # Mock Haiku returning an invalid regex
        mock_module = MagicMock()
        mock_client = MagicMock()
        mock_msg = MagicMock()
        mock_msg.content = [MagicMock(text="[invalid(regex")]
        mock_client.messages.create.return_value = mock_msg
        mock_module.Anthropic.return_value = mock_client
        with patch.dict(sys.modules, {"anthropic": mock_module}):
            result = patcher._generate_regex_for_bypass({"output": {"x": "y"}})
        assert result is None


# ---------------------------------------------------------------------------
# TestOutputScannerLoadsRedTeamPatterns
# ---------------------------------------------------------------------------

@pytest.mark.unit
class TestOutputScannerLoadsRedTeamPatterns:
    def test_scanner_loads_red_team_patterns_when_file_exists(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        rt_dir = tmp_path / ".agenticqa"
        rt_dir.mkdir()
        (rt_dir / "red_team_patterns.json").write_text(json.dumps({
            "version": 1,
            "patterns": [{"label": "my_custom", "regex": r"evil_pattern_xyz"}],
        }))
        scanner = OutputScanner()
        labels = [label for label, _ in scanner._patterns]
        assert "my_custom" in labels

    def test_scanner_applies_loaded_patterns_to_scan(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        rt_dir = tmp_path / ".agenticqa"
        rt_dir.mkdir()
        (rt_dir / "red_team_patterns.json").write_text(json.dumps({
            "version": 1,
            "patterns": [{"label": "custom_bad", "regex": r"SUPERSECRET_TOKEN"}],
        }))
        scanner = OutputScanner()
        result = scanner.scan({"output": "value=SUPERSECRET_TOKEN_xyz"})
        assert result["clean"] is False
        assert any(f["label"] == "custom_bad" for f in result["flags"])

    def test_scanner_handles_missing_file_gracefully(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        scanner = OutputScanner()  # no .agenticqa/ dir
        result = scanner.scan({"status": "ok"})
        assert result["clean"] is True


# ---------------------------------------------------------------------------
# TestRedTeamAgent
# ---------------------------------------------------------------------------

@pytest.mark.unit
class TestRedTeamAgent:
    """Tests for RedTeamAgent.execute() — uses __new__() to bypass BaseAgent.__init__."""

    @pytest.fixture(autouse=True)
    def _chdir(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)

    def _make_agent(self):
        """Construct RedTeamAgent bypassing BaseAgent.__init__ (avoids DB connections)."""
        from agents import RedTeamAgent
        from agenticqa.redteam import AdversarialGenerator, PatternPatcher

        agent = RedTeamAgent.__new__(RedTeamAgent)
        # Minimum BaseAgent attributes
        agent.agent_name = "RedTeam_Agent"
        agent.use_data_store = False
        agent.use_rag = False
        agent.agent_registry = None
        agent._delegation_depth = 0
        agent.pipeline = None
        agent.pattern_analyzer = None
        agent.repo_profile = None
        agent.rag = None
        agent.feedback = None
        agent.outcome_tracker = None
        agent._threshold_calibrator = None
        agent._strategy_selector = None
        agent._last_retrieved_doc_ids = []
        agent.execution_history = []
        # RedTeamAgent-specific
        agent._generator = AdversarialGenerator()
        agent._patcher = PatternPatcher()
        # No-op _record_execution to avoid pipeline dependency
        agent._record_execution = MagicMock()
        agent.log = MagicMock()
        return agent

    def test_execute_returns_required_keys(self, tmp_path):
        agent = self._make_agent()
        result = agent.execute({"mode": "fast", "target": "both", "auto_patch": False})
        required = {
            "bypass_attempts", "successful_bypasses", "patches_applied",
            "proposals_generated", "scanner_strength", "gate_strength",
            "vulnerabilities", "constitutional_proposals", "status",
        }
        assert required.issubset(result.keys())

    def test_bypass_attempts_equals_technique_count(self, tmp_path):
        agent = self._make_agent()
        result = agent.execute({"mode": "fast", "target": "both", "auto_patch": False})
        assert result["bypass_attempts"] == len(BYPASS_TECHNIQUES)

    def test_scanner_strength_between_0_and_1(self, tmp_path):
        agent = self._make_agent()
        result = agent.execute({"mode": "fast", "target": "scanner", "auto_patch": False})
        assert 0.0 <= result["scanner_strength"] <= 1.0

    def test_gate_strength_between_0_and_1(self, tmp_path):
        agent = self._make_agent()
        result = agent.execute({"mode": "fast", "target": "gate", "auto_patch": False})
        assert 0.0 <= result["gate_strength"] <= 1.0

    def test_vulnerabilities_never_contain_raw_output(self, tmp_path):
        agent = self._make_agent()
        result = agent.execute({"mode": "fast", "target": "both", "auto_patch": False})
        for vuln in result["vulnerabilities"]:
            assert "output" not in vuln, "raw output must be stripped from vulnerability records"

    def test_status_is_valid_value(self, tmp_path):
        agent = self._make_agent()
        result = agent.execute({"mode": "fast", "target": "both", "auto_patch": False})
        assert result["status"] in {"clean", "bypasses_found", "patched"}

    def test_auto_patch_false_does_not_write_file(self, tmp_path):
        agent = self._make_agent()
        agent.execute({"mode": "fast", "target": "scanner", "auto_patch": False})
        assert not (tmp_path / ".agenticqa" / "red_team_patterns.json").exists()

    def test_auto_patch_true_may_write_file(self, tmp_path):
        """With auto_patch=True, if scanner bypasses found, patterns file should appear."""
        agent = self._make_agent()
        with patch("agenticqa.redteam.pattern_patcher.PatternPatcher._generate_regex_for_bypass",
                   return_value=r"dG9rZW49"):  # matches base64_encoded_secret sample
            result = agent.execute({"mode": "fast", "target": "scanner", "auto_patch": True})
        if result["patches_applied"] > 0:
            assert (tmp_path / ".agenticqa" / "red_team_patterns.json").exists()
