"""Agent registry for discovery and delegation coordination"""

from typing import Dict, Any, Optional, TYPE_CHECKING
from datetime import datetime
import time

from .delegation import (
    DelegationGuardrails,
    DelegationError,
    CircularDelegationError,
    MaxDelegationDepthError,
    UnauthorizedDelegationError
)
from .tracker import DelegationTracker, DelegationEvent

if TYPE_CHECKING:
    from src.agents import BaseAgent


class AgentRegistry:
    """
    Central registry for agent discovery and delegation.

    Manages:
    - Agent registration and lookup
    - Delegation routing with guardrails
    - Delegation tracking and observability
    """

    def __init__(self, enable_delegation: bool = True):
        self.agents: Dict[str, 'BaseAgent'] = {}
        self.guardrails = DelegationGuardrails()
        self.tracker = DelegationTracker()
        self.enable_delegation = enable_delegation
        self._delegation_stack: list[str] = []

    def register_agent(self, agent: 'BaseAgent'):
        """Register an agent for collaboration"""
        self.agents[agent.agent_name] = agent
        agent.agent_registry = self  # Inject registry into agent

    def delegate_task(
        self,
        from_agent: str,
        to_agent: str,
        task: Dict[str, Any],
        depth: int = 0
    ) -> Dict[str, Any]:
        """
        Delegate a task from one agent to another with safety guardrails.

        Args:
            from_agent: Name of agent delegating the task
            to_agent: Name of target agent
            task: Task data to pass to target agent
            depth: Current delegation depth (0 = root)

        Returns:
            Result from target agent

        Raises:
            CircularDelegationError: If circular delegation detected
            MaxDelegationDepthError: If max depth exceeded
            UnauthorizedDelegationError: If delegation not whitelisted
            DelegationError: For other delegation failures
        """
        if not self.enable_delegation:
            raise DelegationError("Delegation is disabled")

        # Check guardrails
        allowed, reason = self.guardrails.can_delegate(
            from_agent, to_agent, depth, self._delegation_stack
        )
        if not allowed:
            if "depth" in reason.lower():
                raise MaxDelegationDepthError(reason)
            elif "circular" in reason.lower():
                raise CircularDelegationError(reason)
            elif "authorized" in reason.lower():
                raise UnauthorizedDelegationError(reason)
            else:
                raise DelegationError(reason)

        # Get target agent
        target = self.agents.get(to_agent)
        if not target:
            raise DelegationError(f"Agent {to_agent} not found in registry")

        # Track delegation
        event = self.tracker.record_delegation(from_agent, to_agent, task, depth)
        self.guardrails.record_delegation(from_agent, to_agent)
        self._delegation_stack.append(to_agent)

        # Execute delegation
        start_time = time.time()
        try:
            result = target.execute(task)
            duration_ms = (time.time() - start_time) * 1000
            self.tracker.record_result(event, result, duration_ms)

            # Add delegation metadata to result
            result["_delegation"] = {
                "delegated_by": from_agent,
                "depth": depth,
                "duration_ms": duration_ms
            }

            return result

        except Exception as e:
            error_msg = f"{type(e).__name__}: {str(e)}"
            self.tracker.record_error(event, error_msg)
            raise DelegationError(f"Delegation from {from_agent} to {to_agent} failed: {error_msg}") from e

        finally:
            if self._delegation_stack and self._delegation_stack[-1] == to_agent:
                self._delegation_stack.pop()

    def query_agent(
        self,
        from_agent: str,
        to_agent: str,
        question: Dict[str, Any],
        depth: int = 0
    ) -> Dict[str, Any]:
        """
        Query another agent for expertise (read-only, no state changes).
        This is a lighter-weight alternative to full delegation.
        """
        # For now, query is the same as delegate
        # In future, could optimize for read-only operations
        return self.delegate_task(from_agent, to_agent, question, depth)

    def get_available_agents(self) -> list[str]:
        """Get list of registered agents"""
        return list(self.agents.keys())

    def can_agent_delegate_to(self, from_agent: str, to_agent: str) -> bool:
        """Check if one agent can delegate to another"""
        allowed, _ = self.guardrails.can_delegate(
            from_agent, to_agent, 0, []
        )
        return allowed

    def get_delegation_summary(self) -> Dict[str, Any]:
        """Get summary of delegations for current request"""
        return {
            **self.tracker.get_summary(),
            **self.guardrails.get_delegation_stats()
        }

    def reset_for_new_request(self, root_agent: str):
        """Reset state for a new root request"""
        self.guardrails.reset()
        self.tracker.start_request(root_agent)
        self._delegation_stack = [root_agent]
