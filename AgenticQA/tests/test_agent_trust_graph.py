"""Unit tests for AgentTrustGraphAnalyzer — @pytest.mark.unit"""
import pytest
from pathlib import Path

from agenticqa.security.agent_trust_graph import (
    AgentTrustGraphAnalyzer,
    AgentTrustGraph,
)


def make_analyzer() -> AgentTrustGraphAnalyzer:
    return AgentTrustGraphAnalyzer()


def write(path: Path, content: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return path


# ---------------------------------------------------------------------------
# Framework detection
# ---------------------------------------------------------------------------

@pytest.mark.unit
class TestFrameworkDetection:
    def test_langgraph_detected(self, tmp_path):
        write(tmp_path / "graph.py",
              "from langgraph.graph import StateGraph\nwf = StateGraph(State)\n")
        result = make_analyzer().analyze(str(tmp_path))
        assert "langgraph" in result.frameworks_detected

    def test_crewai_detected(self, tmp_path):
        write(tmp_path / "crew.py",
              "from crewai import Agent, Crew\n"
              'agent = Agent(role="researcher")\n')
        result = make_analyzer().analyze(str(tmp_path))
        assert "crewai" in result.frameworks_detected

    def test_autogen_detected(self, tmp_path):
        write(tmp_path / "agents.py",
              "import autogen\n"
              'assistant = autogen.AssistantAgent("assistant")\n')
        result = make_analyzer().analyze(str(tmp_path))
        assert "autogen" in result.frameworks_detected

    def test_clean_repo_no_frameworks(self, tmp_path):
        write(tmp_path / "app.py", "import os\ndef main(): pass\n")
        result = make_analyzer().analyze(str(tmp_path))
        assert result.frameworks_detected == []
        assert result.risk_score == 0.0

    def test_multiple_frameworks(self, tmp_path):
        write(tmp_path / "a.py", "from langgraph.graph import StateGraph\n")
        write(tmp_path / "b.py", "from crewai import Agent\n")
        result = make_analyzer().analyze(str(tmp_path))
        assert "langgraph" in result.frameworks_detected
        assert "crewai" in result.frameworks_detected


# ---------------------------------------------------------------------------
# Node extraction
# ---------------------------------------------------------------------------

@pytest.mark.unit
class TestNodeExtraction:
    def test_langgraph_nodes(self, tmp_path):
        write(tmp_path / "graph.py",
              "from langgraph.graph import StateGraph\n"
              'wf.add_node("planner", planner_fn)\n'
              'wf.add_node("executor", executor_fn)\n')
        result = make_analyzer().analyze(str(tmp_path))
        names = [n.name for n in result.nodes]
        assert "planner" in names
        assert "executor" in names

    def test_autogen_agents(self, tmp_path):
        write(tmp_path / "agents.py",
              "import autogen\n"
              'assistant = autogen.AssistantAgent("assistant_agent")\n'
              'proxy = autogen.UserProxyAgent("user_proxy")\n')
        result = make_analyzer().analyze(str(tmp_path))
        names = [n.name for n in result.nodes]
        assert "assistant_agent" in names
        assert "user_proxy" in names

    def test_crewai_roles(self, tmp_path):
        write(tmp_path / "crew.py",
              "from crewai import Agent\n"
              'researcher = Agent(role="researcher")\n'
              'writer = Agent(role="writer")\n')
        result = make_analyzer().analyze(str(tmp_path))
        names = [n.name for n in result.nodes]
        assert "researcher" in names
        assert "writer" in names


# ---------------------------------------------------------------------------
# Edge extraction
# ---------------------------------------------------------------------------

@pytest.mark.unit
class TestEdgeExtraction:
    def test_langgraph_direct_edge(self, tmp_path):
        write(tmp_path / "graph.py",
              "from langgraph.graph import StateGraph\n"
              'wf.add_node("a", fn_a)\nwf.add_node("b", fn_b)\n'
              'wf.add_edge("a", "b")\n')
        result = make_analyzer().analyze(str(tmp_path))
        edges = [(e.source, e.target) for e in result.edges]
        assert ("a", "b") in edges

    def test_autogen_initiate_chat_edge(self, tmp_path):
        write(tmp_path / "chat.py",
              "import autogen\n"
              'proxy = autogen.UserProxyAgent("proxy")\n'
              'assistant = autogen.AssistantAgent("assistant")\n'
              "proxy.initiate_chat(assistant, message='hello')\n")
        result = make_analyzer().analyze(str(tmp_path))
        # Edge from proxy to assistant
        sources = [e.source for e in result.edges]
        assert "proxy" in sources


# ---------------------------------------------------------------------------
# CIRCULAR_TRUST detection
# ---------------------------------------------------------------------------

@pytest.mark.unit
class TestCircularTrust:
    def test_simple_cycle_detected(self, tmp_path):
        write(tmp_path / "graph.py",
              "from langgraph.graph import StateGraph\n"
              'wf.add_node("agent_a", fn)\nwf.add_node("agent_b", fn)\n'
              'wf.add_edge("agent_a", "agent_b")\n'
              'wf.add_edge("agent_b", "agent_a")\n')
        result = make_analyzer().analyze(str(tmp_path))
        rules = [v.rule_id for v in result.violations]
        assert "CIRCULAR_TRUST" in rules

    def test_no_cycle_in_linear_graph(self, tmp_path):
        write(tmp_path / "graph.py",
              "from langgraph.graph import StateGraph\n"
              'wf.add_node("a", fn)\nwf.add_node("b", fn)\nwf.add_node("c", fn)\n'
              'wf.add_edge("a", "b")\nwf.add_edge("b", "c")\n')
        result = make_analyzer().analyze(str(tmp_path))
        rules = [v.rule_id for v in result.violations]
        assert "CIRCULAR_TRUST" not in rules

    def test_three_node_cycle_detected(self, tmp_path):
        write(tmp_path / "graph.py",
              "from langgraph.graph import StateGraph\n"
              'wf.add_node("a", fn)\nwf.add_node("b", fn)\nwf.add_node("c", fn)\n'
              'wf.add_edge("a", "b")\nwf.add_edge("b", "c")\nwf.add_edge("c", "a")\n')
        result = make_analyzer().analyze(str(tmp_path))
        rules = [v.rule_id for v in result.violations]
        assert "CIRCULAR_TRUST" in rules


# ---------------------------------------------------------------------------
# MISSING_HUMAN_IN_LOOP
# ---------------------------------------------------------------------------

@pytest.mark.unit
class TestMissingHumanInLoop:
    def test_never_mode_flagged(self, tmp_path):
        write(tmp_path / "agents.py",
              "import autogen\n"
              "proxy = autogen.UserProxyAgent('proxy', "
              "human_input_mode='NEVER')\n")
        result = make_analyzer().analyze(str(tmp_path))
        rules = [v.rule_id for v in result.violations]
        assert "MISSING_HUMAN_IN_LOOP" in rules

    def test_terminate_mode_not_flagged(self, tmp_path):
        write(tmp_path / "agents.py",
              "import autogen\n"
              "proxy = autogen.UserProxyAgent('proxy', "
              "human_input_mode='TERMINATE')\n")
        result = make_analyzer().analyze(str(tmp_path))
        rules = [v.rule_id for v in result.violations]
        assert "MISSING_HUMAN_IN_LOOP" not in rules

    def test_human_in_loop_flag_sets_oversight(self, tmp_path):
        write(tmp_path / "agents.py",
              "import autogen\n"
              "proxy = autogen.UserProxyAgent('proxy', "
              "human_input_mode='ALWAYS')\n")
        result = make_analyzer().analyze(str(tmp_path))
        assert result.has_human_oversight is True


# ---------------------------------------------------------------------------
# UNCONSTRAINED_DELEGATION
# ---------------------------------------------------------------------------

@pytest.mark.unit
class TestUnconstrainedDelegation:
    def test_allow_delegation_true_flagged(self, tmp_path):
        write(tmp_path / "crew.py",
              "from crewai import Agent\n"
              "agent = Agent(role='writer', allow_delegation=True)\n")
        result = make_analyzer().analyze(str(tmp_path))
        rules = [v.rule_id for v in result.violations]
        assert "UNCONSTRAINED_DELEGATION" in rules

    def test_allow_delegation_with_allowlist_not_flagged(self, tmp_path):
        write(tmp_path / "crew.py",
              "from crewai import Agent\n"
              "agent = Agent(role='writer', allow_delegation=True, "
              "delegation_allowlist=['researcher'])\n")
        result = make_analyzer().analyze(str(tmp_path))
        rules = [v.rule_id for v in result.violations]
        assert "UNCONSTRAINED_DELEGATION" not in rules

    def test_allow_delegation_false_not_flagged(self, tmp_path):
        write(tmp_path / "crew.py",
              "from crewai import Agent\n"
              "agent = Agent(role='writer', allow_delegation=False)\n")
        result = make_analyzer().analyze(str(tmp_path))
        rules = [v.rule_id for v in result.violations]
        assert "UNCONSTRAINED_DELEGATION" not in rules


# ---------------------------------------------------------------------------
# PRIVILEGED_TOOL_ACCESS
# ---------------------------------------------------------------------------

@pytest.mark.unit
class TestPrivilegedToolAccess:
    def test_shell_tool_without_guardrail_flagged(self, tmp_path):
        write(tmp_path / "agent.py",
              "from langchain.agents import AgentExecutor\n"
              "from langchain.tools import ShellTool\n"
              "tools = [ShellTool()]\n"
              "executor = AgentExecutor(agent=agent, tools=tools)\n")
        result = make_analyzer().analyze(str(tmp_path))
        rules = [v.rule_id for v in result.violations]
        assert "PRIVILEGED_TOOL_ACCESS" in rules

    def test_python_repl_flagged(self, tmp_path):
        write(tmp_path / "agent.py",
              "from langchain.agents import AgentExecutor\n"
              "from langchain.tools import PythonREPLTool\n"
              "tools = [PythonREPLTool()]\n")
        result = make_analyzer().analyze(str(tmp_path))
        rules = [v.rule_id for v in result.violations]
        assert "PRIVILEGED_TOOL_ACCESS" in rules

    def test_shell_tool_with_human_approval_not_flagged(self, tmp_path):
        write(tmp_path / "agent.py",
              "import autogen\n"
              "proxy = autogen.UserProxyAgent('proxy', human_input_mode='TERMINATE')\n"
              "tools = [ShellTool()]\n"
              "# human_approval required before execution\n")
        result = make_analyzer().analyze(str(tmp_path))
        rules = [v.rule_id for v in result.violations]
        # With human approval present, should not flag PRIVILEGED_TOOL_ACCESS
        assert "PRIVILEGED_TOOL_ACCESS" not in rules


# ---------------------------------------------------------------------------
# Risk score and result structure
# ---------------------------------------------------------------------------

@pytest.mark.unit
class TestRiskScore:
    def test_clean_repo_zero_score(self, tmp_path):
        write(tmp_path / "app.py", "import os\n")
        result = make_analyzer().analyze(str(tmp_path))
        assert result.risk_score == 0.0

    def test_violations_raise_score(self, tmp_path):
        write(tmp_path / "graph.py",
              "from langgraph.graph import StateGraph\n"
              'wf.add_node("a", fn)\nwf.add_node("b", fn)\n'
              'wf.add_edge("a", "b")\nwf.add_edge("b", "a")\n')
        result = make_analyzer().analyze(str(tmp_path))
        assert result.risk_score > 0.0

    def test_bad_path_returns_scan_error(self):
        result = make_analyzer().analyze("/nonexistent/path/xyz")
        assert isinstance(result, AgentTrustGraph)

    def test_skips_node_modules(self, tmp_path):
        write(tmp_path / "node_modules" / "pkg" / "index.js",
              "import autogen\n"
              "proxy = autogen.UserProxyAgent('proxy', human_input_mode='NEVER')\n")
        write(tmp_path / "src" / "app.py", "import os\n")
        result = make_analyzer().analyze(str(tmp_path))
        files = [v.source_file for v in result.violations]
        assert not any("node_modules" in f for f in files)
