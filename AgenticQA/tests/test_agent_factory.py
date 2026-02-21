"""
Unit tests for AgentFactory / ConstitutionalWrapper / adapters.
"""

import pytest
from unittest.mock import MagicMock, patch

pytest.importorskip("agenticqa.factory")

from agenticqa.factory import AgentFactory, ConstitutionalWrapper, SUPPORTED_FRAMEWORKS
from agenticqa.factory.constitutional_wrapper import ConstitutionalViolationError


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

class _FakeAgent:
    """Minimal callable that behaves like any framework agent."""
    def invoke(self, input, **kw):
        return {"answer": "ok", "input_keys": list(input.keys())}


# ---------------------------------------------------------------------------
# ConstitutionalWrapper
# ---------------------------------------------------------------------------

@pytest.mark.unit
class TestConstitutionalWrapper:
    def _wrap(self, verdict="ALLOW"):
        agent = _FakeAgent()
        wrapper = ConstitutionalWrapper(agent, "test_agent", "custom", capabilities=["search"])
        # Patch constitutional gate
        wrapper._check_action = MagicMock(return_value={"verdict": verdict, "reason": "test"})
        return wrapper

    def test_allow_returns_completed(self):
        wrapper = ConstitutionalWrapper(_FakeAgent(), "test_agent", "custom")
        with patch("agenticqa.factory.constitutional_wrapper.check_action",
                   return_value={"verdict": "ALLOW", "reason": ""}):
            result = wrapper.invoke({"task": "hello"})
        assert result["status"] == "completed"
        assert "result" in result
        assert "trace_id" in result

    def test_deny_raises(self):
        wrapper = ConstitutionalWrapper(_FakeAgent(), "test_agent", "custom")
        with patch("agenticqa.factory.constitutional_wrapper.check_action",
                   return_value={"verdict": "DENY", "reason": "prohibited"}):
            with pytest.raises(ConstitutionalViolationError):
                wrapper.invoke({"task": "bad"})

    def test_require_approval_returns_awaiting(self):
        wrapper = ConstitutionalWrapper(_FakeAgent(), "test_agent", "custom")
        with patch("agenticqa.factory.constitutional_wrapper.check_action",
                   return_value={"verdict": "REQUIRE_APPROVAL", "reason": "needs approval"}):
            result = wrapper.invoke({"task": "risky"})
        assert result["status"] == "awaiting_approval"
        assert "trace_id" in result

    def test_run_alias(self):
        wrapper = ConstitutionalWrapper(_FakeAgent(), "test_agent", "custom")
        with patch("agenticqa.factory.constitutional_wrapper.check_action",
                   return_value={"verdict": "ALLOW", "reason": ""}):
            result = wrapper.run({"task": "hi"})
        assert result["status"] == "completed"

    def test_call_alias(self):
        wrapper = ConstitutionalWrapper(_FakeAgent(), "test_agent", "custom")
        with patch("agenticqa.factory.constitutional_wrapper.check_action",
                   return_value={"verdict": "ALLOW", "reason": ""}):
            result = wrapper({"task": "hi"})
        assert result["status"] == "completed"

    def test_framework_in_result(self):
        wrapper = ConstitutionalWrapper(_FakeAgent(), "my_agent", "langgraph")
        with patch("agenticqa.factory.constitutional_wrapper.check_action",
                   return_value={"verdict": "ALLOW", "reason": ""}):
            result = wrapper.invoke({})
        assert result["framework"] == "langgraph"
        assert result["agent"] == "my_agent"


# ---------------------------------------------------------------------------
# AgentFactory — wrap
# ---------------------------------------------------------------------------

@pytest.mark.unit
class TestAgentFactoryWrap:
    def test_wrap_returns_wrapper(self):
        factory = AgentFactory()
        agent = _FakeAgent()
        wrapper = factory.wrap("custom", "wrapped_agent", agent, capabilities=["review"])
        assert isinstance(wrapper, ConstitutionalWrapper)
        assert wrapper.agent_name == "wrapped_agent"
        assert wrapper.framework == "custom"

    def test_wrap_unknown_framework_uses_generic(self):
        factory = AgentFactory()
        wrapper = factory.wrap("unknown_fw", "x_agent", _FakeAgent())
        assert isinstance(wrapper, ConstitutionalWrapper)

    @pytest.mark.parametrize("fw", ["langgraph", "langchain", "crewai", "autogen", "custom"])
    def test_wrap_all_supported_frameworks(self, fw):
        factory = AgentFactory()
        wrapper = factory.wrap(fw, f"{fw}_agent", _FakeAgent())
        assert isinstance(wrapper, ConstitutionalWrapper)
        assert wrapper.framework == fw


# ---------------------------------------------------------------------------
# AgentFactory — scaffold
# ---------------------------------------------------------------------------

@pytest.mark.unit
class TestAgentFactoryScaffold:
    def test_scaffold_langgraph(self):
        factory = AgentFactory()
        result = factory.scaffold("langgraph", "search_agent", ["search", "summarize"])
        assert result["framework"] == "langgraph"
        assert result["agent_name"] == "search_agent"
        assert "generated_code" in result
        code = result["generated_code"]
        assert "search_agent" in code
        assert "ConstitutionalWrapper" in code

    def test_scaffold_langchain(self):
        factory = AgentFactory()
        result = factory.scaffold("langchain", "lc_agent", ["review"])
        assert "generated_code" in result
        assert "lc_agent" in result["generated_code"]

    def test_scaffold_crewai(self):
        factory = AgentFactory()
        result = factory.scaffold("crewai", "crew_agent", [])
        assert result["framework"] == "crewai"
        assert "generated_code" in result

    def test_scaffold_capabilities_in_code(self):
        factory = AgentFactory()
        result = factory.scaffold("langgraph", "cap_agent", ["write_code", "delegate"])
        code = result["generated_code"]
        assert "write_code" in code or "write" in code

    def test_scaffold_returns_valid_python(self):
        """Generated code must at least compile."""
        factory = AgentFactory()
        result = factory.scaffold("custom", "py_check_agent", ["search"])
        code = result["generated_code"]
        compile(code, "<scaffold>", "exec")  # raises SyntaxError if invalid


# ---------------------------------------------------------------------------
# SUPPORTED_FRAMEWORKS
# ---------------------------------------------------------------------------

@pytest.mark.unit
def test_supported_frameworks_keys():
    expected = {"langgraph", "langchain", "crewai", "autogen", "custom"}
    assert set(SUPPORTED_FRAMEWORKS.keys()) == expected


@pytest.mark.unit
def test_supported_frameworks_count():
    assert len(SUPPORTED_FRAMEWORKS) == 5
