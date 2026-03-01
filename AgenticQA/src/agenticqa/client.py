"""AgenticQA Python Client SDK.

Typed client for the AgenticQA REST API — agents, security scanners,
compliance checks, and safety controls.

Usage::

    from agenticqa.client import AgenticQAClient

    client = AgenticQAClient("http://localhost:8000", token="your-token")

    # Full 13-scanner security scan
    result = client.scan_repo("/path/to/repo")
    print(f"Critical: {result.total_critical}")

    # Individual scanners
    bias = client.scan_for_bias("The female candidate was rejected.")
    injection = client.scan_for_injection("Ignore previous instructions.")
    sbom = client.ai_model_sbom("/path/to/repo")

    # Legacy agent execution
    results = client.execute_agents({"code": "...", "tests": "..."})

"""
from __future__ import annotations

import json
import requests
from dataclasses import dataclass, field
from typing import Dict, List, Any, Optional
from datetime import datetime


# ── Typed response objects ────────────────────────────────────────────────────

@dataclass
class ScanSummary:
    """Top-level scan summary from run_client_scan."""
    repo_path: str
    scanners_ok: int
    scanners_failed: int
    total_findings: int
    total_critical: int
    total_elapsed_s: float


@dataclass
class ScanResult:
    """Full scan result with summary and per-scanner data."""
    summary: ScanSummary
    scanners: Dict[str, Any]
    raw: Dict[str, Any] = field(repr=False, default_factory=dict)

    @property
    def has_critical(self) -> bool:
        return self.summary.total_critical > 0


# ── Exceptions ────────────────────────────────────────────────────────────────

class AgenticQAError(Exception):
    """Base SDK exception."""
    def __init__(self, message: str, status_code: int = 0):
        super().__init__(message)
        self.status_code = status_code


class AuthenticationError(AgenticQAError):
    pass


class NotFoundError(AgenticQAError):
    pass


class ServerError(AgenticQAError):
    pass


# ── Client ────────────────────────────────────────────────────────────────────

# Backwards-compatible alias
RemoteClient = None  # set after class definition


