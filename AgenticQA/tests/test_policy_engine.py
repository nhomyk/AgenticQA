"""Tests for policy-as-code delegation governance."""

import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from agenticqa.collaboration import (
    AgentRegistry,
    ApprovalRequiredError,
    DelegationBudgetExceededError,
)
from agenticqa.policy import DelegationPolicyEngine


class DummyAgent:
    def __init__(self, name: str):
        self.agent_name = name
        self.agent_registry = None

    def execute(self, task):
        return {"status": "success", "agent": self.agent_name, "task": task}


def test_budget_policy_blocks_excess_delegations():
    policy = DelegationPolicyEngine(max_total_delegations=1, high_risk_task_types=set())
    registry = AgentRegistry(policy_engine=policy)

    src = DummyAgent("SDET_Agent")
    dst = DummyAgent("SRE_Agent")
    registry.register_agent(src)
    registry.register_agent(dst)
    registry.reset_for_new_request("SDET_Agent")

    registry.delegate_task("SDET_Agent", "SRE_Agent", {"task_type": "generate_tests"})

    with pytest.raises(DelegationBudgetExceededError):
        registry.delegate_task("SDET_Agent", "SRE_Agent", {"task_type": "generate_tests"})


def test_approval_policy_blocks_until_approved():
    policy = DelegationPolicyEngine(
        approval_required_task_types={"deploy_tests"},
        high_risk_task_types=set(),
    )
    registry = AgentRegistry(policy_engine=policy)

    src = DummyAgent("SDET_Agent")
    dst = DummyAgent("SRE_Agent")
    registry.register_agent(src)
    registry.register_agent(dst)
    registry.reset_for_new_request("SDET_Agent")

    with pytest.raises(ApprovalRequiredError):
        registry.delegate_task("SDET_Agent", "SRE_Agent", {"task_type": "deploy_tests"})

    result = registry.delegate_task(
        "SDET_Agent",
        "SRE_Agent",
        {"task_type": "deploy_tests", "approved": True},
    )
    assert result["status"] == "success"


def test_callback_can_grant_approval():
    policy = DelegationPolicyEngine(
        approval_required_task_types={"deploy"},
        high_risk_task_types=set(),
        approval_callback=lambda ctx: ctx.get("from_agent") == "SDET_Agent",
    )
    registry = AgentRegistry(policy_engine=policy)

    src = DummyAgent("SDET_Agent")
    dst = DummyAgent("SRE_Agent")
    registry.register_agent(src)
    registry.register_agent(dst)

    result = registry.delegate_task("SDET_Agent", "SRE_Agent", {"task_type": "deploy"})
    assert result["status"] == "success"


def test_registry_configure_governance_gates_helper():
    registry = AgentRegistry()
    registry.configure_governance_gates(max_total_delegations=1, approval_required_task_types={"deploy_tests"})

    src = DummyAgent("SDET_Agent")
    dst = DummyAgent("SRE_Agent")
    registry.register_agent(src)
    registry.register_agent(dst)

    with pytest.raises(ApprovalRequiredError):
        registry.delegate_task("SDET_Agent", "SRE_Agent", {"task_type": "deploy_tests"})

    registry.delegate_task(
        "SDET_Agent",
        "SRE_Agent",
        {"task_type": "generate_tests", "approved": True},
    )
    with pytest.raises(DelegationBudgetExceededError):
        registry.delegate_task(
            "SDET_Agent",
            "SRE_Agent",
            {"task_type": "generate_tests", "approved": True},
        )
