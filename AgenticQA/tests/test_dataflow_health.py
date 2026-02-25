"""
Unit tests for DataflowHealthMonitor.

All tests use injected probe functions — no network required.
"""
import json
import os
import sys
from pathlib import Path
from unittest.mock import patch, MagicMock
import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from agenticqa.monitoring.dataflow_health import (
    DataflowHealthMonitor,
    InfraNode,
    NodeResult,
    DataflowHealthReport,
    _probe_qdrant,
    _probe_weaviate,
    _probe_artifact_store,
    _build_infra_to_agents,
)


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

def _make_probe(name: str, node_type: str, healthy: bool, message: str, critical: bool = False):
    """Return a probe function that always returns a fixed NodeResult."""
    node = InfraNode(name, node_type, is_critical=critical)
    def probe():
        return NodeResult(node, healthy, 1.0, message)
    return probe


# ---------------------------------------------------------------------------
# check_all — all healthy
# ---------------------------------------------------------------------------

@pytest.mark.unit
def test_check_all_healthy():
    """When all probes succeed, report is healthy."""
    probes = {
        "qdrant": _make_probe("qdrant", "vector_store", True, "ok", critical=True),
        "weaviate": _make_probe("weaviate", "vector_store", True, "ok"),
        "neo4j": _make_probe("neo4j", "graph_db", True, "ok"),
        "artifact_store": _make_probe("artifact_store", "file_system", True, "ok", critical=True),
        "learning_metrics": _make_probe("learning_metrics", "file_system", True, "ok"),
    }
    monitor = DataflowHealthMonitor(probes=probes)
    report = monitor.check_all()
    assert report.is_healthy
    assert len(report.broken_nodes) == 0
    assert len(report.healthy_nodes) == 5


# ---------------------------------------------------------------------------
# check_all — broken critical node
# ---------------------------------------------------------------------------

@pytest.mark.unit
def test_check_all_critical_broken():
    """When a critical node is broken, report.is_healthy is False."""
    probes = {
        "qdrant": _make_probe("qdrant", "vector_store", False, "connection refused", critical=True),
        "weaviate": _make_probe("weaviate", "vector_store", True, "ok"),
        "neo4j": _make_probe("neo4j", "graph_db", True, "ok"),
        "artifact_store": _make_probe("artifact_store", "file_system", True, "ok", critical=True),
        "learning_metrics": _make_probe("learning_metrics", "file_system", True, "ok"),
    }
    monitor = DataflowHealthMonitor(probes=probes)
    report = monitor.check_all()
    assert not report.is_healthy
    assert len(report.broken_nodes) == 1
    assert report.broken_nodes[0].node.name == "qdrant"


# ---------------------------------------------------------------------------
# check_all — degraded (non-critical broken)
# ---------------------------------------------------------------------------

@pytest.mark.unit
def test_check_all_degraded_only():
    """Non-critical broken node appears in broken_nodes but is_healthy depends on overall logic."""
    probes = {
        "qdrant": _make_probe("qdrant", "vector_store", True, "ok", critical=True),
        "weaviate": _make_probe("weaviate", "vector_store", False, "version mismatch"),
        "neo4j": _make_probe("neo4j", "graph_db", True, "ok"),
        "artifact_store": _make_probe("artifact_store", "file_system", True, "ok", critical=True),
        "learning_metrics": _make_probe("learning_metrics", "file_system", True, "ok"),
    }
    monitor = DataflowHealthMonitor(probes=probes)
    report = monitor.check_all()
    assert not report.is_healthy  # any broken node → not healthy
    broken_names = [r.node.name for r in report.broken_nodes]
    assert "weaviate" in broken_names
    assert "qdrant" not in broken_names


# ---------------------------------------------------------------------------
# affected_agents mapping
# ---------------------------------------------------------------------------

