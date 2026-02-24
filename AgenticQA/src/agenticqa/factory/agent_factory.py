"""AgentFactory — create and scaffold governed agents for any framework."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from agenticqa.factory.constitutional_wrapper import ConstitutionalWrapper
from agenticqa.factory.adapters.generic_adapter import GenericAdapter
from agenticqa.factory.adapters.langgraph_adapter import LangGraphAdapter
from agenticqa.factory.adapters.sandboxed_adapter import SandboxedAgentAdapter

SUPPORTED_FRAMEWORKS: Dict[str, Any] = {
    "langgraph": LangGraphAdapter,
    "langchain": GenericAdapter,
    "crewai": GenericAdapter,
    "autogen": GenericAdapter,
    "custom": GenericAdapter,
    "sandboxed": SandboxedAgentAdapter,
}


class AgentFactory:
    """
    Creates and scaffolds constitutionally-governed agents for any framework.

    Two main flows:
    1. wrap()     — you have an existing agent object, wrap it with governance
    2. scaffold() — generate starter code for a new governed agent
    """

    def wrap(
        self,
        framework: str,
        agent_name: str,
        agent_obj: Any,
        capabilities: Optional[List[str]] = None,
        scopes: Optional[Dict[str, Any]] = None,
    ) -> ConstitutionalWrapper:
        """
        Wrap an existing agent object with constitutional governance.

        Args:
            framework:    "langgraph" | "langchain" | "crewai" | "autogen" | "custom"
            agent_name:   Unique name for this agent (used in audit logs, Neo4j)
            agent_obj:    The raw agent object (must have .invoke() or .run() or be callable)
            capabilities: Human-readable list of what this agent does
            scopes:       Optional dict of read/write/deny file patterns
        """
        adapter = SUPPORTED_FRAMEWORKS.get(framework, GenericAdapter)
        if adapter is GenericAdapter:
            return adapter.wrap(agent_obj, agent_name, capabilities, framework=framework)
        return adapter.wrap(agent_obj, agent_name, capabilities)

    def scaffold(
        self,
        framework: str,
        agent_name: str,
        capabilities: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """
        Generate governed agent starter code for the given framework.

        Returns a dict with generated_code (ready to save as a .py file),
        plus metadata about the agent.
        """
        capabilities = capabilities or []
        adapter = SUPPORTED_FRAMEWORKS.get(framework, GenericAdapter)

        if framework == "langgraph":
            code = adapter.scaffold(agent_name, capabilities)
        elif framework == "sandboxed":
            code = SandboxedAgentAdapter.scaffold(agent_name, capabilities)
        else:
            code = GenericAdapter.scaffold(agent_name, capabilities, framework=framework)

        return {
            "framework": framework,
            "agent_name": agent_name,
            "capabilities": capabilities,
            "governed": True,
            "generated_code": code,
            "install_hint": _install_hint(framework),
            "usage": f'{agent_name}_agent.invoke({{"input": "your prompt"}})',
        }

    def register(
        self,
        wrapper: ConstitutionalWrapper,
        graph_store=None,
        registry=None,
    ) -> Dict[str, Any]:
        """
        Register a wrapped agent in Neo4j + AgentRegistry.

        Args:
            wrapper:     ConstitutionalWrapper to register
            graph_store: Optional DelegationGraphStore (Neo4j)
            registry:    Optional AgentRegistry for delegation routing
        """
        registered = []

        if graph_store is not None:
            try:
                graph_store.create_or_update_agent(wrapper.agent_name, wrapper.framework)
                registered.append("neo4j")
            except Exception:
                pass

        if registry is not None:
            try:
                registry.register_agent(wrapper)
                registered.append("agent_registry")
            except Exception:
                pass

        # Register capabilities as task types in the delegation ontology so the
        # new agent is reachable via delegate_to_agent() and GraphRAG routing.
        try:
            from agenticqa.delegation.guardrails import DelegationGuardrails
            for cap in getattr(wrapper, "capabilities", []):
                task_type = cap.lower().replace(" ", "_")
                if task_type not in DelegationGuardrails.TASK_AGENT_MAP:
                    DelegationGuardrails.TASK_AGENT_MAP[task_type] = []
                if wrapper.agent_name not in DelegationGuardrails.TASK_AGENT_MAP[task_type]:
                    DelegationGuardrails.TASK_AGENT_MAP[task_type].append(wrapper.agent_name)
            registered.append("ontology")
        except Exception:
            pass

        return {"agent_name": wrapper.agent_name, "registered_in": registered}


def _install_hint(framework: str) -> str:
    hints = {
        "langgraph": "pip install langgraph",
        "langchain": "pip install langchain",
        "crewai": "pip install crewai",
        "autogen": "pip install pyautogen",
        "custom": "",
        "sandboxed": "",
    }
    return hints.get(framework, "")
