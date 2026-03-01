"""Pydantic output contracts for all 8 agents.

Each model defines the REQUIRED keys that every agent.execute() must return.
Optional extension fields (CVE, legal, HIPAA, SBOM, AI Act, drift, etc.) are
typed but not required — they appear only when the corresponding scanner runs.

Usage:
    from agenticqa.contracts import validate_agent_output

    result = agent.execute(data)
    validated = validate_agent_output("QA_Assistant", result)  # raises on bad schema
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional, Type, Union

from pydantic import BaseModel, Field, model_validator


# ── QA Agent ────────────────────────────────────────────────────────────────────

class QAOutput(BaseModel):
    """Contract for QAAssistantAgent.execute() return value."""
    total_tests: int = Field(ge=0)
    passed: int = Field(ge=0)
    failed: int = Field(ge=0)
    coverage: Union[int, float] = Field(ge=0)
    recommendations: List[str] = Field(default_factory=list)
    rag_insights_used: int = Field(default=0, ge=0)

    @model_validator(mode="after")
    def passed_plus_failed_le_total(self) -> "QAOutput":
        if self.passed + self.failed > self.total_tests:
            raise ValueError(
                f"passed ({self.passed}) + failed ({self.failed}) "
                f"> total_tests ({self.total_tests})"
            )
        return self


# ── Performance Agent ───────────────────────────────────────────────────────────

class PerformanceOutput(BaseModel):
    """Contract for PerformanceAgent.execute() return value."""
    duration_ms: Union[int, float] = Field(ge=0)
    baseline_ms: Union[int, float] = Field(ge=0)
    memory_mb: Union[int, float] = Field(ge=0)
    status: str  # "optimal" or "degraded"
    regression_detected: bool
    optimizations: List[str] = Field(default_factory=list)
    rag_insights_used: int = Field(default=0, ge=0)


# ── Compliance Agent ────────────────────────────────────────────────────────────

class ComplianceOutput(BaseModel):
    """Contract for ComplianceAgent.execute() return value."""
    data_encryption: bool
    pii_protection: bool
    audit_logs: bool = False
    violations: List[Any] = Field(default_factory=list)  # str or dict
    rag_insights_used: int = Field(default=0, ge=0)

    # Optional scanner extensions
    cve_risk_score: Optional[float] = None
    reachable_cves: Optional[int] = None
    total_cves: Optional[int] = None
    legal_risk_score: Optional[float] = None
    legal_risk_findings: Optional[int] = None
    legal_critical_findings: Optional[int] = None
    hipaa_risk_score: Optional[float] = None
    hipaa_findings: Optional[int] = None
    hipaa_critical_findings: Optional[int] = None
    sbom_providers: Optional[List[str]] = None
    sbom_unique_models: Optional[int] = None
    sbom_risk_score: Optional[float] = None
    sbom_license_violations: Optional[int] = None
    ai_act_risk_category: Optional[str] = None
    ai_act_conformity_score: Optional[float] = None
    ai_act_annex_iii: Optional[Any] = None  # bool or List[str] depending on scan
    drift: Optional[Dict[str, Any]] = None

    model_config = {"extra": "allow"}


# ── DevOps Agent ────────────────────────────────────────────────────────────────

class DevOpsOutput(BaseModel):
    """Contract for DevOpsAgent.execute() return value."""
    deployment_status: str
    version: Optional[str] = None
    environment: Optional[str] = None
    health_checks: Dict[str, bool] = Field(default_factory=dict)
    rag_insights_used: int = Field(default=0, ge=0)


# ── SRE Agent ───────────────────────────────────────────────────────────────────

class SREFix(BaseModel):
    """Single lint fix applied by SRE agent."""
    rule: Optional[str] = None
    file: Optional[str] = None
    line: Optional[int] = None
    fix: Optional[str] = None
    source: Optional[str] = None

    model_config = {"extra": "allow"}


class SREOutput(BaseModel):
    """Contract for SREAgent.execute() return value."""
    total_errors: int = Field(ge=0)
    fixable_errors: int = Field(ge=0)
    fixes_applied: int = Field(ge=0)
    fix_rate: float = Field(ge=0.0, le=1.0)
    architectural_violations: int = Field(ge=0)
    architectural_violations_by_rule: Dict[str, int] = Field(default_factory=dict)
    fixes: List[Any] = Field(default_factory=list)
    status: str  # "success" or "partial"
    rag_insights_used: int = Field(default=0, ge=0)
    shell_errors: List[Any] = Field(default_factory=list)
    shell_error_count: int = Field(default=0, ge=0)

    # Optional self-healing extensions
    test_repairs: Optional[List[Dict[str, Any]]] = None
    tests_repaired: Optional[int] = None

    model_config = {"extra": "allow"}


# ── SDET Agent ──────────────────────────────────────────────────────────────────

class SDETOutput(BaseModel):
    """Contract for SDETAgent.execute() return value."""
    current_coverage: Union[int, float] = Field(ge=0)
    coverage_status: str  # "adequate" or "insufficient"
    coverage_threshold_used: int = Field(ge=0)
    gaps_identified: int = Field(ge=0)
    gaps: List[Any] = Field(default_factory=list)
    recommendations: List[str] = Field(default_factory=list)
    rag_insights_used: int = Field(default=0, ge=0)
    tests_generated: int = Field(default=0, ge=0)
    generated_test_files: List[str] = Field(default_factory=list)


# ── Fullstack Agent ─────────────────────────────────────────────────────────────

class FullstackOutput(BaseModel):
    """Contract for FullstackAgent.execute() return value."""
    feature_title: str
    category: str
    code_generated: bool
    code: Optional[str] = None
    files_created: List[str] = Field(default_factory=list)
    status: str  # "success" or "failed"
    rag_insights_used: int = Field(default=0, ge=0)


# ── Red Team Agent ──────────────────────────────────────────────────────────────

class RedTeamOutput(BaseModel):
    """Contract for RedTeamAgent.execute() return value."""
    bypass_attempts: int = Field(ge=0)
    successful_bypasses: int = Field(ge=0)
    patches_applied: int = Field(ge=0)
    proposals_generated: int = Field(ge=0)
    scanner_strength: float = Field(ge=0.0, le=1.0)
    gate_strength: float = Field(ge=0.0, le=1.0)
    vulnerabilities: List[Any] = Field(default_factory=list)
    constitutional_proposals: List[Any] = Field(default_factory=list)
    status: str  # "clean", "bypasses_found", "patched"


# ── Registry ────────────────────────────────────────────────────────────────────

AGENT_CONTRACTS: Dict[str, Type[BaseModel]] = {
    "QA_Assistant": QAOutput,
    "Performance": PerformanceOutput,
    "Compliance": ComplianceOutput,
    "DevOps": DevOpsOutput,
    "SRE": SREOutput,
    "SDET": SDETOutput,
    "Fullstack": FullstackOutput,
    "RedTeam_Agent": RedTeamOutput,
}


def validate_agent_output(agent_name: str, output: Dict[str, Any]) -> BaseModel:
    """Validate an agent's output dict against its contract.

    Returns the validated Pydantic model instance.
    Raises ``KeyError`` if agent_name is not registered,
    ``pydantic.ValidationError`` if the output violates the contract.
    """
    if agent_name not in AGENT_CONTRACTS:
        raise KeyError(f"No contract registered for agent '{agent_name}'")
    return AGENT_CONTRACTS[agent_name].model_validate(output)
