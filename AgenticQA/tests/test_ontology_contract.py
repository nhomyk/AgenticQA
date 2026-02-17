"""Tests for ontology contract versioning and compatibility checks."""

import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from agenticqa.delegation.ontology_contract import OntologyContract, OntologyContractError


def test_contract_from_runtime_is_compatible():
    contract = OntologyContract.from_runtime(version="1.2.0")
    result = contract.validate_runtime_compatibility()

    assert result["compatible"] is True
    assert result["issues"] == []


def test_contract_detects_tampering():
    contract = OntologyContract.from_runtime(version="1.2.0")
    payload = contract.to_dict()
    payload["task_agent_map"]["deploy"] = ["Compliance_Agent"]

    with pytest.raises(OntologyContractError):
        OntologyContract.from_dict(payload)


def test_contract_reports_drift_without_raising():
    contract = OntologyContract.from_runtime(version="1.2.0")
    drifted = contract.to_dict()
    drifted["checksum"] = contract.checksum
    drifted["canonical_agents"] = sorted(contract.canonical_agents + ["Synthetic_Agent"])

    # Build object directly to simulate stale persisted contract loaded from trusted storage.
    stale = OntologyContract(
        version=drifted["version"],
        generated_at=drifted["generated_at"],
        task_agent_map=drifted["task_agent_map"],
        allowed_delegations=drifted["allowed_delegations"],
        canonical_agents=drifted["canonical_agents"],
        checksum=drifted["checksum"],
    )

    result = stale.validate_runtime_compatibility()
    assert result["compatible"] is False
    assert "canonical_agents differs from runtime" in result["issues"]
