"""Unit tests for AgentSpec and NaturalLanguageSpecExtractor."""
import json
import re
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

# Helper: patch the deferred `import anthropic` inside _call_llm
def _patch_anthropic(mock_module):
    """Return a context manager that injects mock_module as sys.modules['anthropic']."""
    return patch.dict(sys.modules, {"anthropic": mock_module})

from agenticqa.factory.spec_extractor import (
    AgentSpec,
    NaturalLanguageSpecExtractor,
    VALID_FRAMEWORKS,
)


# ─────────────────────────────────────────────────────────────────────────────
# AgentSpec
# ─────────────────────────────────────────────────────────────────────────────


@pytest.mark.unit
class TestAgentSpec:
    def test_to_dict_has_all_required_keys(self):
        spec = AgentSpec(
            "my_agent", "desc", ["cap1", "cap2"], "sandboxed",
            {"file_patterns": ["**/*.py"], "languages": ["python"]},
            ["no_secrets"],
        )
        d = spec.to_dict()
        assert set(d.keys()) == {"agent_name", "capabilities", "framework", "scope", "checks"}

    def test_to_dict_values_match(self):
        spec = AgentSpec("scan_agent", "scans code", ["scan", "report"])
        d = spec.to_dict()
        assert d["agent_name"] == "scan_agent"
        assert d["capabilities"] == ["scan", "report"]

    def test_scaffold_compatible_dict(self):
        """to_dict() output must be usable as AgentFactory.scaffold() kwargs."""
        from agenticqa.factory import AgentFactory

        spec = AgentSpec("test_agent", "desc", ["search", "report"], "sandboxed")
        d = spec.to_dict()
        result = AgentFactory().scaffold(
            framework=d["framework"],
            agent_name=d["agent_name"],
            capabilities=d["capabilities"],
        )
        assert result["agent_name"] == "test_agent"
        assert "generated_code" in result

    def test_default_framework_is_sandboxed(self):
        spec = AgentSpec("x", "desc", ["a", "b"])
        assert spec.framework == "sandboxed"


# ─────────────────────────────────────────────────────────────────────────────
# LLM extraction path
# ─────────────────────────────────────────────────────────────────────────────


def _make_valid_llm_dict(**overrides) -> dict:
    base = {
        "agent_name": "security_scanner",
        "description": "Scans code for vulnerabilities",
        "capabilities": ["scan_code", "report_findings"],
        "framework": "sandboxed",
        "scope": {"file_patterns": ["**/*.py"], "languages": ["python"]},
        "checks": ["no_secrets", "valid_json_output"],
    }
    base.update(overrides)
    return base


def _mock_anthropic_for(data: dict):
    """Return a mock anthropic module that simulates a valid LLM response."""
    mock_module = MagicMock()
    mock_client = MagicMock()
    mock_message = MagicMock()
    mock_message.content = [MagicMock(text=json.dumps(data))]
    mock_client.messages.create.return_value = mock_message
    mock_module.Anthropic.return_value = mock_client
    return mock_module


