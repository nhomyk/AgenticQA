"""Policy-as-code engine for delegation governance."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Dict, Optional, Set


@dataclass(frozen=True)
class PolicyDecision:
    allowed: bool
    reason: str
    requires_approval: bool = False
    tags: tuple[str, ...] = ()


@dataclass
class DelegationPolicyEngine:
    """Evaluates delegation actions against declarative policy rules."""

    max_total_delegations: Optional[int] = None
    approval_required_task_types: Set[str] = field(default_factory=set)
    high_risk_task_types: Set[str] = field(default_factory=lambda: {"deploy", "rollback", "infrastructure"})
    approval_callback: Optional[Callable[[Dict[str, Any]], bool]] = None

    def evaluate(self, context: Dict[str, Any]) -> PolicyDecision:
        total_delegations = int(context.get("total_delegations", 0))
        task_type = str(context.get("task_type", "unknown"))

        if self.max_total_delegations is not None and total_delegations >= self.max_total_delegations:
            return PolicyDecision(
                allowed=False,
                reason=(
                    f"Delegation policy blocked request: budget exceeded "
                    f"({total_delegations}/{self.max_total_delegations})"
                ),
                tags=("budget",),
            )

        needs_approval = (
            task_type in self.approval_required_task_types
            or task_type in self.high_risk_task_types
        )
        if needs_approval:
            approved = bool(context.get("approved", False))
            if not approved and self.approval_callback:
                approved = bool(self.approval_callback(context))

            if not approved:
                return PolicyDecision(
                    allowed=False,
                    reason=(
                        f"Delegation policy requires approval for task_type='{task_type}'"
                    ),
                    requires_approval=True,
                    tags=("approval", "high-risk" if task_type in self.high_risk_task_types else "policy"),
                )

        return PolicyDecision(allowed=True, reason="allowed", tags=("pass",))

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "DelegationPolicyEngine":
        return cls(
            max_total_delegations=data.get("max_total_delegations"),
            approval_required_task_types=set(data.get("approval_required_task_types", [])),
            high_risk_task_types=set(data.get("high_risk_task_types", ["deploy", "rollback", "infrastructure"])),
        )
