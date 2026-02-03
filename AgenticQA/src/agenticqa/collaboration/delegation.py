"""Delegation system with guardrails for safe agent collaboration"""

from typing import Dict, List, Set, Optional
from datetime import datetime


class DelegationError(Exception):
    """Base exception for delegation errors"""

    pass


class CircularDelegationError(DelegationError):
    """Raised when circular delegation is detected"""

    pass


class MaxDelegationDepthError(DelegationError):
    """Raised when delegation chain exceeds maximum depth"""

    pass


class DelegationBudgetExceededError(DelegationError):
    """Raised when delegation budget is exceeded"""

    pass


class UnauthorizedDelegationError(DelegationError):
    """Raised when agent tries to delegate to unauthorized agent"""

    pass


class DelegationGuardrails:
    """
    Enforces safety rules for agent delegation to prevent infinite loops,
    runaway costs, and unauthorized collaborations.

    Conservative whitelist approach: Only explicitly allowed delegations are permitted.
    """

    # Maximum delegation chain depth (prevents infinite recursion)
    MAX_DEPTH = 3

    # Maximum total delegations per root request (prevents cost explosion)
    MAX_TOTAL_DELEGATIONS = 5

    # Timeout per delegation in seconds
    TIMEOUT_PER_DELEGATION = 30

    # Whitelisted delegation paths (source_agent -> allowed_targets)
    # Conservative start: Only high-value, low-risk delegations
    ALLOWED_DELEGATIONS: Dict[str, List[str]] = {
        "SDET_Agent": ["SRE_Agent"],  # SDET can delegate test generation to SRE
        "Fullstack_Agent": ["Compliance_Agent"],  # Fullstack can validate code with Compliance
        "Compliance_Agent": ["DevOps_Agent"],  # Compliance can consult DevOps on deployment
        "SRE_Agent": [],  # SRE can't delegate (prevents loops)
        "DevOps_Agent": [],  # DevOps can't delegate (prevents loops)
        "QA_Assistant": [],  # QA doesn't delegate (analysis only)
        "Performance_Agent": [],  # Performance doesn't delegate (analysis only)
    }

    def __init__(self):
        self.delegation_counts: Dict[str, int] = {}
        self.start_time: Optional[datetime] = None

    def reset(self):
        """Reset guardrail state for new request"""
        self.delegation_counts = {}
        self.start_time = datetime.utcnow()

    def can_delegate(
        self, from_agent: str, to_agent: str, current_depth: int, delegation_stack: List[str]
    ) -> tuple[bool, Optional[str]]:
        """
        Check if delegation is allowed.

        Returns:
            (allowed, reason_if_not_allowed)
        """
        # Check depth limit
        if current_depth >= self.MAX_DEPTH:
            return False, f"Max delegation depth {self.MAX_DEPTH} exceeded"

        # Check circular dependency
        if to_agent in delegation_stack:
            chain = " -> ".join(delegation_stack + [to_agent])
            return False, f"Circular delegation detected: {chain}"

        # Check total delegation budget
        total_delegations = sum(self.delegation_counts.values())
        if total_delegations >= self.MAX_TOTAL_DELEGATIONS:
            return False, f"Max total delegations {self.MAX_TOTAL_DELEGATIONS} exceeded"

        # Check whitelist
        allowed_targets = self.ALLOWED_DELEGATIONS.get(from_agent, [])
        if to_agent not in allowed_targets:
            return (
                False,
                f"{from_agent} not authorized to delegate to {to_agent}. Allowed: {allowed_targets}",
            )

        return True, None

    def record_delegation(self, from_agent: str, to_agent: str):
        """Record a delegation for budget tracking"""
        key = f"{from_agent}->{to_agent}"
        self.delegation_counts[key] = self.delegation_counts.get(key, 0) + 1

    def get_delegation_stats(self) -> Dict:
        """Get delegation statistics for monitoring"""
        return {
            "total_delegations": sum(self.delegation_counts.values()),
            "delegation_breakdown": self.delegation_counts.copy(),
            "max_allowed": self.MAX_TOTAL_DELEGATIONS,
        }
