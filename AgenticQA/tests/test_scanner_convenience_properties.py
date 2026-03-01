"""Tests for scanner result convenience properties.

Validates the ergonomic aliases added to scanner result dataclasses:
  - ArchitectureScanResult.total_findings, category_counts, severity_counts
  - MCPScanResult.total_findings, category_counts
  - DataFlowReport.total_findings
  - AgentTrustGraph.agents, findings, has_cycles
  - InjectionScanResult.risk_score, critical_findings, total_findings
"""
import pytest
from agenticqa.security.architecture_scanner import ArchitectureScanResult, IntegrationArea
from agenticqa.security.mcp_scanner import MCPScanResult, MCPToolFinding
from agenticqa.security.data_flow_tracer import DataFlowReport, DataFlowFinding
from agenticqa.security.agent_trust_graph import AgentTrustGraph, AgentNode, AgentEdge, TrustViolation
from agenticqa.security.prompt_injection_scanner import InjectionScanResult, InjectionFinding


# ── ArchitectureScanResult ───────────────────────────────────────────────────

def _make_arch_result(n=3):
    areas = []
    cats = ["EXTERNAL_HTTP", "DATABASE", "SHELL_EXEC"]
    sevs = ["high", "high", "critical"]
    for i in range(n):
        areas.append(IntegrationArea(
            category=cats[i % len(cats)],
            source_file=f"file{i}.py",
            line_number=i + 1,
            evidence=f"snippet {i}",
            severity=sevs[i % len(sevs)],
            plain_english=f"Finding {i}",
            attack_vectors=["injection"],
            test_files=[],
        ))
    return ArchitectureScanResult(
        repo_path="/tmp/test",
        integration_areas=areas,
        attack_surface_score=50.0,
        test_coverage_confidence=30.0,
        files_scanned=10,
    )


@pytest.mark.unit
def test_arch_total_findings():
    r = _make_arch_result(5)
    assert r.total_findings == 5


@pytest.mark.unit
def test_arch_total_findings_empty():
    r = _make_arch_result(0)
    assert r.total_findings == 0


@pytest.mark.unit
def test_arch_category_counts():
    r = _make_arch_result(6)
    counts = r.category_counts
    assert counts["EXTERNAL_HTTP"] == 2
    assert counts["DATABASE"] == 2
    assert counts["SHELL_EXEC"] == 2


@pytest.mark.unit
def test_arch_severity_counts():
    r = _make_arch_result(3)
    counts = r.severity_counts
    assert counts["high"] == 2
    assert counts["critical"] == 1


# ── MCPScanResult ────────────────────────────────────────────────────────────

def _make_mcp_result(n=3):
    findings = []
    types = ["TOOL_POISONING", "SSRF_RISK", "COMMAND_INJECTION"]
    for i in range(n):
        findings.append(MCPToolFinding(
            tool_name=f"tool_{i}",
            attack_type=types[i % len(types)],
            severity="high",
            description=f"finding {i}",
            evidence=f"evidence {i}",
            source_file=f"file{i}.py",
            line_number=i + 1,
        ))
    return MCPScanResult(findings=findings, files_scanned=10, risk_score=0.5)


@pytest.mark.unit
def test_mcp_total_findings():
    r = _make_mcp_result(4)
    assert r.total_findings == 4


@pytest.mark.unit
def test_mcp_total_findings_empty():
    r = MCPScanResult()
    assert r.total_findings == 0


@pytest.mark.unit
def test_mcp_category_counts():
    r = _make_mcp_result(6)
    counts = r.category_counts
    assert counts["TOOL_POISONING"] == 2
    assert counts["SSRF_RISK"] == 2


# ── DataFlowReport ───────────────────────────────────────────────────────────

@pytest.mark.unit
def test_dataflow_total_findings():
    findings = [
        DataFlowFinding(
            finding_type="SECRET_SOURCE", severity="high",
            data_type="credential", description="cred leak",
            source_agent="AgentA", sink_agent="AgentB",
            source_file="a.py", line_number=1,
        ),
        DataFlowFinding(
            finding_type="SINK_LOGGING", severity="medium",
            data_type="credential", description="log leak",
            source_agent="AgentA", sink_agent="logger",
            source_file="b.py", line_number=5,
        ),
    ]
    r = DataFlowReport(findings=findings, files_scanned=5, risk_score=0.6)
    assert r.total_findings == 2


@pytest.mark.unit
def test_dataflow_total_findings_empty():
    r = DataFlowReport()
    assert r.total_findings == 0


# ── AgentTrustGraph ──────────────────────────────────────────────────────────

def _make_trust_graph(with_cycle=False):
    nodes = [
        AgentNode(name="AgentA", framework="langchain", source_file="a.py",
                  source_line=1, tools=["read"]),
        AgentNode(name="AgentB", framework="langchain", source_file="b.py",
                  source_line=1, tools=["write"]),
    ]
    edges = [
        AgentEdge(source="AgentA", target="AgentB", edge_type="delegation",
                  framework="langchain", source_file="a.py", source_line=5),
    ]
    violations = []
    if with_cycle:
        edges.append(AgentEdge(source="AgentB", target="AgentA", edge_type="delegation",
                               framework="langchain", source_file="b.py", source_line=10))
        violations.append(TrustViolation(
            rule_id="CIRCULAR_TRUST", severity="high",
            message="Circular trust detected", agents_involved=["AgentA", "AgentB"],
            source_file="a.py", source_line=5,
            remediation="Insert human checkpoint",
        ))
    return AgentTrustGraph(
        nodes=nodes, edges=edges, violations=violations,
        frameworks_detected=["langchain"], has_human_oversight=False, risk_score=0.5,
    )


@pytest.mark.unit
def test_trust_graph_agents_alias():
    g = _make_trust_graph()
    assert g.agents is g.nodes
    assert len(g.agents) == 2


@pytest.mark.unit
def test_trust_graph_findings_alias():
    g = _make_trust_graph(with_cycle=True)
    assert g.findings is g.violations
    assert len(g.findings) == 1


@pytest.mark.unit
def test_trust_graph_has_cycles_true():
    g = _make_trust_graph(with_cycle=True)
    assert g.has_cycles is True


@pytest.mark.unit
def test_trust_graph_has_cycles_false():
    g = _make_trust_graph(with_cycle=False)
    assert g.has_cycles is False


# ── InjectionScanResult ─────────────────────────────────────────────────────

def _make_injection_result(n=3):
    findings = []
    for i in range(n):
        findings.append(InjectionFinding(
            file=f"file{i}.py", line=i + 1,
            rule_id="PROMPT_INJECTION_SURFACE",
            severity="critical" if i == 0 else "medium",
            message=f"finding {i}",
            evidence=f"evidence {i}",
            sink="llm_prompt",
        ))
    return InjectionScanResult(findings=findings, surface_score=0.75)


@pytest.mark.unit
def test_injection_risk_score_alias():
    r = _make_injection_result()
    assert r.risk_score == r.surface_score
    assert r.risk_score == 0.75


@pytest.mark.unit
def test_injection_critical_findings():
    r = _make_injection_result(3)
    crit = r.critical_findings
    assert len(crit) == 1
    assert crit[0].severity == "critical"


@pytest.mark.unit
def test_injection_total_findings():
    r = _make_injection_result(5)
    assert r.total_findings == 5


@pytest.mark.unit
def test_injection_total_findings_empty():
    r = InjectionScanResult(findings=[], surface_score=0.0)
    assert r.total_findings == 0