@pytest.mark.unit
def test_affected_agents_includes_all_for_qdrant():
    """When Qdrant is down, all 8 agents appear in affected_agents."""
    probes = {
        "qdrant": _make_probe("qdrant", "vector_store", False, "down", critical=True),
        "weaviate": _make_probe("weaviate", "vector_store", True, "ok"),
        "neo4j": _make_probe("neo4j", "graph_db", True, "ok"),
        "artifact_store": _make_probe("artifact_store", "file_system", True, "ok", critical=True),
        "learning_metrics": _make_probe("learning_metrics", "file_system", True, "ok"),
    }
    monitor = DataflowHealthMonitor(probes=probes)
    report = monitor.check_all()
    affected = report.affected_agents.get("qdrant", [])
    # All 8 agents depend on qdrant
    assert len(affected) == 8


@pytest.mark.unit
def test_affected_agents_neo4j_excludes_non_graph_agents():
    """When Neo4j is down, agents without GraphRAG are NOT listed."""
    infra_to_agents = _build_infra_to_agents()
    neo4j_agents = set(infra_to_agents.get("neo4j", []))
    # Performance_Agent and SRE_Agent do not use Neo4j
    assert "Performance_Agent" not in neo4j_agents
    assert "SRE_Agent" not in neo4j_agents
    # Delegation-capable agents DO use it
    assert "Compliance_Agent" in neo4j_agents
    assert "SDET_Agent" in neo4j_agents


# ---------------------------------------------------------------------------
# check_agent
# ---------------------------------------------------------------------------

@pytest.mark.unit
def test_check_agent_healthy():
    """check_agent returns is_healthy=True when all deps pass."""
    probes = {
        "qdrant": _make_probe("qdrant", "vector_store", True, "ok", critical=True),
        "weaviate": _make_probe("weaviate", "vector_store", True, "ok"),
        "neo4j": _make_probe("neo4j", "graph_db", True, "ok"),
        "artifact_store": _make_probe("artifact_store", "file_system", True, "ok", critical=True),
        "learning_metrics": _make_probe("learning_metrics", "file_system", True, "ok"),
    }
    monitor = DataflowHealthMonitor(probes=probes)
    result = monitor.check_agent("SRE_Agent")
    assert result["is_healthy"]
    assert "qdrant" in result["dependencies"]
    assert "artifact_store" in result["dependencies"]
    # SRE_Agent does not use Neo4j
    assert "neo4j" not in result["dependencies"]


@pytest.mark.unit
def test_check_agent_reports_broken_dep():
    """check_agent is_healthy=False when a dependency fails."""
    probes = {
        "qdrant": _make_probe("qdrant", "vector_store", False, "down", critical=True),
        "weaviate": _make_probe("weaviate", "vector_store", True, "ok"),
        "artifact_store": _make_probe("artifact_store", "file_system", True, "ok", critical=True),
        "learning_metrics": _make_probe("learning_metrics", "file_system", True, "ok"),
    }
    monitor = DataflowHealthMonitor(probes=probes)
    result = monitor.check_agent("QA_Assistant")
    assert not result["is_healthy"]
    assert not result["dependencies"]["qdrant"]["healthy"]


# ---------------------------------------------------------------------------
# probe_raises_does_not_crash_monitor
# ---------------------------------------------------------------------------

@pytest.mark.unit
def test_crashing_probe_captured_as_broken():
    """A probe that raises an exception is recorded as broken, not propagated."""
    def bad_probe():
        raise RuntimeError("explode")

    probes = {
        "qdrant": bad_probe,
        "artifact_store": _make_probe("artifact_store", "file_system", True, "ok", critical=True),
    }
    monitor = DataflowHealthMonitor(probes=probes)
    report = monitor.check_all()  # must not raise
    broken_names = [r.node.name for r in report.broken_nodes]
    assert "qdrant" in broken_names


# ---------------------------------------------------------------------------
# to_dict serialization
# ---------------------------------------------------------------------------

@pytest.mark.unit
def test_report_to_dict_is_json_serializable():
    """DataflowHealthReport.to_dict() produces JSON-serializable output."""
    probes = {
        "qdrant": _make_probe("qdrant", "vector_store", True, "ok", critical=True),
        "artifact_store": _make_probe("artifact_store", "file_system", False, "error", critical=True),
    }
    monitor = DataflowHealthMonitor(probes=probes)
    report = monitor.check_all()
    d = report.to_dict()
    # Must not raise
    s = json.dumps(d)
    parsed = json.loads(s)
    assert "broken_nodes" in parsed
    assert parsed["broken_nodes"][0]["name"] == "artifact_store"