@pytest.mark.unit
class TestNaturalLanguageSpecExtractorLLMPath:
    def test_extract_returns_agent_spec_on_valid_llm_response(self):
        data = _make_valid_llm_dict()
        extractor = NaturalLanguageSpecExtractor()
        with _patch_anthropic(_mock_anthropic_for(data)):
            spec = extractor.extract("An agent that scans Python files for security issues")
        assert isinstance(spec, AgentSpec)
        assert spec.agent_name == "security_scanner"
        assert spec.framework == "sandboxed"
        assert len(spec.capabilities) >= 2

    def test_extract_uses_fallback_when_llm_unavailable(self):
        extractor = NaturalLanguageSpecExtractor()
        # Remove anthropic from sys.modules so the import fails inside _call_llm
        with patch.dict(sys.modules, {"anthropic": None}):
            spec = extractor.extract("scan Python files for lint errors")
        assert isinstance(spec, AgentSpec)
        assert spec.agent_name
        assert len(spec.capabilities) >= 2

    def test_extract_uses_fallback_when_llm_returns_invalid_json(self):
        mock_module = MagicMock()
        mock_client = MagicMock()
        mock_message = MagicMock()
        mock_message.content = [MagicMock(text="not valid json at all")]
        mock_client.messages.create.return_value = mock_message
        mock_module.Anthropic.return_value = mock_client

        extractor = NaturalLanguageSpecExtractor()
        with _patch_anthropic(mock_module):
            spec = extractor.extract("run tests and report results")
        assert isinstance(spec, AgentSpec)

    def test_extract_uses_fallback_when_llm_returns_missing_fields(self):
        # Missing "checks" field — fails _validate_spec_dict
        incomplete = {
            "agent_name": "bad_agent",
            "description": "incomplete",
            "capabilities": ["a", "b"],
            "framework": "sandboxed",
            "scope": {},
        }
        extractor = NaturalLanguageSpecExtractor()
        with _patch_anthropic(_mock_anthropic_for(incomplete)):
            spec = extractor.extract("some description")
        assert isinstance(spec, AgentSpec)

    def test_extract_empty_description_returns_spec(self):
        extractor = NaturalLanguageSpecExtractor()
        spec = extractor.extract("")
        assert isinstance(spec, AgentSpec)
        assert spec.agent_name

    def test_framework_in_spec_reflects_llm_choice(self):
        data = _make_valid_llm_dict(framework="langgraph")
        extractor = NaturalLanguageSpecExtractor()
        with _patch_anthropic(_mock_anthropic_for(data)):
            spec = extractor.extract("build a langgraph workflow")
        assert spec.framework == "langgraph"


# ─────────────────────────────────────────────────────────────────────────────
# Fallback extraction path
# ─────────────────────────────────────────────────────────────────────────────


@pytest.mark.unit
class TestFallbackExtract:
    def test_fallback_returns_agent_spec(self):
        extractor = NaturalLanguageSpecExtractor()
        spec = extractor._fallback_extract("scan python files for security issues")
        assert isinstance(spec, AgentSpec)

    def test_fallback_default_capabilities_when_no_keywords_match(self):
        extractor = NaturalLanguageSpecExtractor()
        spec = extractor._fallback_extract("zzz qqq mmm")
        assert len(spec.capabilities) >= 2

    def test_fallback_detects_typescript(self):
        extractor = NaturalLanguageSpecExtractor()
        spec = extractor._fallback_extract("analyze typescript components in .tsx files")
        patterns = spec.scope.get("file_patterns", [])
        assert any("ts" in p for p in patterns)

    def test_fallback_agent_name_is_snake_case(self):
        extractor = NaturalLanguageSpecExtractor()
        spec = extractor._fallback_extract("scan code for vulnerabilities in Python files")
        assert re.fullmatch(r"[a-z][a-z0-9_]*", spec.agent_name)

    def test_fallback_agent_name_max_40_chars(self):
        extractor = NaturalLanguageSpecExtractor()
        spec = extractor._fallback_extract(
            "scan code for vulnerabilities in Python files and also more words here"
        )
        assert len(spec.agent_name) <= 40


# ─────────────────────────────────────────────────────────────────────────────
# Generated code is valid Python
# ─────────────────────────────────────────────────────────────────────────────


@pytest.mark.unit
class TestGeneratedCodeIsValidPython:
    def test_spec_to_scaffold_produces_compilable_code(self):
        from agenticqa.factory import AgentFactory

        spec = AgentSpec(
            agent_name="my_test_agent",
            description="test agent",
            capabilities=["scan", "report"],
            framework="sandboxed",
            scope={"file_patterns": ["**/*.py"], "languages": ["python"]},
            checks=["no_secrets"],
        )
        result = AgentFactory().scaffold(
            framework=spec.framework,
            agent_name=spec.agent_name,
            capabilities=spec.capabilities,
        )
        compile(result["generated_code"], "<scaffold>", "exec")

    @pytest.mark.parametrize(
        "fw", ["langgraph", "langchain", "crewai", "autogen", "custom", "sandboxed"]
    )
    def test_all_frameworks_produce_valid_python(self, fw):
        from agenticqa.factory import AgentFactory

        spec = AgentSpec("fw_test_agent", "desc", ["task_a", "task_b"], fw)
        result = AgentFactory().scaffold(fw, spec.agent_name, spec.capabilities)
        compile(result["generated_code"], "<scaffold>", "exec")
