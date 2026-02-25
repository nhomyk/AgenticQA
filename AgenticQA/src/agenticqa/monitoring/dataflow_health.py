"""
DataflowHealthMonitor

Links the agent ontology graph to live infrastructure and alerts when any
dependency in the data pipeline is broken.

Problem it solves:
    When Weaviate 1.24.8 silently rejected connections (Python client requires
    1.27.0+), all RAG writes were discarded with no alert.  This monitor
    detects exactly that scenario — and every analogous failure — before or
    during a CI run.

Usage:
    # CLI (human-readable):
    python -m agenticqa.monitoring.dataflow_health

    # Programmatic:
    from agenticqa.monitoring.dataflow_health import DataflowHealthMonitor
    report = DataflowHealthMonitor().check_all()
    if not report.is_healthy:
        for break_event in report.broken_links:
            print(break_event)
"""

from __future__ import annotations

import os
import json
import socket
import urllib.request
import urllib.error
import subprocess
import time
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------

@dataclass
class InfraNode:
    """A single infrastructure component the agents depend on."""
    name: str          # "qdrant", "weaviate", "neo4j", "artifact_store", ...
    node_type: str     # "vector_store" | "graph_db" | "relational_db" | "file_system"
    is_critical: bool  # False → degraded; True → blocking


@dataclass
class AgentLink:
    """A directed dependency: agent_name depends on infra_node_name."""
    agent_name: str
    infra_node: str
    purpose: str       # human-readable reason (e.g. "RAG retrieval")


@dataclass
class NodeResult:
    """Result of probing one infrastructure node."""
    node: InfraNode
    healthy: bool
    latency_ms: float
    message: str
    detail: Optional[str] = None  # extra context (e.g. version string)


@dataclass
class DataflowHealthReport:
    """Full health report produced by DataflowHealthMonitor.check_all()."""
    timestamp: str
    is_healthy: bool
    healthy_nodes: List[NodeResult]
    broken_nodes: List[NodeResult]
    # For each broken node: which agents are impacted and in what way
    affected_agents: Dict[str, List[str]]  # infra_name -> [agent_name, ...]
    summary: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "timestamp": self.timestamp,
            "is_healthy": self.is_healthy,
            "healthy_nodes": [
                {"name": r.node.name, "latency_ms": r.latency_ms, "message": r.message}
                for r in self.healthy_nodes
            ],
            "broken_nodes": [
                {
                    "name": r.node.name,
                    "node_type": r.node.node_type,
                    "is_critical": r.node.is_critical,
                    "message": r.message,
                    "detail": r.detail,
                    "affected_agents": self.affected_agents.get(r.node.name, []),
                }
                for r in self.broken_nodes
            ],
            "summary": self.summary,
        }


# ---------------------------------------------------------------------------
# Probe helpers
# ---------------------------------------------------------------------------

def _http_get(url: str, timeout: float = 4.0) -> Tuple[bool, float, str]:
    """Return (ok, latency_ms, message)."""
    t0 = time.monotonic()
    try:
        with urllib.request.urlopen(url, timeout=timeout) as resp:  # noqa: S310
            body = resp.read(512).decode("utf-8", errors="replace")
            latency_ms = (time.monotonic() - t0) * 1000
            return True, latency_ms, body[:120]
    except urllib.error.HTTPError as e:
        latency_ms = (time.monotonic() - t0) * 1000
        return False, latency_ms, f"HTTP {e.code}: {e.reason}"
    except Exception as e:
        latency_ms = (time.monotonic() - t0) * 1000
        return False, latency_ms, str(e)


def _tcp_connect(host: str, port: int, timeout: float = 3.0) -> Tuple[bool, float, str]:
    """Return (ok, latency_ms, message)."""
    t0 = time.monotonic()
    try:
        with socket.create_connection((host, port), timeout=timeout):
            latency_ms = (time.monotonic() - t0) * 1000
            return True, latency_ms, f"TCP {host}:{port} open"
    except Exception as e:
        latency_ms = (time.monotonic() - t0) * 1000
        return False, latency_ms, str(e)


# ---------------------------------------------------------------------------
# Individual node probes
# ---------------------------------------------------------------------------

def _probe_qdrant() -> NodeResult:
    node = InfraNode("qdrant", "vector_store", is_critical=True)
    url = os.getenv("QDRANT_URL", "http://localhost:6333")
    ok, ms, msg = _http_get(f"{url.rstrip('/')}/healthz")
    if ok:
        return NodeResult(node, True, ms, "Qdrant healthy", detail=url)
    return NodeResult(node, False, ms,
                      f"Qdrant unreachable at {url}: {msg}",
                      detail=f"Set QDRANT_URL or start: docker run -p 6333:6333 qdrant/qdrant:v1.9.0")