class AgenticQAClient:
    """Full-featured client for the AgenticQA REST API.

    Args:
        base_url: API server URL (e.g. ``http://localhost:8000``).
        token: Bearer token for authentication (optional when auth disabled).
        timeout: Request timeout in seconds.
    """

    def __init__(self, base_url: str = "http://localhost:8000",
                 token: Optional[str] = None, timeout: int = 300):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.session = requests.Session()
        if token:
            self.session.headers["Authorization"] = f"Bearer {token}"
        self.session.headers["Content-Type"] = "application/json"

    # ── Internal ──────────────────────────────────────────────────────────

    def _url(self, path: str) -> str:
        return f"{self.base_url}{path}"

    def _handle(self, resp: requests.Response) -> Dict[str, Any]:
        if resp.status_code in (401, 403):
            raise AuthenticationError(resp.text, resp.status_code)
        if resp.status_code == 404:
            raise NotFoundError(resp.text, resp.status_code)
        if resp.status_code >= 500:
            raise ServerError(resp.text, resp.status_code)
        if resp.status_code >= 400:
            raise AgenticQAError(resp.text, resp.status_code)
        return resp.json()

    def _get(self, path: str, params: Optional[Dict] = None) -> Dict[str, Any]:
        return self._handle(
            self.session.get(self._url(path), params=params, timeout=self.timeout)
        )

    def _post(self, path: str, data: Optional[Dict] = None) -> Dict[str, Any]:
        return self._handle(
            self.session.post(self._url(path), json=data or {}, timeout=self.timeout)
        )

    def execute_agents(self, test_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute all agents against test data.

        Args:
            test_data: Test data to execute agents against

        Returns:
            Agent execution results with QA, Performance, Compliance, and DevOps findings

        Example:
            >>> client = RemoteClient()
            >>> results = client.execute_agents({
            ...     "code": "def add(a, b): return a + b",
            ...     "tests": "assert add(1, 2) == 3"
            ... })
        """
        endpoint = f"{self.base_url}/api/agents/execute"
        response = self.session.post(endpoint, json=test_data, timeout=self.timeout)
        response.raise_for_status()
        return response.json()

    def get_agent_insights(self, agent_name: Optional[str] = None) -> Dict[str, Any]:
        """
        Get insights and recommendations from agents.

        Args:
            agent_name: Specific agent name (qa, performance, compliance, devops) or None for all

        Returns:
            Agent insights and pattern analysis
        """
        endpoint = f"{self.base_url}/api/agents/insights"
        params = {}
        if agent_name:
            params["agent"] = agent_name

        response = self.session.get(endpoint, params=params, timeout=self.timeout)
        response.raise_for_status()
        return response.json()

    def get_agent_history(self, agent_name: str, limit: int = 50) -> List[Dict[str, Any]]:
        """
        Get execution history for a specific agent.

        Args:
            agent_name: Agent name (qa, performance, compliance, or devops)
            limit: Number of recent executions to retrieve

        Returns:
            List of agent execution records
        """
        endpoint = f"{self.base_url}/api/agents/{agent_name}/history"
        params = {"limit": limit}

        response = self.session.get(endpoint, params=params, timeout=self.timeout)
        response.raise_for_status()
        return response.json()

    def search_artifacts(self, query: str, limit: int = 50) -> List[Dict[str, Any]]:
        """
        Search test artifacts in the secure data store.

        Args:
            query: Search query (source, type, or tags)
            limit: Maximum results to return

        Returns:
            List of matching artifacts
        """
        endpoint = f"{self.base_url}/api/datastore/search"
        params = {"q": query, "limit": limit}

        response = self.session.get(endpoint, params=params, timeout=self.timeout)
        response.raise_for_status()
        return response.json()

    def get_artifact(self, artifact_id: str) -> Dict[str, Any]:
        """
        Retrieve a specific artifact from data store.

        Args:
            artifact_id: Unique artifact identifier

        Returns:
            Artifact data with metadata
        """
        endpoint = f"{self.base_url}/api/datastore/artifact/{artifact_id}"

        response = self.session.get(endpoint, timeout=self.timeout)
        response.raise_for_status()
        return response.json()

    def get_datastore_stats(self) -> Dict[str, Any]:
        """
        Get statistics about the data store.

        Returns:
            Data store metrics (total artifacts, size, patterns detected, etc.)
        """
        endpoint = f"{self.base_url}/api/datastore/stats"

        response = self.session.get(endpoint, timeout=self.timeout)
        response.raise_for_status()
        return response.json()

    def get_patterns(self) -> Dict[str, Any]:
        """
        Get detected patterns in historical agent data.

        Returns:
            Failure patterns, performance trends, and flakiness detection
        """
        endpoint = f"{self.base_url}/api/datastore/patterns"

        response = self.session.get(endpoint, timeout=self.timeout)
        response.raise_for_status()
        return response.json()

    def health_check(self) -> bool:
        """Check if API server is reachable and healthy."""
        try:
            response = self.session.get(f"{self.base_url}/health", timeout=5)
            return response.status_code == 200
        except Exception:
            return False

    def dataflow_health(self) -> Dict[str, Any]:
        """Check infrastructure health (Qdrant, Neo4j, etc)."""
        return self._get("/api/health/dataflow")

    # ── Security scanners (repo-level) ────────────────────────────────────

    def scan_repo(self, repo_path: str) -> ScanResult:
        """Run all 13 scanners via run_client_scan against a local repo path.

        This calls the scan script directly on the server side. For CI
        integration, prefer the CLI: ``python scripts/run_client_scan.py``
        """
        data = self._post("/api/agents/execute", {
            "task_type": "security_scan",
            "repo_path": repo_path,
        })
        s = data.get("summary", {})
        return ScanResult(
            summary=ScanSummary(
                repo_path=s.get("repo_path", repo_path),
                scanners_ok=s.get("scanners_ok", 0),
                scanners_failed=s.get("scanners_failed", 0),
                total_findings=s.get("total_findings", 0),
                total_critical=s.get("total_critical", 0),
                total_elapsed_s=s.get("total_elapsed_s", 0),
            ),
            scanners=data.get("scanners", {}),
            raw=data,
        )

    def prompt_injection_scan(self, repo_path: str) -> Dict[str, Any]:
        """Scan code for prompt injection vulnerabilities."""
        return self._post("/api/redteam/prompt-injection", {"repo_path": repo_path})

    def ai_act_check(self, repo_path: str) -> Dict[str, Any]:
        """Run EU AI Act compliance check."""
        return self._post("/api/compliance/ai-act", {"repo_path": repo_path})

    def ai_model_sbom(self, repo_path: str) -> Dict[str, Any]:
        """Generate AI Model Software Bill of Materials."""
        return self._post("/api/compliance/ai-model-sbom", {"repo_path": repo_path})

    def legal_risk_scan(self, repo_path: str) -> Dict[str, Any]:
        """Scan for credential/SSRF/legal risks."""
        return self._post("/api/compliance/legal-risk", {"repo_path": repo_path})

    def cve_scan(self, repo_path: str) -> Dict[str, Any]:
        """Scan for known CVE vulnerabilities in dependencies."""
        return self._post("/api/security/cve-reachability", {"repo_path": repo_path})

    def hipaa_scan(self, repo_path: str) -> Dict[str, Any]:
        """Scan for HIPAA PHI violations."""
        return self._post("/api/compliance/hipaa", {"repo_path": repo_path})

    def trust_graph(self, repo_path: str) -> Dict[str, Any]:
        """Analyze multi-agent trust relationships."""
        return self._post("/api/redteam/agent-trust-graph", {"repo_path": repo_path})

    def shadow_ai_scan(self, repo_path: str) -> Dict[str, Any]:
        """Detect unauthorized AI model usage."""
        return self._post("/api/security/shadow-ai-scan", {"repo_path": repo_path})

    # ── Inline content scanners ───────────────────────────────────────────

    def scan_for_bias(self, text: str) -> Dict[str, Any]:
        """Scan text for demographic bias signals."""
        return self._post("/api/security/bias-scan", {"text": text})

    def scan_for_injection(self, text: str) -> Dict[str, Any]:
        """Scan text/document for indirect prompt injection."""
        return self._post("/api/security/injection-scan", {"text": text})

    def redact_pii(self, text: str) -> Dict[str, Any]:
        """Redact PII from text and return sanitized version."""
        return self._post("/api/security/pii-redact", {"text": text})

    def scan_pii(self, text: str) -> Dict[str, Any]:
        """Detect PII in text without modifying it."""
        return self._post("/api/security/pii-scan", {"text": text})

    # ── Safety controls ───────────────────────────────────────────────────

    def intercept_action(self, agent: str, tool: str,
                         args: Dict[str, Any]) -> Dict[str, Any]:
        """Check if a tool call should be intercepted."""
        return self._post("/api/safety/intercept", {
            "agent": agent, "tool": tool, "args": args,
        })

    def create_lease(self, agent: str, reads: int = 100, writes: int = 10,
                     deletes: int = 0, executes: int = 5,
                     ttl_seconds: int = 3600) -> Dict[str, Any]:
        """Create a scope lease for an agent."""
        return self._post("/api/safety/lease", {
            "agent": agent, "reads": reads, "writes": writes,
            "deletes": deletes, "executes": executes, "ttl_seconds": ttl_seconds,
        })

    # ── Provenance / cost ─────────────────────────────────────────────────

    def verify_provenance(self, agent: str,
                          execution_id: str) -> Dict[str, Any]:
        """Verify an agent execution's provenance."""
        return self._get("/api/provenance/verify", {
            "agent": agent, "execution_id": execution_id,
        })

    def cost_summary(self) -> Dict[str, Any]:
        """Get cost tracking summary for all agents."""
        return self._get("/api/system/cost-summary")

    # ── Lifecycle ─────────────────────────────────────────────────────────

    def close(self):
        """Close the underlying HTTP session."""
        self.session.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()

    def __repr__(self) -> str:
        return f"AgenticQAClient(base_url={self.base_url!r})"


# Backwards-compatible alias
RemoteClient = AgenticQAClient
