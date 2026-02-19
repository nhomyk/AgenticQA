"""Prompt Ops orchestration for collaborative code generation.

Uses the existing Fullstack agent as the primary code author and coordinates
validation/review passes with specialized agents through delegation guardrails.
"""

from __future__ import annotations

from typing import Any, Dict, Optional


class PromptOpsOrchestrator:
    """Coordinate prompt-driven code generation with multi-agent collaboration."""

    def __init__(self):
        self.registry = None
        self.fullstack = None
        self.compliance = None
        self.devops = None
        self.sdet = None
        self._init_agents()

    def _init_agents(self) -> None:
        try:
            try:
                from src.agents import ComplianceAgent, DevOpsAgent, FullstackAgent, SDETAgent  # type: ignore
                from src.agenticqa.collaboration import AgentRegistry  # type: ignore
            except Exception:
                from agents import ComplianceAgent, DevOpsAgent, FullstackAgent, SDETAgent  # type: ignore
                from agenticqa.collaboration import AgentRegistry  # type: ignore

            self.fullstack = FullstackAgent()
            self.compliance = ComplianceAgent()
            self.devops = DevOpsAgent()
            self.sdet = SDETAgent()

            self.registry = AgentRegistry(enable_delegation=True)
            self.registry.configure_governance_gates(max_total_delegations=6)
            for agent in (self.fullstack, self.compliance, self.devops, self.sdet):
                self.registry.register_agent(agent)
        except Exception:
            # Graceful degradation: caller should fallback to direct generation
            self.registry = None

    def run(self, request: Dict[str, Any], feature_request: Dict[str, str]) -> Dict[str, Any]:
        if not self.fullstack:
            raise RuntimeError("prompt_ops_orchestrator_unavailable")

        if self.registry:
            self.registry.reset_for_new_request(root_agent="Fullstack_Agent")

        generation = self.fullstack.execute(feature_request)

        collaboration: Dict[str, Any] = {}
        routing_explanations: Dict[str, Any] = {}
        metadata = request.get("metadata") or {}

        compliance_payload = {
            "task_type": "security_review",
            "context": request.get("prompt", ""),
            "regulations": metadata.get("regulations", ["baseline_security"]),
            "encrypted": bool(metadata.get("encrypted", True)),
            "pii_masked": bool(metadata.get("pii_masked", True)),
            "audit_enabled": bool(metadata.get("audit_enabled", True)),
        }
        collaboration["compliance"] = self._safe_delegate(
            source=self.fullstack,
            target_agent="Compliance_Agent",
            task=compliance_payload,
        )
        routing_explanations["compliance"] = {
            "from": "Fullstack_Agent",
            "to": "Compliance_Agent",
            "why": "Security/compliance validation before merge/push",
            "signals": {
                "regulations": compliance_payload.get("regulations", []),
                "has_pii": not compliance_payload.get("pii_masked", True),
            },
        }

        sdet_payload = {
            "task_type": "coverage_review",
            "coverage_percent": int(metadata.get("coverage_percent", 80)),
            "uncovered_files": metadata.get("uncovered_files", []),
            "test_type": metadata.get("test_type", "unit"),
        }
        collaboration["sdet"] = self._safe_delegate(
            source=self.fullstack,
            target_agent="SDET_Agent",
            task=sdet_payload,
        )
        routing_explanations["sdet"] = {
            "from": "Fullstack_Agent",
            "to": "SDET_Agent",
            "why": "Coverage and test gap validation for generated changes",
            "signals": {
                "coverage_percent": sdet_payload.get("coverage_percent"),
                "uncovered_files_count": len(sdet_payload.get("uncovered_files", [])),
            },
        }

        devops_payload = {
            "task_type": "deploy_readiness",
            "message": request.get("prompt", "")[:220],
            "version": f"workflow-{request.get('id', 'unknown')}",
            "environment": metadata.get("environment", "ci"),
        }
        if self.compliance:
            collaboration["devops"] = self._safe_delegate(
                source=self.compliance,
                target_agent="DevOps_Agent",
                task=devops_payload,
            )
            routing_explanations["devops"] = {
                "from": "Compliance_Agent",
                "to": "DevOps_Agent",
                "why": "Deployment readiness and runtime health validation",
                "signals": {
                    "environment": devops_payload.get("environment"),
                    "task_type": devops_payload.get("task_type"),
                },
            }

        quality_gate = self._build_quality_gate(collaboration)
        ontology = {
            "author_agent": "Fullstack_Agent",
            "review_agents": ["Compliance_Agent", "SDET_Agent", "DevOps_Agent"],
            "delegation_mode": "guardrailed",
            "learning_mode": "hybrid_rag_and_structured_artifacts",
            "routing_explanations": routing_explanations,
        }

        delegation_summary = self.registry.get_delegation_summary() if self.registry else {}

        return {
            "feature_request": feature_request,
            "generation": generation,
            "collaboration": collaboration,
            "quality_gate": quality_gate,
            "ontology": ontology,
            "delegation_summary": delegation_summary,
        }

    def _safe_delegate(self, source: Any, target_agent: str, task: Dict[str, Any]) -> Dict[str, Any]:
        try:
            return source.delegate_to_agent(target_agent, task)
        except Exception as exc:
            return {
                "status": "error",
                "error": str(exc),
                "target_agent": target_agent,
            }

    def _build_quality_gate(self, collaboration: Dict[str, Any]) -> Dict[str, Any]:
        compliance = collaboration.get("compliance") or {}
        sdet = collaboration.get("sdet") or {}

        violations = compliance.get("violations") or []
        coverage_status = sdet.get("coverage_status", "unknown")

        blockers = []
        if violations:
            blockers.append("compliance_violations")

        return {
            "passed": len(blockers) == 0,
            "blockers": blockers,
            "coverage_status": coverage_status,
            "violations_count": len(violations),
        }