def _probe_weaviate() -> NodeResult:
    node = InfraNode("weaviate", "vector_store", is_critical=False)
    host = os.getenv("WEAVIATE_HOST", "localhost")
    port = int(os.getenv("WEAVIATE_PORT", "8080"))

    # Only probe if not a cloud host (no dot in plain localhost)
    if "." in host and not host.startswith("localhost"):
        # Cloud / custom endpoint — TCP check only
        ok, ms, msg = _tcp_connect(host, 443 if "https" in host else port)
        if ok:
            return NodeResult(node, True, ms, f"Weaviate cloud reachable at {host}", detail=host)
        return NodeResult(node, False, ms, f"Weaviate cloud unreachable at {host}: {msg}")

    url = f"http://{host}:{port}"
    ok_ready, ms, _ = _http_get(f"{url}/v1/.well-known/ready")
    if not ok_ready:
        return NodeResult(node, False, ms,
                          f"Weaviate unreachable at {url}",
                          detail="docker compose -f docker-compose.weaviate.yml up -d weaviate")

    # Version check — the silent killer
    ok_meta, ms2, _ = _http_get(f"{url}/v1/meta")
    if ok_meta:
        try:
            meta = json.loads(_fetch_full_body(f"{url}/v1/meta"))
            version = meta.get("version", "unknown")
        except Exception:
            version = "unknown"

        # weaviate-client v4 requires >= 1.27.0
        if version != "unknown":
            try:
                parts = [int(x) for x in version.split(".")[:2]]
                if parts < [1, 27]:
                    return NodeResult(
                        node, False, ms + ms2,
                        f"Weaviate version {version} is incompatible — Python client requires >=1.27.0. "
                        "RAG writes will be silently discarded.",
                        detail=f"Upgrade: update docker-compose.weaviate.yml image to semitechnologies/weaviate:1.27.0"
                    )
            except (ValueError, IndexError):
                pass
        return NodeResult(node, True, ms, f"Weaviate {version} healthy at {url}", detail=url)

    return NodeResult(node, True, ms, f"Weaviate ready at {url} (meta unavailable)", detail=url)


def _fetch_full_body(url: str, timeout: float = 3.0) -> str:
    try:
        with urllib.request.urlopen(url, timeout=timeout) as resp:  # noqa: S310
            return resp.read(2048).decode("utf-8", errors="replace")
    except Exception:
        return ""


def _probe_neo4j() -> NodeResult:
    node = InfraNode("neo4j", "graph_db", is_critical=False)
    host = os.getenv("NEO4J_HOST", "localhost")
    bolt_port = int(os.getenv("NEO4J_BOLT_PORT", "7687"))
    http_port = int(os.getenv("NEO4J_HTTP_PORT", "7474"))

    ok_bolt, ms, msg = _tcp_connect(host, bolt_port)
    if ok_bolt:
        return NodeResult(node, True, ms, f"Neo4j Bolt reachable at {host}:{bolt_port}")
    # Try HTTP as fallback
    ok_http, ms2, _ = _http_get(f"http://{host}:{http_port}")
    if ok_http:
        return NodeResult(node, True, ms2, f"Neo4j HTTP reachable at {host}:{http_port} (Bolt unavailable)")
    return NodeResult(node, False, ms,
                      f"Neo4j unreachable (Bolt {host}:{bolt_port}, HTTP {host}:{http_port}): {msg}",
                      detail="docker compose -f docker-compose.weaviate.yml up -d neo4j")


def _probe_artifact_store() -> NodeResult:
    node = InfraNode("artifact_store", "file_system", is_critical=True)
    store_path = os.getenv("ARTIFACT_STORE_PATH", ".test-artifact-store")
    p = Path(store_path)
    t0 = time.monotonic()
    try:
        if not p.exists():
            p.mkdir(parents=True, exist_ok=True)
        # Check writable by touching a probe file
        probe = p / ".health_probe"
        probe.write_text("ok")
        probe.unlink()
        ms = (time.monotonic() - t0) * 1000
        # Count artifacts — store uses index.json with {"artifacts": {...}, ...}
        count = 0
        for index_name in ("index.json", "master_index.json"):
            index_path = p / index_name
            if index_path.exists():
                try:
                    raw = json.loads(index_path.read_text())
                    if isinstance(raw, dict) and "artifacts" in raw:
                        count = len(raw["artifacts"])
                    elif isinstance(raw, dict):
                        count = len(raw)
                    else:
                        count = len(raw)
                except Exception:
                    count = -1
                break
        return NodeResult(node, True, ms, f"Artifact store writable ({count} artifacts)", detail=str(p.resolve()))
    except Exception as e:
        ms = (time.monotonic() - t0) * 1000
        return NodeResult(node, False, ms, f"Artifact store not writable: {e}",
                          detail=f"Check permissions on {p.resolve()}")


