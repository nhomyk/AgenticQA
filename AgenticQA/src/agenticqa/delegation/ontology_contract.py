"""Versioned ontology contract for delegation policies."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, List

from ..collaboration.delegation import DelegationGuardrails as CollaborationGuardrails
from .guardrails import DelegationGuardrails as OntologyGuardrails


class OntologyContractError(Exception):
    """Raised when ontology contracts are invalid or incompatible."""


@dataclass(frozen=True)
class OntologyContract:
    """Serializable snapshot of runtime delegation ontology."""

    version: str
    generated_at: str
    task_agent_map: Dict[str, List[str]]
    allowed_delegations: Dict[str, List[str]]
    canonical_agents: List[str]
    checksum: str

    @classmethod
    def from_runtime(cls, version: str = "1.0.0") -> "OntologyContract":
        task_agent_map = cls._normalize_map(OntologyGuardrails.TASK_AGENT_MAP)
        allowed_delegations = cls._normalize_map(CollaborationGuardrails.ALLOWED_DELEGATIONS)
        canonical_agents = sorted(
            {
                *allowed_delegations.keys(),
                *{agent for targets in allowed_delegations.values() for agent in targets},
                *{agent for agents in task_agent_map.values() for agent in agents},
            }
        )

        payload = {
            "version": version,
            "task_agent_map": task_agent_map,
            "allowed_delegations": allowed_delegations,
            "canonical_agents": canonical_agents,
        }
        checksum = cls._checksum(payload)

        return cls(
            version=version,
            generated_at=datetime.utcnow().isoformat(),
            task_agent_map=task_agent_map,
            allowed_delegations=allowed_delegations,
            canonical_agents=canonical_agents,
            checksum=checksum,
        )

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "OntologyContract":
        required = {
            "version",
            "generated_at",
            "task_agent_map",
            "allowed_delegations",
            "canonical_agents",
            "checksum",
        }
        missing = required - set(data.keys())
        if missing:
            raise OntologyContractError(f"Missing required contract keys: {sorted(missing)}")

        contract = cls(
            version=data["version"],
            generated_at=data["generated_at"],
            task_agent_map=cls._normalize_map(data["task_agent_map"]),
            allowed_delegations=cls._normalize_map(data["allowed_delegations"]),
            canonical_agents=sorted(set(data["canonical_agents"])),
            checksum=data["checksum"],
        )
        contract.validate_checksum()
        return contract

    def to_dict(self) -> Dict[str, Any]:
        return {
            "version": self.version,
            "generated_at": self.generated_at,
            "task_agent_map": self.task_agent_map,
            "allowed_delegations": self.allowed_delegations,
            "canonical_agents": self.canonical_agents,
            "checksum": self.checksum,
        }

    def validate_checksum(self):
        payload = {
            "version": self.version,
            "task_agent_map": self.task_agent_map,
            "allowed_delegations": self.allowed_delegations,
            "canonical_agents": self.canonical_agents,
        }
        expected = self._checksum(payload)
        if expected != self.checksum:
            raise OntologyContractError(
                "Ontology checksum mismatch. Contract may be stale or tampered."
            )

    def validate_runtime_compatibility(self) -> Dict[str, Any]:
        runtime = OntologyContract.from_runtime(version=self.version)
        issues: List[str] = []

        if self.task_agent_map != runtime.task_agent_map:
            issues.append("task_agent_map differs from runtime ontology")
        if self.allowed_delegations != runtime.allowed_delegations:
            issues.append("allowed_delegations differs from runtime collaboration guardrails")
        if self.canonical_agents != runtime.canonical_agents:
            issues.append("canonical_agents differs from runtime")

        return {
            "compatible": len(issues) == 0,
            "issues": issues,
            "expected_checksum": runtime.checksum,
            "actual_checksum": self.checksum,
        }

    @staticmethod
    def _normalize_map(raw_map: Dict[str, List[str]]) -> Dict[str, List[str]]:
        return {k: sorted(set(v)) for k, v in sorted(raw_map.items(), key=lambda item: item[0])}

    @staticmethod
    def _checksum(payload: Dict[str, Any]) -> str:
        encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
        return hashlib.sha256(encoded).hexdigest()
