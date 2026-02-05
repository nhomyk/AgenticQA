"""
Delegation Guardrails

Prevents common delegation mistakes by validating task-agent compatibility
before delegations are executed.
"""

from typing import Dict, List, Optional
import logging

logger = logging.getLogger(__name__)


class DelegationGuardrails:
    """Prevent bad delegations through pre-validation"""

    # Define which agents should handle which task types
    # This is the "ontology" - the designed workflow
    TASK_AGENT_MAP = {
        "load_test": ["Performance_Agent", "QA_Agent"],
        "benchmark": ["Performance_Agent"],
        "deploy": ["DevOps_Agent", "SRE_Agent"],
        "deploy_tests": ["SRE_Agent", "DevOps_Agent"],
        "rollback": ["SRE_Agent", "DevOps_Agent"],
        "monitor": ["SRE_Agent", "DevOps_Agent"],
        "generate_tests": ["SDET_Agent", "QA_Agent"],
        "validate_tests": ["SDET_Agent", "QA_Agent"],
        "validate_code": ["QA_Agent", "Fullstack_Agent"],
        "security_scan": ["Compliance_Agent", "SDET_Agent"],
        "audit": ["Compliance_Agent"],
        "compliance_check": ["Compliance_Agent"],
        "implement_feature": ["Fullstack_Agent"],
        "code_review": ["Fullstack_Agent", "Compliance_Agent"],
        "refactor": ["Fullstack_Agent"],
        "ci_cd": ["DevOps_Agent"],
        "infrastructure": ["DevOps_Agent", "SRE_Agent"],
    }

    @classmethod
    def validate_delegation(
        cls,
        from_agent: str,
        to_agent: str,
        task_type: str,
        strict: bool = False
    ) -> Dict[str, any]:
        """
        Validate delegation before executing.

        Args:
            from_agent: Source agent name
            to_agent: Target agent name
            task_type: Type of task being delegated
            strict: If True, reject all invalid delegations

        Returns:
            {
                "valid": bool,
                "reason": str,
                "suggestion": Optional[str],
                "confidence": float
            }
        """
        allowed_agents = cls.TASK_AGENT_MAP.get(task_type, [])

        # Unknown task type - allow but warn
        if not allowed_agents:
            logger.warning(f"Unknown task type: {task_type}")
            return {
                "valid": not strict,
                "reason": f"Unknown task type '{task_type}', no validation rules defined",
                "suggestion": "Consider adding this task type to TASK_AGENT_MAP",
                "confidence": 0.0
            }

        # Valid delegation
        if to_agent in allowed_agents:
            return {
                "valid": True,
                "reason": f"{to_agent} is authorized to handle {task_type}",
                "suggestion": None,
                "confidence": 1.0
            }

        # Invalid delegation - suggest alternatives
        return {
            "valid": False,
            "reason": f"{to_agent} not suitable for {task_type}",
            "suggestion": f"Consider delegating to: {', '.join(allowed_agents)}",
            "confidence": 0.0,
            "alternatives": allowed_agents
        }

    @classmethod
    def get_recommended_agent(cls, task_type: str) -> Optional[str]:
        """
        Get the most recommended agent for a task type.

        Args:
            task_type: Type of task

        Returns:
            Recommended agent name, or None if unknown task type
        """
        allowed_agents = cls.TASK_AGENT_MAP.get(task_type, [])
        if allowed_agents:
            return allowed_agents[0]  # Return first (primary) agent
        return None

    @classmethod
    def check_self_delegation(cls, from_agent: str, to_agent: str) -> Dict[str, any]:
        """
        Check if agent is delegating to itself.

        Args:
            from_agent: Source agent
            to_agent: Target agent

        Returns:
            {"is_self_delegation": bool, "warning": Optional[str]}
        """
        if from_agent == to_agent:
            return {
                "is_self_delegation": True,
                "warning": f"{from_agent} is delegating to itself - possible logic error"
            }
        return {
            "is_self_delegation": False,
            "warning": None
        }

    @classmethod
    def validate_with_history(
        cls,
        from_agent: str,
        to_agent: str,
        task_type: str,
        graph_store=None,
        min_success_rate: float = 0.7
    ) -> Dict[str, any]:
        """
        Validate delegation using both rules and historical data.

        Args:
            from_agent: Source agent
            to_agent: Target agent
            task_type: Task type
            graph_store: DelegationGraphStore instance for history lookup
            min_success_rate: Minimum acceptable historical success rate

        Returns:
            Validation result with historical context
        """
        # First, check rules-based validation
        rule_validation = cls.validate_delegation(from_agent, to_agent, task_type)

        if not graph_store:
            return rule_validation

        # Check historical success rate
        try:
            with graph_store.session() as session:
                result = session.run("""
                    MATCH (from:Agent {name: $from_agent})-[d:DELEGATES_TO]->(to:Agent {name: $to_agent})
                    WHERE d.task CONTAINS $task_type
                    WITH count(d) as total,
                         sum(CASE WHEN d.status = 'success' THEN 1 ELSE 0 END) as successes
                    RETURN total, successes,
                           CASE WHEN total > 0 THEN toFloat(successes) / total ELSE 0.0 END as success_rate
                """,
                    from_agent=from_agent,
                    to_agent=to_agent,
                    task_type=task_type
                )

                record = result.single()
                if record and record["total"] > 0:
                    success_rate = record["success_rate"]
                    total = record["total"]

                    if success_rate < min_success_rate:
                        rule_validation["valid"] = False
                        rule_validation["reason"] += f" (Historical success rate: {success_rate*100:.1f}% based on {total} delegations)"
                        rule_validation["confidence"] = success_rate
                    else:
                        rule_validation["confidence"] = success_rate
                        rule_validation["reason"] += f" (Historical success rate: {success_rate*100:.1f}%)"

        except Exception as e:
            logger.warning(f"Could not check historical data: {e}")

        return rule_validation


# Example usage
if __name__ == "__main__":
    # Example 1: Valid delegation
    result = DelegationGuardrails.validate_delegation(
        from_agent="SDET_Agent",
        to_agent="SRE_Agent",
        task_type="deploy_tests"
    )
    print(f"Valid: {result['valid']}")
    print(f"Reason: {result['reason']}")

    # Example 2: Invalid delegation
    result = DelegationGuardrails.validate_delegation(
        from_agent="Performance_Agent",
        to_agent="DevOps_Agent",
        task_type="load_test"
    )
    print(f"\nValid: {result['valid']}")
    print(f"Reason: {result['reason']}")
    print(f"Suggestion: {result['suggestion']}")

    # Example 3: Self-delegation check
    result = DelegationGuardrails.check_self_delegation(
        from_agent="SDET_Agent",
        to_agent="SDET_Agent"
    )
    print(f"\nSelf-delegation: {result['is_self_delegation']}")
    if result['warning']:
        print(f"Warning: {result['warning']}")