def _probe_learning_metrics() -> NodeResult:
    node = InfraNode("learning_metrics", "file_system", is_critical=False)
    metrics_path = Path.home() / ".agenticqa" / "metrics_history.jsonl"
    t0 = time.monotonic()
    try:
        metrics_path.parent.mkdir(parents=True, exist_ok=True)
        # Try to append a zero-byte write
        with metrics_path.open("a") as f:
            pass
        ms = (time.monotonic() - t0) * 1000
        lines = 0
        if metrics_path.exists():
            lines = sum(1 for _ in metrics_path.open())
        return NodeResult(node, True, ms, f"Learning metrics store writable ({lines} snapshots)",
                          detail=str(metrics_path))
    except Exception as e:
        ms = (time.monotonic() - t0) * 1000
        return NodeResult(node, False, ms, f"Learning metrics not writable: {e}",
                          detail=str(metrics_path))


# ---------------------------------------------------------------------------
# Ontology-derived agent → infra links
# ---------------------------------------------------------------------------

# All 8 agents depend on these infrastructure nodes
_UNIVERSAL_LINKS: List[Tuple[str, str]] = [
    ("artifact_store", "stores execution artifacts for learning loop"),
    ("learning_metrics", "records EWMA metrics snapshots"),
]

# Agents that use RAG (all of them, but vector store is the key dependency)
_RAG_LINKS: List[Tuple[str, str]] = [
    ("qdrant", "primary vector store for RAG retrieval/ingestion"),
    ("weaviate", "secondary vector store for dual-write"),
]

# Agents that use GraphRAG / delegation store
_GRAPH_LINKS: List[Tuple[str, str]] = [
    ("neo4j", "GraphRAG delegation store — agent collaboration graph"),
]

# Per-agent link table: agent_name -> [(infra_node, purpose), ...]
_AGENT_INFRA: Dict[str, List[Tuple[str, str]]] = {
    "QA_Assistant": _UNIVERSAL_LINKS + _RAG_LINKS,
    "Performance_Agent": _UNIVERSAL_LINKS + _RAG_LINKS,
    "Compliance_Agent": _UNIVERSAL_LINKS + _RAG_LINKS + _GRAPH_LINKS,
    "DevOps_Agent": _UNIVERSAL_LINKS + _RAG_LINKS + _GRAPH_LINKS,
    "SRE_Agent": _UNIVERSAL_LINKS + _RAG_LINKS,
    "SDET_Agent": _UNIVERSAL_LINKS + _RAG_LINKS + _GRAPH_LINKS,
    "Fullstack_Agent": _UNIVERSAL_LINKS + _RAG_LINKS + _GRAPH_LINKS,
    "RedTeam_Agent": _UNIVERSAL_LINKS + _RAG_LINKS,
}


def _build_infra_to_agents() -> Dict[str, List[str]]:
    """Invert _AGENT_INFRA: infra_name -> [agent_names...]"""
    result: Dict[str, List[str]] = {}
    for agent, links in _AGENT_INFRA.items():
        for infra_name, _ in links:
            result.setdefault(infra_name, [])
            if agent not in result[infra_name]:
                result[infra_name].append(agent)
    return result


# ---------------------------------------------------------------------------
# Monitor
# ---------------------------------------------------------------------------

_PROBES: Dict[str, Callable[[], NodeResult]] = {
    "qdrant": _probe_qdrant,
    "weaviate": _probe_weaviate,
    "neo4j": _probe_neo4j,
    "artifact_store": _probe_artifact_store,
    "learning_metrics": _probe_learning_metrics,
}