# ---------------------------------------------------------------------------
# _probe_artifact_store (real filesystem, uses tmp_path)
# ---------------------------------------------------------------------------

@pytest.mark.unit
def test_probe_artifact_store_writable(tmp_path):
    """_probe_artifact_store returns healthy for a writable directory."""
    with patch.dict(os.environ, {"ARTIFACT_STORE_PATH": str(tmp_path)}):
        result = _probe_artifact_store()
    assert result.healthy


@pytest.mark.unit
def test_probe_artifact_store_counts_artifacts(tmp_path):
    """_probe_artifact_store reads artifact count from index.json."""
    index = {"artifacts": {"id1": {}, "id2": {}, "id3": {}}, "last_updated": "now"}
    (tmp_path / "index.json").write_text(json.dumps(index))
    with patch.dict(os.environ, {"ARTIFACT_STORE_PATH": str(tmp_path)}):
        result = _probe_artifact_store()
    assert result.healthy
    assert "3 artifacts" in result.message


# ---------------------------------------------------------------------------
# _probe_qdrant (mocked HTTP)
# ---------------------------------------------------------------------------

@pytest.mark.unit
def test_probe_qdrant_healthy():
    """_probe_qdrant returns healthy when /healthz succeeds."""
    with patch("agenticqa.monitoring.dataflow_health._http_get", return_value=(True, 5.0, "healthz check passed")), \
         patch.dict(os.environ, {"QDRANT_URL": "http://localhost:6333"}):
        result = _probe_qdrant()
    assert result.healthy
    assert result.node.is_critical


@pytest.mark.unit
def test_probe_qdrant_unreachable():
    """_probe_qdrant returns unhealthy with remediation hint."""
    with patch("agenticqa.monitoring.dataflow_health._http_get", return_value=(False, 3000.0, "Connection refused")), \
         patch.dict(os.environ, {"QDRANT_URL": "http://localhost:9999"}):
        result = _probe_qdrant()
    assert not result.healthy
    assert "qdrant" in result.detail.lower()


# ---------------------------------------------------------------------------
# _probe_weaviate version check
# ---------------------------------------------------------------------------

@pytest.mark.unit
def test_probe_weaviate_version_too_old():
    """Weaviate version < 1.27.0 is flagged as broken with the exact error message."""
    def mock_http_get(url, timeout=4.0):
        if "ready" in url:
            return True, 2.0, "ok"
        return True, 1.0, ""  # meta endpoint — triggers _fetch_full_body

    with patch("agenticqa.monitoring.dataflow_health._http_get", side_effect=mock_http_get), \
         patch("agenticqa.monitoring.dataflow_health._fetch_full_body",
               return_value='{"version": "1.24.8"}'), \
         patch.dict(os.environ, {"WEAVIATE_HOST": "localhost", "WEAVIATE_PORT": "8080"}):
        result = _probe_weaviate()
    assert not result.healthy
    assert "1.24.8" in result.message
    assert "1.27.0" in result.message
    assert "silently discarded" in result.message


@pytest.mark.unit
def test_probe_weaviate_version_ok():
    """Weaviate version 1.27.0 is reported as healthy."""
    def mock_http_get(url, timeout=4.0):
        if "ready" in url:
            return True, 2.0, "ok"
        return True, 1.0, ""

    with patch("agenticqa.monitoring.dataflow_health._http_get", side_effect=mock_http_get), \
         patch("agenticqa.monitoring.dataflow_health._fetch_full_body",
               return_value='{"version": "1.27.0"}'), \
         patch.dict(os.environ, {"WEAVIATE_HOST": "localhost", "WEAVIATE_PORT": "8080"}):
        result = _probe_weaviate()
    assert result.healthy
    assert "1.27.0" in result.message