class DataflowHealthMonitor:
    """
    Checks every infrastructure node in the agent pipeline and reports
    which agents are affected by any broken link.

    Designed to be run:
    - As a CI pre-flight step before agent jobs
    - From the dashboard "System Health" page
    - Via the API endpoint GET /api/health/dataflow
    """

    def __init__(self, probes: Optional[Dict[str, Callable[[], NodeResult]]] = None):
        self._probes = probes if probes is not None else _PROBES
        self._infra_to_agents = _build_infra_to_agents()

    def check_all(self) -> DataflowHealthReport:
        """Run all probes and return a full health report."""
        from datetime import datetime, timezone
        ts = datetime.now(timezone.utc).isoformat()

        healthy: List[NodeResult] = []
        broken: List[NodeResult] = []

        for name, probe_fn in self._probes.items():
            try:
                result = probe_fn()
            except Exception as exc:
                # Defensive: a probe itself must never crash the monitor
                fake_node = InfraNode(name, "unknown", is_critical=False)
                result = NodeResult(fake_node, False, 0.0, f"Probe error: {exc}")

            if result.healthy:
                healthy.append(result)
            else:
                broken.append(result)

        affected: Dict[str, List[str]] = {
            r.node.name: self._infra_to_agents.get(r.node.name, [])
            for r in broken
        }

        is_healthy = len(broken) == 0
        summary = self._build_summary(healthy, broken, affected)

        return DataflowHealthReport(
            timestamp=ts,
            is_healthy=is_healthy,
            healthy_nodes=healthy,
            broken_nodes=broken,
            affected_agents=affected,
            summary=summary,
        )

    def check_agent(self, agent_name: str) -> Dict[str, Any]:
        """Check only the infrastructure that a specific agent depends on."""
        agent_infra = _AGENT_INFRA.get(agent_name, [])
        results = {}
        for infra_name, purpose in agent_infra:
            if infra_name in self._probes:
                result = self._probes[infra_name]()
                results[infra_name] = {
                    "healthy": result.healthy,
                    "message": result.message,
                    "purpose": purpose,
                    "latency_ms": result.latency_ms,
                }
        all_healthy = all(r["healthy"] for r in results.values())
        return {
            "agent": agent_name,
            "is_healthy": all_healthy,
            "dependencies": results,
        }

    @staticmethod
    def _build_summary(
        healthy: List[NodeResult],
        broken: List[NodeResult],
        affected: Dict[str, List[str]],
    ) -> str:
        if not broken:
            return f"All {len(healthy)} infrastructure nodes healthy."

        lines = [f"{len(broken)} broken node(s) detected:"]
        for r in broken:
            agents = affected.get(r.node.name, [])
            severity = "CRITICAL" if r.node.is_critical else "DEGRADED"
            lines.append(
                f"  [{severity}] {r.node.name}: {r.message}"
            )
            if agents:
                lines.append(f"    Affected agents: {', '.join(agents)}")
            if r.detail:
                lines.append(f"    Remediation: {r.detail}")
        return "\n".join(lines)


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

def main() -> int:
    import argparse
    parser = argparse.ArgumentParser(
        description="Check AgenticQA infrastructure dataflow health"
    )
    parser.add_argument("--json", action="store_true", help="Output JSON")
    parser.add_argument("--agent", help="Check a specific agent's dependencies only")
    parser.add_argument("--fail-on-degraded", action="store_true",
                        help="Exit non-zero even for non-critical broken nodes")
    args = parser.parse_args()

    monitor = DataflowHealthMonitor()

    if args.agent:
        result = monitor.check_agent(args.agent)
        if args.json:
            print(json.dumps(result, indent=2))
        else:
            status = "HEALTHY" if result["is_healthy"] else "UNHEALTHY"
            print(f"Agent: {args.agent} — {status}")
            for name, dep in result["dependencies"].items():
                icon = "✅" if dep["healthy"] else "❌"
                print(f"  {icon} {name}: {dep['message']} ({dep['purpose']})")
        return 0 if result["is_healthy"] else 1

    report = monitor.check_all()

    if args.json:
        print(json.dumps(report.to_dict(), indent=2))
    else:
        icon = "✅" if report.is_healthy else "❌"
        print(f"\n{icon} AgenticQA Dataflow Health — {report.timestamp}")
        print("=" * 60)
        for r in report.healthy_nodes:
            print(f"  ✅ {r.node.name:<20} {r.message} ({r.latency_ms:.0f}ms)")
        for r in report.broken_nodes:
            severity = "CRITICAL" if r.node.is_critical else "DEGRADED"
            print(f"  ❌ {r.node.name:<20} [{severity}] {r.message}")
            if r.detail:
                print(f"     → {r.detail}")
            agents = report.affected_agents.get(r.node.name, [])
            if agents:
                print(f"     Affected: {', '.join(agents)}")
        print()
        print(report.summary)
        print()

    # Exit codes: 0=healthy, 1=critical broken, 2=degraded only
    if any(r.node.is_critical for r in report.broken_nodes):
        return 1
    if report.broken_nodes and args.fail_on_degraded:
        return 2
    return 0


if __name__ == "__main__":
    import sys
    sys.exit(main())
