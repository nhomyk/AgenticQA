"""FastAPI integration for agent orchestration and data store access"""

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Dict, Any, Optional, List
from datetime import UTC, datetime
from pathlib import Path
import os

try:
    from src.agenticqa.security.api_middleware import (
        BearerTokenMiddleware,
        OriginValidationMiddleware,
        ResponseScanMiddleware,
        RateLimitMiddleware,
        InputSizeMiddleware,
    )
except ImportError:
    from agenticqa.security.api_middleware import (
        BearerTokenMiddleware,
        OriginValidationMiddleware,
        ResponseScanMiddleware,
        RateLimitMiddleware,
        InputSizeMiddleware,
    )

from src.agents import AgentOrchestrator
from src.data_store import SecureDataPipeline
try:
    from src.agenticqa.workflow_requests import PromptWorkflowStore
    from src.agenticqa.workflow_worker import WorkflowExecutionWorker
    from src.agenticqa.observability import ObservabilityStore
    from src.agenticqa.reliability_evidence import build_evidence_summary, check_tcp, read_latest_jsonl
    from src.agenticqa.repo_profile import detect_repo_profile
    from src.agenticqa.rag.config import RAGConfig
    from src.agenticqa.portability_scorecard import (
        build_portability_roi_report,
        build_portability_scorecard,
        load_baseline,
        save_baseline,
    )
    from src.agenticqa.audit_report import build_audit_report
    from src.agenticqa.ingestion.event_schema import normalize_event as _normalize_ingest_event
    from src.agenticqa.constitutional_gate import (
        check_action as _constitutional_check, get_constitution,
        check_file_scope as _check_file_scope, get_agent_scopes,
    )
    from src.agenticqa.factory import AgentFactory, SUPPORTED_FRAMEWORKS
    from src.agenticqa.factory import SandboxedAgentAdapter
    from src.agenticqa.factory.spec_extractor import NaturalLanguageSpecExtractor, AgentSpec
    from src.agents import RedTeamAgent
except Exception:
    from agenticqa.workflow_requests import PromptWorkflowStore
    from agenticqa.workflow_worker import WorkflowExecutionWorker
    from agenticqa.observability import ObservabilityStore
    from agenticqa.reliability_evidence import build_evidence_summary, check_tcp, read_latest_jsonl
    from agenticqa.repo_profile import detect_repo_profile
    from agenticqa.rag.config import RAGConfig
    from agenticqa.portability_scorecard import (
        build_portability_roi_report,
        build_portability_scorecard,
        load_baseline,
        save_baseline,
    )
    from agenticqa.audit_report import build_audit_report
    from agenticqa.ingestion.event_schema import normalize_event as _normalize_ingest_event
    from agenticqa.constitutional_gate import (
        check_action as _constitutional_check, get_constitution,
        check_file_scope as _check_file_scope, get_agent_scopes,
    )
    from agenticqa.factory import AgentFactory, SUPPORTED_FRAMEWORKS
    from agenticqa.factory import SandboxedAgentAdapter
    from agenticqa.factory.spec_extractor import NaturalLanguageSpecExtractor, AgentSpec
    from agents import RedTeamAgent

app = FastAPI(title="AgenticQA API", version="1.0.0")

# ── Security middleware stack (outermost = first to run) ──────────────────
# Order matters: middlewares are applied in reverse registration order in
# Starlette — the last added runs first. We want:
#   OriginValidation → BearerToken → ResponseScan → handler
# so we register in the opposite order.
app.add_middleware(ResponseScanMiddleware)
app.add_middleware(BearerTokenMiddleware)
app.add_middleware(OriginValidationMiddleware)
app.add_middleware(RateLimitMiddleware)    # 60 req/min per token; 15 for heavy endpoints
app.add_middleware(InputSizeMiddleware)    # 512 KB body limit; depth-20 JSON limit

# CORS — localhost only (DNS rebinding defence; mirrors docker/mcp-gateway)
_LOCALHOST_ORIGINS = [
    "http://localhost",
    "http://localhost:8501",   # Streamlit dashboard
    "http://localhost:3000",   # dev React / Next.js
    "http://localhost:8000",   # uvicorn self
    "http://localhost:8080",
    "http://127.0.0.1",
    "http://127.0.0.1:8501",
    "http://127.0.0.1:3000",
    "http://127.0.0.1:8000",
    "http://127.0.0.1:8080",
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=_LOCALHOST_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize orchestrator and data store
orchestrator = AgentOrchestrator()
data_pipeline = SecureDataPipeline(use_great_expectations=False)
workflow_store = PromptWorkflowStore()
observability_store = ObservabilityStore()
workflow_worker = WorkflowExecutionWorker(workflow_store, observability_store=observability_store)


# Request/Response Models
class ExecutionRequest(BaseModel):
    """Request to execute agents"""

    test_results: Optional[Dict[str, Any]] = None
    execution_data: Optional[Dict[str, Any]] = None
    linting_data: Optional[Dict[str, Any]] = None
    compliance_data: Optional[Dict[str, Any]] = None
    deployment_config: Optional[Dict[str, Any]] = None


class ArtifactSearchRequest(BaseModel):
    """Request to search artifacts"""

    artifact_type: Optional[str] = None
    source: Optional[str] = None
    tags: Optional[List[str]] = None


class DataStoreStats(BaseModel):
    """Data store statistics"""

    total_artifacts: int
    by_type: Dict[str, int]
    by_source: Dict[str, int]
    last_updated: Optional[str] = None


class WorkflowRequestCreate(BaseModel):
    """Prompt-driven workflow creation request."""

    prompt: str
    repo: str = "."
    requester: str = "dashboard"
    metadata: Optional[Dict[str, Any]] = None


class WorkflowActionRequest(BaseModel):
    """Action request for an existing workflow item."""

    reason: Optional[str] = None
    requester: Optional[str] = None


class WorkflowRunRequest(BaseModel):
    """Worker execution request options."""

    dry_run: bool = True
    open_pr: bool = True


class PluginRepoRequest(BaseModel):
    """Request for plug-in onboarding operations."""

    repo: str = "."
    force: bool = False


class PortabilityBaselineRequest(BaseModel):
    """Request payload to persist current portability scorecard as baseline."""

    repo: str = "."
    note: str = ""


class ChatSessionCreateRequest(BaseModel):
    """Create a persisted dashboard chat session."""

    repo: str = "."
    requester: str = "dashboard_chat"
    metadata: Optional[Dict[str, Any]] = None


class ChatMessageRequest(BaseModel):
    """Append a message to an existing chat session."""

    role: str
    content: str
    metadata: Optional[Dict[str, Any]] = None
    request_id: Optional[str] = None


class ChatTurnRequest(BaseModel):
    """Single chat turn with optional workflow request creation."""

    message: str
    session_id: Optional[str] = None
    repo: str = "."
    requester: str = "dashboard_chat"
    auto_create_workflow: bool = True
    mode: str = "deterministic"
    tool_execution: str = "require_approval"
    metadata: Optional[Dict[str, Any]] = None


class ObservabilityEventsQuery(BaseModel):
    """Optional filters for observability event queries."""

    trace_id: Optional[str] = None
    request_id: Optional[str] = None
    agent: Optional[str] = None
    action: Optional[str] = None
    limit: int = 100


class IngestEventRequest(BaseModel):
    """Single normalized event from any external agent platform."""

    trace_id: str
    agent: str
    action: str
    status: str
    request_id: Optional[str] = None
    span_id: Optional[str] = None
    parent_span_id: Optional[str] = None
    event_type: Optional[str] = None
    step_key: Optional[str] = None
    latency_ms: Optional[float] = None
    decision: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None
    llm_prompt_tokens: Optional[int] = None
    llm_completion_tokens: Optional[int] = None


class IngestBatchRequest(BaseModel):
    events: List[IngestEventRequest]


def _infer_operator_actions(message: str) -> List[Dict[str, Any]]:
    """Infer a deterministic action plan from plain-language operator input."""
    text = (message or "").lower()
    actions: List[Dict[str, Any]] = []

    if any(token in text for token in ["scorecard", "portability"]):
        actions.append(
            {
                "tool": "get_portability_scorecard",
                "label": "Fetch portability scorecard",
                "risk": "low",
                "requires_approval": False,
                "kind": "read",
            }
        )
    if any(token in text for token in ["baseline", "save baseline"]):
        actions.append(
            {
                "tool": "save_portability_baseline",
                "label": "Save current baseline snapshot",
                "risk": "medium",
                "requires_approval": True,
                "kind": "write",
            }
        )
    if any(token in text for token in ["roi", "report"]):
        actions.append(
            {
                "tool": "get_portability_roi_report",
                "label": "Generate ROI report",
                "risk": "low",
                "requires_approval": False,
                "kind": "read",
            }
        )
    if any(token in text for token in ["approve", "queue", "run", "replay", "cancel"]):
        actions.append(
            {
                "tool": "governed_workflow_transition",
                "label": "Run governed workflow action",
                "risk": "high",
                "requires_approval": True,
                "kind": "write",
            }
        )

    if not actions:
        actions.append(
            {
                "tool": "create_workflow_request",
                "label": "Create workflow request",
                "risk": "medium",
                "requires_approval": True,
                "kind": "write",
            }
        )

    return actions


def _build_chat_assistant_reply(
    message: str,
    workflow_item: Optional[Dict[str, Any]] = None,
    action_plan: Optional[List[Dict[str, Any]]] = None,
    mode: str = "deterministic",
    tool_execution: str = "require_approval",
) -> str:
    """Build deterministic assistant feedback for dashboard chat turns."""
    cleaned = (message or "").strip()
    if mode == "llm":
        mode_text = "LLM mode selected; deterministic fallback is active until provider adapter is configured."
    else:
        mode_text = "Deterministic operator mode active."

    action_count = len(action_plan or [])

    if workflow_item:
        req_id = workflow_item.get("id")
        status = workflow_item.get("status")
        next_action = workflow_item.get("next_action")
        return (
            f"{mode_text} "
            f"Captured your request and saved it as workflow `{req_id}`. "
            f"Current status: {status}. Next action: {next_action}. "
            f"Action plan contains {action_count} governed step(s) with policy `{tool_execution}`. "
            "You can approve/queue it from Prompt Ops controls or keep chatting to submit follow-up changes."
        )
    if not cleaned:
        return "Please enter a prompt to continue."
    return (
        f"{mode_text} Message saved with {action_count} proposed action(s). "
        f"Current policy is `{tool_execution}`. Enable auto-workflow to turn chat prompts into executable workflow requests."
    )


def _resolve_tool_policy(tool_execution: str) -> str:
    policy = (tool_execution or "require_approval").strip().lower()
    if policy not in {"suggest_only", "require_approval", "auto_for_safe"}:
        return "require_approval"
    return policy


def _resolve_chat_mode(mode: str) -> str:
    requested = (mode or "deterministic").strip().lower()
    if requested not in {"deterministic", "llm"}:
        return "deterministic"
    return requested


def _llm_provider_config() -> Dict[str, Any]:
    provider = os.getenv("AGENTICQA_LLM_PROVIDER", "none").strip().lower()
    model = os.getenv("AGENTICQA_LLM_MODEL", "deterministic-fallback")
    base_url = os.getenv("AGENTICQA_LLM_BASE_URL", "")
    has_key = bool(os.getenv("AGENTICQA_LLM_API_KEY"))
    return {
        "provider": provider,
        "model": model,
        "base_url": base_url,
        "configured": provider not in {"", "none"} and has_key,
        "api_key_configured": has_key,
    }


@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "timestamp": datetime.now(UTC).isoformat(),
        "agents_ready": 4,
    }


@app.get("/api/health/dataflow")
async def dataflow_health():
    """
    Check all infrastructure nodes in the agent pipeline.

    Returns a structured report showing which nodes are healthy/broken
    and which agents are affected by any broken link.
    """
    try:
        import sys as _sys
        _sys.path.insert(0, str(Path(__file__).parent / "src"))
        from agenticqa.monitoring.dataflow_health import DataflowHealthMonitor
        report = DataflowHealthMonitor().check_all()
        d = report.to_dict()
        d["http_status"] = 200 if report.is_healthy else 503
        return d
    except Exception as e:
        return {
            "is_healthy": False,
            "summary": f"Monitor error: {e}",
            "broken_nodes": [],
            "healthy_nodes": [],
            "affected_agents": {},
            "http_status": 500,
        }


@app.get("/api/health/integrity")
async def system_integrity():
    """
    Application-level integrity check — verifies ontology, constitutional gate,
    scanners, artifact store, provenance, and ingest pipeline are all wired
    correctly. Complements /api/health/dataflow (infrastructure probes).

    Returns 200 when all checks pass, 503 when any check fails.
    """
    try:
        from agenticqa.monitoring.integrity_checker import SystemIntegrityChecker
        report = SystemIntegrityChecker().check_all()
        d = report.to_dict()
        d["http_status"] = 200 if report.passed else 503
        return d
    except Exception as e:
        return {
            "passed": False,
            "total": 0,
            "passed_count": 0,
            "failed_count": 1,
            "checks": [{"name": "startup", "passed": False, "message": str(e)}],
            "http_status": 500,
        }


@app.get("/api/system/readiness")
async def system_readiness():
    """Detailed readiness checks for local dependencies and data stores."""
    try:
        home = Path.home() / ".agenticqa"
        vector_provider = RAGConfig.get_vector_provider().value
        weaviate_up = check_tcp("127.0.0.1", 8080)
        qdrant_up = check_tcp("127.0.0.1", 6333)
        checks = {
            "workflow_db_writable": home.exists() or home.parent.exists(),
            "observability_db_writable": home.exists() or home.parent.exists(),
            "neo4j_tcp": check_tcp("127.0.0.1", 7687),
            "weaviate_tcp": weaviate_up,
            "qdrant_tcp": qdrant_up,
            "vector_provider": vector_provider,
            "vector_provider_tcp": qdrant_up if vector_provider == "qdrant" else weaviate_up,
            "vector_store_available": weaviate_up or qdrant_up,
        }
        ready = checks["workflow_db_writable"] and checks["observability_db_writable"]
        return {
            "success": True,
            "ready": bool(ready),
            "checks": checks,
            "timestamp": datetime.now(UTC).isoformat(),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/system/constitution")
async def get_system_constitution():
    """Return the AgenticQA Agent Constitution.

    Any external agent platform (LangGraph, CrewAI, AutoGen, etc.) can query
    this endpoint to discover the governance rules they must enforce.
    """
    try:
        constitution = get_constitution()
        if not constitution:
            raise HTTPException(status_code=503, detail="Constitution not loaded.")
        return {
            "success": True,
            "version": constitution.get("version", "unknown"),
            "effective_date": constitution.get("effective_date"),
            "platform": constitution.get("platform"),
            "tier_1_count": len(constitution.get("tier_1", [])),
            "tier_2_count": len(constitution.get("tier_2", [])),
            "tier_3_count": len(constitution.get("tier_3", [])),
            "constitution": constitution,
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


class ConstitutionalCheckRequest(BaseModel):
    action_type: str
    context: Dict[str, Any] = {}


@app.post("/api/system/constitution/check")
async def constitutional_check(request: ConstitutionalCheckRequest):
    """Pre-action constitutional check for any agent platform.

    Submit a proposed action and its context; receive ALLOW / REQUIRE_APPROVAL / DENY.

    Example request:
        {"action_type": "delete", "context": {"ci_status": "FAILED", "trace_id": "tr-001"}}
    Example response:
        {"verdict": "DENY", "law": "T1-001", "name": "no_destructive_without_ci", "reason": "..."}
    """
    try:
        result = _constitutional_check(
            action_type=request.action_type,
            context=request.context,
        )
        return {"success": True, **result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/system/agent-scopes")
async def get_system_agent_scopes():
    """Return all declared agent file scopes.

    Shows exactly which files each agent is permitted to read and write.
    Any external agent platform can query this to enforce scope restrictions
    before performing file operations.
    """
    try:
        scopes = get_agent_scopes()
        if not scopes:
            raise HTTPException(status_code=503, detail="Agent scopes not loaded.")
        summary = []
        for agent_name, scope in scopes.items():
            if not isinstance(scope, dict):
                continue
            summary.append({
                "agent": agent_name,
                "description": scope.get("description", ""),
                "read_patterns": scope.get("read", []),
                "write_patterns": scope.get("write", []),
                "deny_patterns": scope.get("deny", []),
                "write_count": len(scope.get("write", [])),
                "deny_count": len(scope.get("deny", [])),
                "read_only": len(scope.get("write", [])) == 0,
            })
        return {
            "success": True,
            "agent_count": len(summary),
            "agents": summary,
            "scopes": scopes,
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


class FileScopeCheckRequest(BaseModel):
    agent: str
    action: str
    file_path: str


@app.post("/api/system/agent-scopes/check")
async def file_scope_check(request: FileScopeCheckRequest):
    """Check whether an agent is permitted to perform an action on a specific file.

    Example request:
        {"agent": "SDET_Agent", "action": "write", "file_path": ".github/workflows/ci.yml"}
    Example response:
        {"verdict": "DENY", "law": "T1-006", "name": "agent_file_scope_violation", "reason": "..."}
    """
    try:
        result = _check_file_scope(
            agent_name=request.agent,
            action=request.action,
            file_path=request.file_path,
        )
        return {"success": True, **result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/agents/execute")
async def execute_agents(request: ExecutionRequest):
    """Execute all agents with provided data"""
    # ConstitutionalGate check — same gate used by the RedTeamAgent
    gate_result = _constitutional_check(
        action_type="run_agents",
        context={"source": "api", "data_keys": list(request.dict().keys())},
    )
    if not gate_result.get("allowed", True):
        raise HTTPException(
            status_code=403,
            detail={
                "reason": gate_result.get("reason", "Action blocked by constitutional gate"),
                "gate": "ConstitutionalGate",
            },
        )
    try:
        results = orchestrator.execute_all_agents(request.dict())
        return {
            "success": True,
            "timestamp": datetime.now(UTC).isoformat(),
            "results": results,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/agents/insights")
async def get_agent_insights():
    """Get pattern insights from all agents"""
    try:
        insights = orchestrator.get_agent_insights()
        return {
            "success": True,
            "timestamp": datetime.now(UTC).isoformat(),
            "insights": insights,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/agents/{agent_name}/history")
async def get_agent_history(agent_name: str, limit: int = 10):
    """Get execution history for a specific agent"""
    try:
        agent = orchestrator.agents.get(agent_name.lower())
        if not agent:
            raise HTTPException(status_code=404, detail=f"Agent {agent_name} not found")

        history = agent.get_similar_executions(limit=limit)
        return {
            "success": True,
            "agent": agent_name,
            "history": history,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/datastore/search")
async def search_artifacts(request: ArtifactSearchRequest):
    """Search for artifacts in data store"""
    try:
        artifacts = data_pipeline.artifact_store.search_artifacts(
            artifact_type=request.artifact_type,
            source=request.source,
            tags=request.tags,
        )
        return {
            "success": True,
            "count": len(artifacts),
            "artifacts": artifacts,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/datastore/artifact/{artifact_id}")
async def get_artifact(artifact_id: str):
    """Retrieve a specific artifact"""
    try:
        artifact = data_pipeline.artifact_store.get_artifact(artifact_id)
        is_valid = data_pipeline.artifact_store.verify_artifact_integrity(artifact_id)
        return {
            "success": True,
            "artifact_id": artifact_id,
            "integrity_verified": is_valid,
            "data": artifact,
        }
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail=f"Artifact {artifact_id} not found")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/datastore/stats")
async def get_datastore_stats():
    """Get data store statistics"""
    try:
        all_artifacts = data_pipeline.artifact_store.search_artifacts()

        # Count by type and source
        by_type = {}
        by_source = {}

        for artifact in all_artifacts:
            artifact_type = artifact.get("artifact_type", "unknown")
            source = artifact.get("source", "unknown")

            by_type[artifact_type] = by_type.get(artifact_type, 0) + 1
            by_source[source] = by_source.get(source, 0) + 1

        return {
            "success": True,
            "total_artifacts": len(all_artifacts),
            "by_type": by_type,
            "by_source": by_source,
            "last_updated": (
                all_artifacts[-1]["timestamp"] if all_artifacts else None
            ),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/datastore/patterns")
async def get_patterns():
    """Get analyzed patterns from data store"""
    try:
        patterns = data_pipeline.analyze_patterns()
        return {
            "success": True,
            "timestamp": datetime.now(UTC).isoformat(),
            "patterns": patterns,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/plugin/bootstrap")
async def plugin_bootstrap(body: PluginRepoRequest):
    """Bootstrap AgenticQA plug-in files for any target repository."""
    try:
        try:
            from src.agenticqa.plugin_onboarding import bootstrap_project
        except Exception:
            from agenticqa.plugin_onboarding import bootstrap_project

        result = bootstrap_project(repo_root=Path(body.repo), force=body.force)
        return {
            "success": True,
            "repo": body.repo,
            "created_files": [str(p) for p in result.created_files],
            "detected_stack": result.detected_stack,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/plugin/doctor")
async def plugin_doctor(body: PluginRepoRequest):
    """Run onboarding health checks for a target repository."""
    try:
        try:
            from src.agenticqa.plugin_onboarding import run_doctor
        except Exception:
            from agenticqa.plugin_onboarding import run_doctor

        result = run_doctor(repo_root=Path(body.repo))
        return {
            "success": True,
            "repo": body.repo,
            "healthy": result.healthy,
            "checks": result.checks,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/workflows/requests")
async def create_workflow_request(request: WorkflowRequestCreate):
    """Create a prompt-driven development workflow request."""
    try:
        if not request.prompt.strip():
            raise HTTPException(status_code=400, detail="prompt cannot be empty")

        item = workflow_store.create_request(
            prompt=request.prompt,
            repo=request.repo,
            requester=request.requester,
            metadata=request.metadata,
        )
        return {
            "success": True,
            "timestamp": datetime.now(UTC).isoformat(),
            "request": item,
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/chat/sessions")
async def create_chat_session(body: ChatSessionCreateRequest):
    """Create a new persisted chat session for dashboard operator flow."""
    try:
        session = workflow_store.create_chat_session(
            repo=body.repo,
            requester=body.requester,
            metadata=body.metadata,
        )
        return {
            "success": True,
            "timestamp": datetime.now(UTC).isoformat(),
            "session": session,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/chat/sessions")
async def list_chat_sessions(limit: int = 25):
    """List recent chat sessions."""
    try:
        sessions = workflow_store.list_chat_sessions(limit=limit)
        return {
            "success": True,
            "count": len(sessions),
            "sessions": sessions,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/chat/sessions/{session_id}")
async def get_chat_session(session_id: str, limit: int = 200):
    """Get a chat session with message history."""
    try:
        session = workflow_store.get_chat_session(session_id=session_id, message_limit=limit)
        if not session:
            raise HTTPException(status_code=404, detail="chat session not found")
        return {
            "success": True,
            "session": session,
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/chat/sessions/{session_id}/messages")
async def add_chat_message(session_id: str, body: ChatMessageRequest):
    """Append a message to a chat session."""
    try:
        content = (body.content or "").strip()
        if not content:
            raise HTTPException(status_code=400, detail="content cannot be empty")
        message = workflow_store.add_chat_message(
            session_id=session_id,
            role=body.role,
            content=content,
            metadata=body.metadata,
            request_id=body.request_id,
        )
        return {
            "success": True,
            "timestamp": datetime.now(UTC).isoformat(),
            "message": message,
        }
    except ValueError as e:
        if "chat_session_not_found" in str(e):
            raise HTTPException(status_code=404, detail="chat session not found")
        if "invalid_chat_role" in str(e):
            raise HTTPException(status_code=400, detail="invalid chat role")
        raise HTTPException(status_code=409, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/chat/turn")
async def chat_turn(body: ChatTurnRequest):
    """Persist a chat turn and optionally create a workflow request from the prompt."""
    try:
        message = (body.message or "").strip()
        if not message:
            raise HTTPException(status_code=400, detail="message cannot be empty")

        session = None
        if body.session_id:
            session = workflow_store.get_chat_session(body.session_id, message_limit=1)
            if not session:
                raise HTTPException(status_code=404, detail="chat session not found")
        else:
            session = workflow_store.create_chat_session(
                repo=body.repo,
                requester=body.requester,
                metadata={"source": "chat_turn"},
            )

        session_id = session["id"]
        user_msg = workflow_store.add_chat_message(
            session_id=session_id,
            role="user",
            content=message,
            metadata=body.metadata,
        )

        mode = _resolve_chat_mode(body.mode)
        tool_policy = _resolve_tool_policy(body.tool_execution)
        action_plan = _infer_operator_actions(message)

        allow_write = tool_policy != "suggest_only"

        workflow_item = None
        if body.auto_create_workflow and allow_write:
            workflow_item = workflow_store.create_request(
                prompt=message,
                repo=body.repo,
                requester=body.requester,
                metadata={
                    "source": "dashboard_chat",
                    "chat_session_id": session_id,
                    "operator_mode": mode,
                    "tool_execution": tool_policy,
                    "action_plan": action_plan,
                    **(body.metadata or {}),
                },
            )

        assistant_text = _build_chat_assistant_reply(
            message=message,
            workflow_item=workflow_item,
            action_plan=action_plan,
            mode=mode,
            tool_execution=tool_policy,
        )
        assistant_msg = workflow_store.add_chat_message(
            session_id=session_id,
            role="assistant",
            content=assistant_text,
            metadata={
                "source": "chat_orchestrator",
                "mode": mode,
                "tool_execution": tool_policy,
                "action_plan": action_plan,
            },
            request_id=(workflow_item or {}).get("id") if workflow_item else None,
        )

        return {
            "success": True,
            "timestamp": datetime.now(UTC).isoformat(),
            "session_id": session_id,
            "mode": mode,
            "tool_execution": tool_policy,
            "action_plan": action_plan,
            "user_message": user_msg,
            "assistant_message": assistant_msg,
            "workflow_request": workflow_item,
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/operator/config")
async def get_operator_config():
    """Return operator console configuration summary (safe/no secrets)."""
    try:
        llm = _llm_provider_config()
        return {
            "success": True,
            "timestamp": datetime.now(UTC).isoformat(),
            "operator": {
                "default_mode": "deterministic",
                "tool_execution_modes": ["suggest_only", "require_approval", "auto_for_safe"],
                "write_actions_require_approval": True,
            },
            "llm": llm,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/operator/config/test-connection")
async def test_operator_llm_connection():
    """Validate LLM configuration wiring (dry check, no remote call)."""
    try:
        llm = _llm_provider_config()
        ok = bool(llm.get("configured"))
        detail = "configured" if ok else "provider or API key missing"
        return {
            "success": True,
            "timestamp": datetime.now(UTC).isoformat(),
            "ok": ok,
            "detail": detail,
            "llm": llm,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/workflows/requests")
async def list_workflow_requests(limit: int = 25):
    """List recent workflow requests."""
    try:
        return {
            "success": True,
            "count": min(max(limit, 1), 200),
            "requests": workflow_store.list_requests(limit=min(max(limit, 1), 200)),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/workflows/requests/{request_id}")
async def get_workflow_request(request_id: str):
    """Get a single workflow request with lifecycle events."""
    try:
        item = workflow_store.get_request(request_id)
        if not item:
            raise HTTPException(status_code=404, detail="workflow request not found")
        return {"success": True, "request": item}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/workflows/requests/{request_id}/approve")
async def approve_workflow_request(request_id: str):
    """Approve a workflow request for execution queueing."""
    try:
        item = workflow_store.approve_request(request_id)
        return {"success": True, "request": item}
    except ValueError as e:
        if "not_found" in str(e):
            raise HTTPException(status_code=404, detail="workflow request not found")
        raise HTTPException(status_code=409, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/workflows/requests/{request_id}/queue")
async def queue_workflow_request(request_id: str):
    """Queue an approved workflow request for worker pickup."""
    try:
        item = workflow_store.queue_request(request_id)
        return {"success": True, "request": item}
    except ValueError as e:
        if "not_found" in str(e):
            raise HTTPException(status_code=404, detail="workflow request not found")
        raise HTTPException(status_code=409, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/workflows/requests/{request_id}/cancel")
async def cancel_workflow_request(request_id: str, body: WorkflowActionRequest):
    """Cancel a workflow request."""
    try:
        item = workflow_store.cancel_request(request_id, reason=body.reason or "cancelled_by_user")
        return {"success": True, "request": item}
    except ValueError as e:
        if "not_found" in str(e):
            raise HTTPException(status_code=404, detail="workflow request not found")
        raise HTTPException(status_code=409, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/workflows/requests/{request_id}/replay")
async def replay_workflow_request(request_id: str, body: WorkflowActionRequest):
    """Replay an existing workflow request with self-heal metadata and queue it immediately."""
    try:
        item = workflow_store.replay_request(
            request_id=request_id,
            requester=body.requester or "replay_api",
        )
        return {"success": True, "request": item}
    except ValueError as e:
        if "not_found" in str(e):
            raise HTTPException(status_code=404, detail="workflow request not found")
        raise HTTPException(status_code=409, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/workflows/metrics")
async def get_workflow_metrics(limit: int = 200):
    """Return Prompt Ops outcome metrics (MTTR, pass-rate uplift, flaky reduction)."""
    try:
        metrics = workflow_store.get_metrics(lookback_limit=limit)
        return {"success": True, "metrics": metrics}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/workflows/evidence")
async def get_workflow_evidence(limit: int = 500):
    """Client-facing evidence bundle mapping system claims to measurable signals."""
    try:
        metrics = workflow_store.get_metrics(lookback_limit=limit)
        traces = observability_store.list_traces(limit=100)
        history_path = Path.home() / ".agenticqa" / "benchmarks" / "sdet_trend_history.jsonl"
        latest = read_latest_jsonl(history_path)
        evidence = build_evidence_summary(metrics=metrics, latest_benchmark=latest, trace_count=len(traces))
        return {
            "success": True,
            "timestamp": datetime.now(UTC).isoformat(),
            "evidence": evidence,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/workflows/portability-scorecard")
async def get_portability_scorecard(repo: str = ".", limit: int = 500):
    """Build portability scorecard and baseline delta for any target repository."""
    try:
        repo_root = Path(repo).expanduser().resolve()
        profile = detect_repo_profile(repo_root).to_dict()
        metrics = workflow_store.get_metrics(lookback_limit=limit)
        insights = observability_store.get_global_insights(limit=limit)
        baseline = load_baseline(str(repo_root))
        scorecard = build_portability_scorecard(
            repo_profile=profile,
            workflow_metrics=metrics,
            observability_insights=insights,
            baseline=baseline,
        )
        return {
            "success": True,
            "timestamp": datetime.now(UTC).isoformat(),
            "repo": str(repo_root),
            "scorecard": scorecard,
            "has_baseline": baseline is not None,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/workflows/portability-scorecard/baseline")
async def save_portability_scorecard_baseline(body: PortabilityBaselineRequest):
    """Persist current portability scorecard as baseline for future delta comparisons."""
    try:
        repo_root = Path(body.repo).expanduser().resolve()
        profile = detect_repo_profile(repo_root).to_dict()
        metrics = workflow_store.get_metrics(lookback_limit=500)
        insights = observability_store.get_global_insights(limit=500)
        scorecard = build_portability_scorecard(
            repo_profile=profile,
            workflow_metrics=metrics,
            observability_insights=insights,
            baseline=load_baseline(str(repo_root)),
        )
        saved = save_baseline(
            repo_root=str(repo_root),
            scorecard=scorecard,
            note=body.note,
        )
        return {
            "success": True,
            "timestamp": datetime.now(UTC).isoformat(),
            "repo": str(repo_root),
            "baseline": saved,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/workflows/portability-scorecard/roi-report")
async def get_portability_roi_report(repo: str = ".", limit: int = 500):
    """Export a compact baseline/current/delta ROI report for a repository."""
    try:
        repo_root = Path(repo).expanduser().resolve()
        profile = detect_repo_profile(repo_root).to_dict()
        metrics = workflow_store.get_metrics(lookback_limit=limit)
        insights = observability_store.get_global_insights(limit=limit)
        baseline = load_baseline(str(repo_root))
        scorecard = build_portability_scorecard(
            repo_profile=profile,
            workflow_metrics=metrics,
            observability_insights=insights,
            baseline=baseline,
        )
        report = build_portability_roi_report(
            repo_root=str(repo_root),
            scorecard=scorecard,
            workflow_metrics=metrics,
        )
        return {
            "success": True,
            "timestamp": datetime.now(UTC).isoformat(),
            "repo": str(repo_root),
            "has_baseline": baseline is not None,
            "report": report,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/workflows/worker/run-next")
async def run_next_workflow_request(body: WorkflowRunRequest):
    """Run worker execution for the oldest queued workflow request."""
    try:
        item = workflow_worker.run_next(dry_run=body.dry_run, open_pr=body.open_pr)
        if not item:
            return {
                "success": True,
                "message": "no queued requests",
                "request": None,
            }
        return {"success": True, "request": item}
    except ValueError as e:
        if "not_found" in str(e):
            raise HTTPException(status_code=404, detail="workflow request not found")
        raise HTTPException(status_code=409, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/workflows/worker/run/{request_id}")
async def run_workflow_request(request_id: str, body: WorkflowRunRequest):
    """Run worker execution for a specific queued workflow request."""
    try:
        item = workflow_worker.run_request(
            request_id=request_id,
            dry_run=body.dry_run,
            open_pr=body.open_pr,
        )
        return {"success": True, "request": item}
    except ValueError as e:
        if "not_found" in str(e):
            raise HTTPException(status_code=404, detail="workflow request not found")
        raise HTTPException(status_code=409, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/observability/traces")
async def list_observability_traces(limit: int = 100):
    """List recent execution traces across workflow/agent actions."""
    try:
        traces = observability_store.list_traces(limit=limit)
        return {"success": True, "count": len(traces), "traces": traces}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/observability/traces/{trace_id}")
async def get_observability_trace(trace_id: str, limit: int = 500):
    """Get all events for a single trace."""
    try:
        trace = observability_store.get_trace(trace_id=trace_id, limit=limit)
        return {"success": True, "trace": trace}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/observability/traces/{trace_id}/analysis")
async def get_observability_trace_analysis(trace_id: str, limit: int = 1000):
    """Get computed span tree and quality analysis for a single trace."""
    try:
        events = observability_store.list_events(
            limit=limit,
            trace_id=trace_id,
            newest_first=False,
        )
        analysis = observability_store.analyze_trace(trace_id=trace_id, events=events)
        return {
            "success": True,
            "trace_id": trace_id,
            "event_count": len(events),
            "analysis": analysis,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/observability/traces/{trace_id}/counterfactuals")
async def get_observability_counterfactuals(trace_id: str, limit: int = 300):
    """Get counterfactual recommendations for failed/retried actions in a trace."""
    try:
        data = observability_store.get_counterfactual_recommendations(trace_id=trace_id, limit=limit)
        return {
            "success": True,
            "trace_id": trace_id,
            "counterfactuals": data,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/observability/traces/{trace_id}/audit-report")
async def get_observability_audit_report(trace_id: str, format: str = "json", limit: int = 500):
    """Build a shareable AI Decision Audit Report for a single trace.

    Returns structured JSON by default. Use format=markdown to get the pre-rendered PR body.
    Raises 404 if the trace has no recorded events.
    """
    try:
        report = build_audit_report(trace_id=trace_id, obs_store=observability_store, limit=limit)
        if format == "markdown":
            return {
                "success": True,
                "trace_id": trace_id,
                "audit_id": report["audit_id"],
                "markdown_body": report["markdown_body"],
            }
        return {"success": True, "trace_id": trace_id, "report": report}
    except ValueError as e:
        if str(e).startswith("trace_not_found:"):
            raise HTTPException(status_code=404, detail=f"Trace not found: {trace_id}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/observability/events")
async def list_observability_events(
    limit: int = 100,
    trace_id: Optional[str] = None,
    request_id: Optional[str] = None,
    agent: Optional[str] = None,
    action: Optional[str] = None,
    status: Optional[str] = None,
    event_type: Optional[str] = None,
):
    """Query raw observability events with optional filters."""
    try:
        events = observability_store.list_events(
            limit=limit,
            trace_id=trace_id,
            request_id=request_id,
            agent=agent,
            action=action,
            status=status,
            event_type=event_type,
        )
        return {"success": True, "count": len(events), "events": events}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/observability/quality")
async def get_observability_quality(
    limit: int = 100,
    min_completeness: float = 0.95,
    min_decision_quality: float = 0.60,
):
    """Return aggregate trace quality metrics for CI/CD quality gates."""
    try:
        summary = observability_store.get_quality_summary(
            limit=limit,
            min_completeness=min_completeness,
            min_decision_quality=min_decision_quality,
        )
        return {
            "success": True,
            "timestamp": datetime.now(UTC).isoformat(),
            "quality": summary,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/observability/ingest")
async def ingest_event(event: IngestEventRequest):
    """Ingest a single agent event from any external platform.

    Accepts events from LangGraph, LangChain, CrewAI, AutoGen, OpenAI Agents SDK,
    or any custom agent. All existing observability endpoints (traces, audit-report,
    counterfactuals, complexity trends) work transparently on ingested events.
    """
    try:
        evt = _normalize_ingest_event(event.model_dump())
        observability_store.log_event(
            trace_id=evt.trace_id,
            request_id=evt.request_id,
            agent=evt.agent,
            action=evt.action,
            status=evt.status,
            span_id=evt.span_id,
            parent_span_id=evt.parent_span_id,
            event_type=evt.event_type,
            step_key=evt.step_key,
            latency_ms=evt.latency_ms,
            decision=evt.decision,
            error=evt.error,
            metadata=evt.metadata,
        )
        if evt.llm_prompt_tokens or evt.llm_completion_tokens:
            observability_store.log_complexity_metric(
                agent=evt.agent,
                action=evt.action,
                trace_id=evt.trace_id,
                llm_prompt_tokens=evt.llm_prompt_tokens or 0,
                llm_completion_tokens=evt.llm_completion_tokens or 0,
            )
        return {"success": True, "trace_id": evt.trace_id, "agent": evt.agent, "status": evt.status}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/observability/ingest/batch")
async def ingest_events_batch(batch: IngestBatchRequest):
    """Ingest a batch of agent events. Processes all events; returns per-event status."""
    results = []
    errors = 0
    for raw in batch.events:
        try:
            evt = _normalize_ingest_event(raw.model_dump())
            observability_store.log_event(
                trace_id=evt.trace_id,
                request_id=evt.request_id,
                agent=evt.agent,
                action=evt.action,
                status=evt.status,
                span_id=evt.span_id,
                parent_span_id=evt.parent_span_id,
                event_type=evt.event_type,
                step_key=evt.step_key,
                latency_ms=evt.latency_ms,
                decision=evt.decision,
                error=evt.error,
                metadata=evt.metadata,
            )
            if evt.llm_prompt_tokens or evt.llm_completion_tokens:
                observability_store.log_complexity_metric(
                    agent=evt.agent,
                    action=evt.action,
                    trace_id=evt.trace_id,
                    llm_prompt_tokens=evt.llm_prompt_tokens or 0,
                    llm_completion_tokens=evt.llm_completion_tokens or 0,
                )
            results.append({"trace_id": evt.trace_id, "agent": evt.agent, "ok": True})
        except Exception as e:
            errors += 1
            results.append({"ok": False, "error": str(e)})
    return {
        "success": errors == 0,
        "total": len(results),
        "errors": errors,
        "results": results,
    }


@app.get("/api/observability/agent-complexity")
async def get_agent_complexity(agent: Optional[str] = None, window_days: int = 14):
    """Return RAG retrieval complexity trends per agent for degradation detection.

    Tracks rag_docs_retrieved, avg_similarity_score, and patterns_considered over time.
    Anomaly flagged when recent 3-day similarity drops >20% vs window baseline.
    """
    try:
        if agent:
            trends = observability_store.get_complexity_trends(agent=agent, window_days=window_days)
            return {"success": True, "timestamp": datetime.now(UTC).isoformat(), "complexity": trends}
        from datetime import timedelta
        cutoff = (datetime.now(UTC) - timedelta(days=window_days)).isoformat()
        c = observability_store.conn.cursor()
        agents = [
            r[0] for r in c.execute(
                "SELECT DISTINCT agent FROM agent_complexity_metrics WHERE timestamp >= ?", (cutoff,)
            ).fetchall()
        ]
        all_trends = [
            observability_store.get_complexity_trends(agent=a, window_days=window_days)
            for a in agents
        ]
        return {
            "success": True,
            "timestamp": datetime.now(UTC).isoformat(),
            "agents": agents,
            "complexity": all_trends,
            "anomalies": [t for t in all_trends if t.get("anomaly")],
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/observability/insights")
async def get_observability_insights(limit: int = 500):
    """Get aggregate observability insights (quality, failures, policy impact)."""
    try:
        insights = observability_store.get_global_insights(limit=limit)
        return {
            "success": True,
            "timestamp": datetime.now(UTC).isoformat(),
            "insights": insights,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ---------------------------------------------------------------------------
# Agent Factory endpoints
# ---------------------------------------------------------------------------

class AgentScaffoldRequest(BaseModel):
    framework: str
    agent_name: str
    capabilities: List[str] = []


@app.get("/api/agent-factory/frameworks")
async def list_agent_frameworks():
    """List all supported agent frameworks for scaffolding."""
    return {
        "success": True,
        "frameworks": list(SUPPORTED_FRAMEWORKS.keys()),
        "count": len(SUPPORTED_FRAMEWORKS),
    }


@app.post("/api/agent-factory/scaffold")
async def scaffold_agent(request: AgentScaffoldRequest):
    """
    Generate governed agent starter code for the requested framework.

    The generated code has AgenticQA's constitutional gate, feedback loop,
    and outcome tracker pre-wired. Save the output as a .py file to use.
    """
    if request.framework not in SUPPORTED_FRAMEWORKS:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported framework '{request.framework}'. "
                   f"Supported: {list(SUPPORTED_FRAMEWORKS.keys())}",
        )
    if not request.agent_name.strip():
        raise HTTPException(status_code=400, detail="agent_name cannot be empty.")

    try:
        factory = AgentFactory()
        result = factory.scaffold(
            framework=request.framework,
            agent_name=request.agent_name.strip(),
            capabilities=request.capabilities,
        )
        return {"success": True, **result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


class SandboxWrapRequest(BaseModel):
    agent_name: str
    script_path: str
    capabilities: List[str] = []
    allowed_dir: str = "."
    timeout_s: int = 30
    env_passthrough: List[str] = []
    block_on_flag: bool = True


@app.post("/api/agent-factory/sandbox-wrap")
async def sandbox_wrap_agent(request: SandboxWrapRequest):
    """
    Register a sandboxed agent: subprocess isolation + constitutional gate + output scanner.

    The script_path must point to a standalone Python script that reads JSON from stdin
    and writes JSON to stdout. The agent runs in a clean environment (no inherited secrets),
    with cwd locked to allowed_dir and a hard timeout.
    """
    if not request.agent_name.strip():
        raise HTTPException(status_code=400, detail="agent_name cannot be empty.")
    if not request.script_path.strip():
        raise HTTPException(status_code=400, detail="script_path cannot be empty.")

    try:
        wrapper = SandboxedAgentAdapter.wrap(
            script_path=request.script_path.strip(),
            agent_name=request.agent_name.strip(),
            capabilities=request.capabilities,
            allowed_dir=request.allowed_dir,
            timeout_s=request.timeout_s,
            env_passthrough=request.env_passthrough,
            block_on_flag=request.block_on_flag,
        )
        return {
            "success": True,
            "agent_name": wrapper.agent_name,
            "framework": wrapper.framework,
            "governed": True,
            "capabilities": wrapper.capabilities,
            "sandbox": {
                "allowed_dir": request.allowed_dir,
                "timeout_s": request.timeout_s,
                "env_passthrough": request.env_passthrough,
                "block_on_flag": request.block_on_flag,
            },
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


class FromPromptRequest(BaseModel):
    description: str
    framework: Optional[str] = None  # overrides LLM-inferred framework
    persist: bool = True


@app.post("/api/agent-factory/from-prompt")
async def scaffold_agent_from_prompt(request: FromPromptRequest):
    """
    Natural language → governed agent.

    1. LLM extracts an AgentSpec from the description.
    2. Optional framework override is applied.
    3. AgentFactory scaffolds governed code.
    4. If persist=True, saves to .agenticqa/custom_agents/{agent_name}.py in CWD.
    """
    if not request.description.strip():
        raise HTTPException(status_code=400, detail="description cannot be empty.")

    try:
        spec = NaturalLanguageSpecExtractor().extract(request.description)

        if request.framework:
            if request.framework not in SUPPORTED_FRAMEWORKS:
                raise HTTPException(
                    status_code=400,
                    detail=f"Unsupported framework '{request.framework}'. "
                           f"Supported: {list(SUPPORTED_FRAMEWORKS.keys())}",
                )
            spec.framework = request.framework

        scaffold_result = AgentFactory().scaffold(
            framework=spec.framework,
            agent_name=spec.agent_name,
            capabilities=spec.capabilities,
        )

        # Security scan generated code before persisting
        try:
            from agenticqa.security.agent_skill_scanner import AgentSkillScanner
        except ImportError:
            from src.agenticqa.security.agent_skill_scanner import AgentSkillScanner
        skill_scan = AgentSkillScanner().scan_source(
            scaffold_result["generated_code"],
            filename=f"{spec.agent_name}.py",
        )
        if not skill_scan.is_safe:
            raise HTTPException(
                status_code=422,
                detail={
                    "error": "Generated agent code failed security scan",
                    "findings": [
                        {"line": f.lineno, "attack_type": f.attack_type,
                         "severity": f.severity, "detail": f.detail}
                        for f in skill_scan.findings
                    ],
                    "risk_score": round(skill_scan.risk_score, 3),
                },
            )

        persisted_path = None
        if request.persist:
            out_dir = Path(".agenticqa") / "custom_agents"
            out_dir.mkdir(parents=True, exist_ok=True)
            out_file = out_dir / f"{spec.agent_name}.py"
            out_file.write_text(scaffold_result["generated_code"])
            persisted_path = str(out_file)

        return {
            "success": True,
            "spec": spec.to_dict(),
            "generated_code": scaffold_result["generated_code"],
            "install_hint": scaffold_result["install_hint"],
            "usage": scaffold_result["usage"],
            "persisted_path": persisted_path,
            "security_scan": skill_scan.to_dict(),
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ---------------------------------------------------------------------------
# Red Team Agent
# ---------------------------------------------------------------------------

class RedTeamScanRequest(BaseModel):
    mode: str = "fast"        # "fast" | "thorough"
    target: str = "both"      # "scanner" | "gate" | "both"
    auto_patch: bool = True


@app.post("/api/red-team/scan")
async def red_team_scan(request: RedTeamScanRequest):
    """Probe governance stack for bypasses and optionally self-patch OutputScanner patterns."""
    if request.mode not in ("fast", "thorough"):
        raise HTTPException(status_code=400, detail="mode must be 'fast' or 'thorough'")
    if request.target not in ("scanner", "gate", "both"):
        raise HTTPException(status_code=400, detail="target must be 'scanner', 'gate', or 'both'")
    try:
        agent = RedTeamAgent()
        result = agent.execute({
            "mode": request.mode,
            "target": request.target,
            "auto_patch": request.auto_patch,
        })
        return {"success": True, **result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/redteam/history")
async def redteam_history(mode: str = "", limit: int = 50, window: int = 10):
    """Return red team scan history, trend curves, and security posture summary."""
    try:
        from data_store.redteam_history import RedTeamHistoryStore
        store = RedTeamHistoryStore()
        mode_filter = mode or None
        history = store.load_history(mode_filter=mode_filter, limit=limit)
        scanner_trend = store.get_trend("scanner_strength", window=window, mode_filter=mode_filter)
        gate_trend = store.get_trend("gate_strength", window=window, mode_filter=mode_filter)
        bypass_trend = store.get_trend("successful_bypasses", window=window, mode_filter=mode_filter)
        summary = store.summary(window=window, mode_filter=mode_filter)
        return {
            "success": True,
            "history": history,
            "trends": {
                "scanner_strength": scanner_trend,
                "gate_strength": gate_trend,
                "successful_bypasses": bypass_trend,
            },
            "summary": summary,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/sdet/generated-tests")
async def sdet_generated_tests(repo_path: str = "."):
    """List all LLM-generated test files in .agenticqa/generated_tests/."""
    try:
        from pathlib import Path as _Path
        gen_dir = _Path(repo_path) / ".agenticqa" / "generated_tests"
        if not gen_dir.exists():
            return {"success": True, "files": [], "count": 0}
        files = []
        for test_file in sorted(gen_dir.glob("test_*.py")):
            try:
                files.append({
                    "name": test_file.name,
                    "path": str(test_file),
                    "size_bytes": test_file.stat().st_size,
                    "preview": test_file.read_text()[:500],
                })
            except Exception:
                continue
        return {"success": True, "files": files, "count": len(files)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/developer-profiles")
async def developer_profiles(repo_path: str = ".", top_n: int = 10):
    """Return the developer risk leaderboard for the given repo."""
    try:
        import hashlib
        import subprocess as _sp
        from data_store.developer_profile import DeveloperRiskLeaderboard
        try:
            _proc = _sp.run(
                ["git", "remote", "get-url", "origin"],
                capture_output=True, text=True, timeout=5, cwd=repo_path,
            )
            _url = _proc.stdout.strip().lower().rstrip("/").removesuffix(".git")
            repo_id = hashlib.sha1(_url.encode()).hexdigest()[:12] if _url else "unknown"
        except Exception:
            repo_id = hashlib.sha1(repo_path.encode()).hexdigest()[:12]
        board = DeveloperRiskLeaderboard(repo_id)
        return {"success": True, "repo_id": repo_id, "leaderboard": board.top_n(top_n)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/org-memory")
async def org_memory(repo_path: str = "."):
    """Return cross-repo org memory for the org owning the given repo."""
    try:
        from data_store.org_memory import OrgMemory
        mem = OrgMemory.for_repo(repo_path)
        return {"success": True, **mem.summary()}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/semantic-diff")
async def semantic_diff(
    repo_path: str = ".",
    base: str = "HEAD~1",
    head: str = "HEAD",
):
    """
    Analyze what semantically changed between two git refs.

    Returns high/medium risk removals: null checks, error handlers, auth decorators,
    input validation, timeouts, and assertions.
    """
    try:
        from agenticqa.diff.semantic_diff import SemanticDiffAnalyzer
        result = SemanticDiffAnalyzer().analyze_git_range(base=base, head=head, cwd=repo_path)
        return {"success": True, **result.summary()}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/compliance/drift")
async def compliance_drift(repo_path: str = ".", lookback: int = 10):
    """Return compliance violation drift between the last two runs for this repo."""
    try:
        from agenticqa.compliance.drift_detector import ComplianceDriftDetector
        detector = ComplianceDriftDetector()
        drift = detector.detect_drift(repo_path, lookback=lookback)
        history = detector.history(repo_path, limit=30)
        return {"success": True, "drift": drift, "history": history}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/risk-gate")
async def risk_gate(
    repo_path: str = ".",
    files: List[str] = Query(default=[]),
    threshold: float = 0.70,
):
    """
    Evaluate changed files against developer risk scores.

    Pass ?files=src/foo.py&files=src/bar.py to check specific files.
    Returns gate=pass|block with per-file risk details.
    """
    try:
        import hashlib
        import subprocess as _sp
        from agenticqa.gates.risk_gate import DeveloperRiskGate
        try:
            _proc = _sp.run(
                ["git", "remote", "get-url", "origin"],
                capture_output=True, text=True, timeout=5, cwd=repo_path,
            )
            _url = _proc.stdout.strip().lower().rstrip("/").removesuffix(".git")
            repo_id = hashlib.sha1(_url.encode()).hexdigest()[:12] if _url else "unknown"
        except Exception:
            repo_id = hashlib.sha1(repo_path.encode()).hexdigest()[:12]
        gate = DeveloperRiskGate(threshold=threshold)
        result = gate.evaluate(files, repo_id=repo_id, cwd=repo_path)
        return {"success": True, "repo_id": repo_id, **result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/github/pr-inline-comments")
async def post_inline_comments(request: dict):
    """Post inline review comments on specific PR diff lines."""
    try:
        from agenticqa.github.pr_commenter import PRCommenter
        commenter = PRCommenter()
        pr_number = request.get("pr_number")
        if not pr_number:
            pr_number = commenter._detect_pr_number()
        if not pr_number:
            return {"success": False, "reason": "no PR detected"}
        posted = commenter.post_inline_comments(
            pr_number=int(pr_number),
            findings=request.get("findings", []),
            commit_sha=request.get("commit_sha"),
        )
        return {"success": True, "posted": posted}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/github/pr-comment")
async def post_pr_comment_endpoint(request: dict):
    """Post or update AgenticQA CI results as a PR comment."""
    try:
        from agenticqa.github.pr_commenter import CIResultBundle, PRCommenter

        redteam = request.get("redteam") or {}
        sdet = request.get("sdet") or {}
        compliance = request.get("compliance") or {}
        sre = request.get("sre") or {}
        qa = request.get("qa") or {}

        bundle = CIResultBundle(
            run_id=request.get("run_id", "unknown"),
            commit_sha=request.get("commit_sha", "unknown"),
            total_tests=qa.get("total_tests"),
            tests_passed=qa.get("passed"),
            tests_failed=qa.get("failed"),
            coverage_percent=sdet.get("current_coverage"),
            coverage_status=sdet.get("coverage_status"),
            tests_generated=sdet.get("tests_generated"),
            sre_total_errors=sre.get("total_errors"),
            sre_fix_rate=sre.get("fix_rate"),
            sre_fixes_applied=sre.get("fixes_applied"),
            scanner_strength=redteam.get("scanner_strength"),
            gate_strength=redteam.get("gate_strength"),
            successful_bypasses=redteam.get("successful_bypasses"),
            compliance_violations=len(compliance.get("violations", [])) if compliance else None,
            reachable_cves=compliance.get("reachable_cves"),
            cve_risk_score=compliance.get("cve_risk_score"),
        )
        commenter = PRCommenter()
        pr_number = request.get("pr_number")
        success = commenter.post_results(bundle, pr_number=pr_number)
        return {"success": success, "pr_number": pr_number}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/security/cve-reachability")
async def cve_reachability(repo_path: str = "."):
    """Scan the repo for CVEs (pip-audit + npm audit) and determine import-level reachability."""
    try:
        from agenticqa.security.cve_reachability import CVEReachabilityAnalyzer
        analyzer = CVEReachabilityAnalyzer()
        py_result = analyzer.scan_python(repo_path)
        js_result = analyzer.scan_javascript(repo_path)
        return {
            "success": True,
            "python": {
                "total_cves": len(py_result.cves),
                "reachable_cves": [
                    {
                        "package": c.package,
                        "cve_id": c.cve_id,
                        "severity": c.severity,
                        "fixed_version": c.fixed_version,
                        "reachable_via": c.reachable_via,
                    }
                    for c in py_result.reachable_cves
                ],
                "unreachable_count": len(py_result.unreachable_cves),
                "risk_score": py_result.risk_score,
                "scan_error": py_result.scan_error,
            },
            "javascript": {
                "total_cves": len(js_result.cves),
                "reachable_cves": [
                    {
                        "package": c.package,
                        "cve_id": c.cve_id,
                        "severity": c.severity,
                        "fixed_version": c.fixed_version,
                        "reachable_via": c.reachable_via,
                    }
                    for c in js_result.reachable_cves
                ],
                "unreachable_count": len(js_result.unreachable_cves),
                "risk_score": js_result.risk_score,
                "scan_error": js_result.scan_error,
            },
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/compliance/legal-risk")
async def legal_risk_scan(repo_path: str = "."):
    """Scan a repo for legal compliance risks: credentials, PII docs, privilege exposure, SSRF, missing auth."""
    try:
        from agenticqa.security.legal_risk_scanner import LegalRiskScanner
        result = LegalRiskScanner().scan(repo_path)
        return {
            "success": True,
            "risk_score": result.risk_score,
            "total_findings": len(result.findings),
            "critical_findings": len(result.critical_findings),
            "scan_error": result.scan_error,
            "findings": [
                {
                    "file": f.file,
                    "line": f.line,
                    "rule_id": f.rule_id,
                    "severity": f.severity,
                    "message": f.message,
                    "evidence": f.evidence,
                }
                for f in result.findings
            ],
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/regression/compare")
async def regression_compare(
    agent: str,
    baseline_model: str,
    candidate_model: str,
    candidate_output: str = "",
    run_id: str = "local",
):
    """Compare a candidate model output against the stored golden snapshot."""
    try:
        from agenticqa.regression.model_regression import ModelRegressionTester
        tester = ModelRegressionTester()
        result = tester.compare(
            agent_name=agent,
            baseline_model=baseline_model,
            candidate_model=candidate_model,
            candidate_output=candidate_output,
            input_data={"agent": agent},
        )
        return {
            "agent": result.agent_name,
            "baseline_model": result.baseline_model,
            "candidate_model": result.candidate_model,
            "similarity_score": result.similarity_score,
            "regression_detected": result.regression_detected,
            "threshold_used": result.threshold_used,
            "has_baseline": result.baseline_snapshot is not None,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/provenance/verify")
async def provenance_verify(output_hash: str, agent: str):
    """Verify an AI output hash against the provenance log."""
    try:
        from agenticqa.provenance.output_provenance import OutputProvenanceLogger
        result = OutputProvenanceLogger().verify_by_hash(output_hash, agent)
        return {
            "valid": result.valid,
            "reason": result.reason,
            "record": {
                "output_hash": result.record.output_hash,
                "model_id": result.record.model_id,
                "agent_name": result.record.agent_name,
                "timestamp": result.record.timestamp,
                "run_id": result.record.run_id,
                "output_length": result.record.output_length,
            } if result.record else None,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/provenance/chain")
async def provenance_chain(agent: str, limit: int = 20):
    """Return the most-recent provenance records for an agent."""
    try:
        from agenticqa.provenance.output_provenance import OutputProvenanceLogger
        records = OutputProvenanceLogger().get_chain(agent, limit=limit)
        return {
            "agent": agent,
            "count": len(records),
            "records": [
                {"output_hash": r.output_hash, "model_id": r.model_id,
                 "timestamp": r.timestamp, "run_id": r.run_id,
                 "output_length": r.output_length}
                for r in records
            ],
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/compliance/ai-model-sbom")
async def ai_model_sbom_scan(repo_path: str = "."):
    """Produce an AI Model SBOM: inventory of all ML models, providers, licenses, and risk flags."""
    try:
        from agenticqa.security.ai_model_sbom import AIModelSBOMScanner
        result = AIModelSBOMScanner().scan(repo_path)
        return {
            "success": True,
            "providers_detected": result.providers_detected,
            "unique_models": len(result.unique_model_ids),
            "unique_model_ids": result.unique_model_ids,
            "license_violations": len(result.license_violations),
            "risk_score": result.risk_score,
            "scan_error": result.scan_error,
            "components": [
                {
                    "model_id": c.model_id,
                    "provider": c.provider,
                    "license": c.license,
                    "risk_flags": c.risk_flags,
                    "source_file": c.source_file,
                    "source_line": c.source_line,
                }
                for c in result.components
            ],
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/compliance/hipaa")
async def hipaa_phi_scan(repo_path: str = "."):
    """Scan repo for HIPAA PHI risks: hardcoded SSN/DOB/MRN, PHI in logs, PHI to LLM, missing audit."""
    try:
        from agenticqa.security.hipaa_phi_scanner import HIPAAPHIScanner
        result = HIPAAPHIScanner().scan(repo_path)
        return {
            "success": True,
            "risk_score": result.risk_score,
            "total_findings": len(result.findings),
            "critical_findings": len(result.critical_findings),
            "scan_error": result.scan_error,
            "findings": [
                {"file": f.file, "line": f.line, "rule_id": f.rule_id,
                 "severity": f.severity, "message": f.message, "evidence": f.evidence}
                for f in result.findings
            ],
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/compliance/ai-act")
async def ai_act_check(repo_path: str = "."):
    """Check EU AI Act conformity: Annex III classification + Art.9/13/14/22 evidence."""
    try:
        from agenticqa.compliance.ai_act import AIActComplianceChecker
        result = AIActComplianceChecker().check(repo_path)
        return {
            "success": True,
            "risk_category": result.risk_category,
            "annex_iii_match": result.annex_iii_match,
            "conformity_score": result.conformity_score,
            "scan_error": result.scan_error,
            "findings": [
                {"article": f.article, "requirement": f.requirement, "status": f.status,
                 "severity": f.severity, "evidence": f.evidence, "remediation": f.remediation}
                for f in result.findings
            ],
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/redteam/prompt-injection")
async def prompt_injection_scan(repo_path: str = "."):
    """Scan repo for prompt injection attack surface."""
    try:
        from agenticqa.security.prompt_injection_scanner import PromptInjectionScanner
        result = PromptInjectionScanner().scan(repo_path)
        return {
            "success": True,
            "surface_score": result.surface_score,
            "total_findings": len(result.findings),
            "scan_error": result.scan_error,
            "findings": [
                {"file": f.file, "line": f.line, "rule_id": f.rule_id,
                 "severity": f.severity, "message": f.message, "evidence": f.evidence}
                for f in result.findings
            ],
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/redteam/agent-trust-graph")
async def agent_trust_graph_scan(repo_path: str = "."):
    """Analyze multi-agent trust graph: circular trust, missing human oversight, privileged tools, escalation paths."""
    try:
        from agenticqa.security.agent_trust_graph import AgentTrustGraphAnalyzer
        result = AgentTrustGraphAnalyzer().analyze(repo_path)
        return {
            "success": True,
            "frameworks_detected": result.frameworks_detected,
            "agent_nodes": len(result.nodes),
            "agent_edges": len(result.edges),
            "violations": len(result.violations),
            "has_human_oversight": result.has_human_oversight,
            "risk_score": result.risk_score,
            "scan_error": result.scan_error,
            "nodes": [
                {"name": n.name, "framework": n.framework, "tools": n.tools,
                 "human_input_mode": n.human_input_mode,
                 "source_file": n.source_file, "source_line": n.source_line}
                for n in result.nodes
            ],
            "edges": [
                {"source": e.source, "target": e.target, "edge_type": e.edge_type,
                 "framework": e.framework, "source_file": e.source_file, "source_line": e.source_line}
                for e in result.edges
            ],
            "trust_violations": [
                {"rule_id": v.rule_id, "severity": v.severity, "message": v.message,
                 "agents_involved": v.agents_involved, "source_file": v.source_file,
                 "source_line": v.source_line, "remediation": v.remediation}
                for v in result.violations
            ],
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/security/mcp-scan")
async def mcp_security_scan(repo_path: str = "."):
    """Scan MCP server definitions and implementations for security vulnerabilities."""
    try:
        from agenticqa.security.mcp_scanner import MCPSecurityScanner
        result = MCPSecurityScanner().scan(repo_path)
        return {
            "success": True,
            "files_scanned": result.files_scanned,
            "tools_scanned": result.tools_scanned,
            "servers_scanned": result.servers_scanned,
            "risk_score": result.risk_score,
            "attack_types_detected": result.attack_types_detected,
            "total_findings": len(result.findings),
            "critical_count": len(result.critical_findings),
            "high_count": len(result.high_findings),
            "scan_error": result.scan_error,
            "findings": [
                {
                    "tool_name": f.tool_name,
                    "attack_type": f.attack_type,
                    "severity": f.severity,
                    "description": f.description,
                    "evidence": f.evidence,
                    "source_file": f.source_file,
                    "line_number": f.line_number,
                    "cwe": f.cwe,
                    "cvss_score": f.cvss_score,
                }
                for f in result.findings
            ],
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/security/data-flow-trace")
async def data_flow_trace(repo_path: str = "."):
    """Trace sensitive data (PII/credentials) flows across agent trust boundaries."""
    try:
        from agenticqa.security.data_flow_tracer import CrossAgentDataFlowTracer
        report = CrossAgentDataFlowTracer().trace(repo_path)
        return {
            "success": True,
            "files_scanned": report.files_scanned,
            "agents_analyzed": report.agents_analyzed,
            "tainted_variables_detected": report.tainted_variables_detected,
            "risk_score": report.risk_score,
            "finding_types": report.finding_types,
            "total_findings": len(report.findings),
            "critical_count": len(report.critical_findings),
            "scan_error": report.scan_error,
            "findings": [
                {
                    "finding_type": f.finding_type,
                    "severity": f.severity,
                    "data_type": f.data_type,
                    "description": f.description,
                    "source_agent": f.source_agent,
                    "sink_agent": f.sink_agent,
                    "sanitized": f.sanitized,
                    "source_file": f.source_file,
                    "line_number": f.line_number,
                    "remediation": f.remediation,
                    "trace": [
                        {"agent": h.agent_name, "file": h.source_file,
                         "line": h.line_number, "op": h.operation,
                         "evidence": h.evidence}
                        for h in f.trace
                    ],
                }
                for f in report.findings
            ],
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/security/skill-scan")
async def skill_scan(agents_dir: str = ".agenticqa/custom_agents"):
    """
    AST-scan all custom agent skill files for dangerous patterns.

    Returns a per-file report with findings (attack_type, severity, line) and
    an aggregate risk score. Files with critical findings or risk_score >= 0.5
    have is_safe=False and should not be loaded.
    """
    try:
        from agenticqa.security.agent_skill_scanner import AgentSkillScanner
    except ImportError:
        from src.agenticqa.security.agent_skill_scanner import AgentSkillScanner
    try:
        scanner = AgentSkillScanner()
        results = scanner.scan_directory(agents_dir)
        total = len(results)
        safe = sum(1 for r in results if r.is_safe)
        blocked = total - safe
        return {
            "success": True,
            "agents_dir": agents_dir,
            "total_files": total,
            "safe": safe,
            "blocked": blocked,
            "results": [r.to_dict() for r in results],
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/temporal/violations")
async def temporal_violations(
    repo_id: str,
    days: int = 30,
    granularity: str = "day",
):
    """Return time-bucketed violation counts from Neo4j temporal graph."""
    try:
        from agenticqa.graph.temporal_graph import TemporalViolationStore
        store = TemporalViolationStore()
        return {
            "success": True,
            "trend": store.get_violation_trend(repo_id, days=days, granularity=granularity),
            "fix_rate": store.get_fix_rate_trend(repo_id, days=days),
            "top_rules": store.get_top_rules_over_time(repo_id, days=days, top_n=10),
            "agents": store.get_agent_comparison(repo_id, days=days),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/learning-metrics")
async def learning_metrics(repo_id: str = "", limit: int = 30):
    """Return per-run learning metrics history and improvement curve."""
    try:
        from data_store.learning_metrics import LearningMetricsSnapshot
        snap = LearningMetricsSnapshot()
        rid = repo_id or None
        history = snap.load_history(repo_id=rid, limit=limit)
        summary = snap.summary(repo_id=rid, window=min(limit, 10))
        curves = {
            metric: snap.get_improvement_curve(metric, repo_id=rid, window=limit)
            for metric in ("fix_rate", "artifact_count", "delegation_pairs")
        }
        return {"success": True, "summary": summary, "history": history, "curves": curves}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/repo-profile")
async def repo_profile_endpoint(repo_path: str = "."):
    """Return the current repo's RepoProfile including run_history for trend charts."""
    try:
        from data_store.repo_profile import RepoProfile
        import hashlib, subprocess as _sp
        try:
            _proc = _sp.run(
                ["git", "remote", "get-url", "origin"],
                capture_output=True, text=True, timeout=5, cwd=repo_path,
            )
            _url = _proc.stdout.strip().lower().rstrip("/").removesuffix(".git")
            repo_id = hashlib.sha1(_url.encode()).hexdigest()[:12] if _url else "unknown"
        except Exception:
            repo_id = hashlib.sha1(repo_path.encode()).hexdigest()[:12]
        profile = RepoProfile(repo_id)
        return {"success": True, "repo_id": repo_id, "profile": profile._data}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/export/sarif")
async def export_sarif(request: Request):
    """
    Convert agent results to SARIF 2.1.0 for GitHub Code Scanning.

    Body: {sre?: {...}, compliance?: {...}, redteam?: {...}, repo_root?: str}
    Returns SARIF JSON (application/json).
    """
    try:
        body = await request.json()
        import sys as _sys
        _sys.path.insert(0, str(Path(__file__).parent / "src"))
        from agenticqa.export.sarif import SARIFExporter
        exporter = SARIFExporter(repo_root=body.get("repo_root", "."))
        total = 0
        if body.get("sre"):
            total += exporter.add_sre_result(body["sre"])
        if body.get("compliance"):
            total += exporter.add_compliance_result(body["compliance"])
        if body.get("redteam"):
            total += exporter.add_redteam_result(body["redteam"])
        return {"sarif": exporter.to_dict(), "finding_count": total}
    except Exception as e:
        return {"error": str(e)}


@app.post("/api/gdpr/erasure-request")
async def gdpr_erasure_request(request: Request):
    """
    Create a GDPR Art.17 erasure request for a tenant.
    Body: {"tenant_id": str, "subject_id": str}
    Returns: {"request_id": str, "requested_at": float, "status": "pending"}
    """
    try:
        body = await request.json()
        tenant_id = body.get("tenant_id", "")
        subject_id = body.get("subject_id", "")
        if not tenant_id:
            raise HTTPException(status_code=400, detail="tenant_id is required")
        from agenticqa.security.gdpr_erasure_verifier import GDPREraseVerifier
        req = GDPREraseVerifier().request_erasure(tenant_id=tenant_id, subject_id=subject_id)
        return req.__dict__
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/gdpr/erasure-status/{request_id}")
async def gdpr_erasure_status(request_id: str):
    """
    Verify that all stores have been purged for a given erasure request.
    Returns ErasureVerificationResult with per-store clean/residual status.
    """
    try:
        from agenticqa.security.gdpr_erasure_verifier import GDPREraseVerifier
        result = GDPREraseVerifier().verify_erasure(request_id)
        return result.to_dict()
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/security/audit-chain")
async def audit_chain_log(
    tenant_id: str = "",
    limit: int = 100,
):
    """
    Return the verified immutable audit chain (EU AI Act Art.12 compliance log).
    Query: ?tenant_id=xxx&limit=100
    """
    try:
        from agenticqa.security.immutable_audit import ImmutableAuditChain
        chain = ImmutableAuditChain()
        ok, violations = chain.verify_chain()
        entries = chain.get_compliance_log(
            tenant_id=tenant_id or None,
            limit=limit,
        )
        return {
            "chain_length": chain.length(),
            "chain_intact": ok,
            "violations": [str(v) for v in violations],
            "entries": entries,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/security/classify-intent")
async def classify_intent(request: Request):
    """
    Run SemanticIntentClassifier on a text snippet.
    Body: {"text": str}
    Returns: attack_class, probability, confidence, top_terms
    """
    try:
        body = await request.json()
        text = body.get("text", "")
        from agenticqa.security.semantic_classifier import SemanticIntentClassifier
        result = SemanticIntentClassifier().classify(text)
        return {
            "attack_class": result.attack_class,
            "probability": result.probability,
            "confidence": result.confidence,
            "top_terms": result.top_terms,
            "all_scores": result.all_scores,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/security/ci-scan")
async def ci_yaml_scan(path: str = ".github/workflows"):
    """
    Scan GitHub Actions YAML files for injection vulnerabilities.
    Query: ?path=.github/workflows
    """
    try:
        from agenticqa.security.ci_yaml_scanner import CIYAMLInjectionScanner
        results = CIYAMLInjectionScanner().scan_directory(path)
        return {
            "files_scanned": len(results),
            "files_with_findings": sum(1 for r in results if r.findings),
            "critical": sum(
                1 for r in results for f in r.findings if f.severity == "critical"
            ),
            "results": [
                {
                    "path": r.path,
                    "risk_score": r.risk_score,
                    "is_safe": r.is_safe,
                    "findings": [f.__dict__ for f in r.findings],
                }
                for r in results
            ],
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/security/architecture-scan")
async def architecture_scan(repo_path: str = "."):
    """
    Scan a repository for integration areas and attack surface.

    Returns plain-English findings, attack vectors per integration,
    test coverage confidence, and attack surface score (0–100).

    Query: ?repo_path=/path/to/repo  (default: current directory)
    """
    try:
        from agenticqa.security.architecture_scanner import ArchitectureScanner
        result = ArchitectureScanner().scan(repo_path)
        payload = {
            "success": True,
            "repo_path": result.repo_path,
            "files_scanned": result.files_scanned,
            "attack_surface_score": result.attack_surface_score,
            "test_coverage_confidence": result.test_coverage_confidence,
            "total_integration_areas": len(result.integration_areas),
            "untested_count": len(result.untested_areas),
            "critical_count": len(result.critical_areas),
            "categories": {k: len(v) for k, v in result.by_category().items()},
            "plain_english_report": result.plain_english_report(),
            "integration_areas": [a.to_dict() for a in result.integration_areas],
            "scan_error": result.scan_error,
        }
        # Auto-save to learning store so scan history feeds the data flywheel
        try:
            from data_store.artifact_store import TestArtifactStore
            _astore = TestArtifactStore(
                os.getenv("AGENTICQA_ARTIFACT_STORE", ".test-artifact-store")
            )
            _astore.store_artifact(
                artifact_data={"artifact_type": "architecture_scan", **result.to_dict()},
                artifact_type="architecture_scan",
                source=repo_path,
                tags=["architecture", "security",
                      f"score_{int(result.attack_surface_score)}"],
            )
        except Exception:
            pass  # non-blocking — scan result returned regardless
        return payload
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ── Agent Safety: Destructive Action Interceptor ──────────────────────────────

_interceptor_singleton = None

def _get_interceptor():
    global _interceptor_singleton
    if _interceptor_singleton is None:
        from agenticqa.security.destructive_action_interceptor import DestructiveActionInterceptor
        _interceptor_singleton = DestructiveActionInterceptor()
    return _interceptor_singleton


class InterceptRequest(BaseModel):
    tool_name: str
    parameters: dict = {}
    agent_id: str = "unknown"
    session_id: str = ""
    context_snippet: str = ""


@app.post("/api/safety/intercept")
async def intercept_action(req: InterceptRequest):
    """Classify and gate a tool call before execution."""
    from agenticqa.security.destructive_action_interceptor import ActionCall
    interceptor = _get_interceptor()
    call = ActionCall(
        tool_name=req.tool_name,
        parameters=req.parameters,
        agent_id=req.agent_id,
        session_id=req.session_id,
        context_snippet=req.context_snippet,
    )
    verdict = interceptor.intercept(call)
    return verdict.to_dict()


@app.get("/api/safety/pending")
async def get_pending_approvals():
    """List all pending approval requests requiring human sign-off."""
    interceptor = _get_interceptor()
    return {"pending": interceptor.get_pending_approvals()}


@app.post("/api/safety/approve/{token}")
async def approve_action(token: str, approved_by: str = "human"):
    """Approve a pending action by its approval token."""
    interceptor = _get_interceptor()
    ok = interceptor.approve(token, approved_by=approved_by)
    if not ok:
        raise HTTPException(status_code=404, detail="Token not found or expired")
    return {"approved": True, "token": token}


@app.post("/api/safety/deny/{token}")
async def deny_action(token: str):
    """Deny and remove a pending approval request."""
    interceptor = _get_interceptor()
    ok = interceptor.deny(token)
    return {"denied": ok, "token": token}


# ── Agent Safety: Scope Lease Manager ────────────────────────────────────────

_lease_mgr_singleton = None

def _get_lease_mgr():
    global _lease_mgr_singleton
    if _lease_mgr_singleton is None:
        from agenticqa.security.scope_lease_manager import AgentScopeLeaseManager
        _lease_mgr_singleton = AgentScopeLeaseManager()
    return _lease_mgr_singleton


class LeaseCreateRequest(BaseModel):
    agent_id: str
    session_id: str = ""
    label: str = "standard"        # standard | readonly | elevated | custom
    max_reads: int = 2147483647
    max_writes: int = 50
    max_deletes: int = 0
    max_executes: int = 0
    lease_ttl_seconds: int = 600


class LeaseCheckRequest(BaseModel):
    lease_id: str
    action: str   # read | write | delete | execute (or tool name alias)


@app.post("/api/safety/lease")
async def create_lease(req: LeaseCreateRequest):
    """Issue a new scope lease for an agent session."""
    from agenticqa.security.scope_lease_manager import LeaseConfig
    mgr = _get_lease_mgr()
    if req.label == "readonly":
        config = LeaseConfig.readonly()
    elif req.label == "elevated":
        config = LeaseConfig.elevated(max_deletes=req.max_deletes, max_executes=req.max_executes)
    else:
        config = LeaseConfig(
            max_reads=req.max_reads,
            max_writes=req.max_writes,
            max_deletes=req.max_deletes,
            max_executes=req.max_executes,
            lease_ttl_seconds=req.lease_ttl_seconds,
            label=req.label,
        )
    lease_id = mgr.create_lease(req.agent_id, req.session_id, config)
    return {"lease_id": lease_id, **mgr.get_lease_status(lease_id)}


@app.get("/api/safety/lease/{lease_id}")
async def get_lease(lease_id: str):
    """Get current status and counters for a lease."""
    mgr = _get_lease_mgr()
    status = mgr.get_lease_status(lease_id)
    if not status:
        raise HTTPException(status_code=404, detail=f"Lease {lease_id} not found")
    return status


@app.post("/api/safety/lease/check")
async def check_lease(req: LeaseCheckRequest):
    """Check-and-consume one operation unit from a lease (hard enforcement)."""
    mgr = _get_lease_mgr()
    allowed, reason = mgr.check_and_consume(req.lease_id, req.action)
    if not allowed:
        raise HTTPException(status_code=403, detail=reason)
    return {"allowed": True, "reason": reason}


@app.delete("/api/safety/lease/{lease_id}")
async def revoke_lease(lease_id: str, reason: str = "manual revocation"):
    """Immediately revoke a lease — all further ops blocked."""
    mgr = _get_lease_mgr()
    ok = mgr.revoke_lease(lease_id, reason=reason)
    if not ok:
        raise HTTPException(status_code=404, detail=f"Lease {lease_id} not found")
    return {"revoked": True, "lease_id": lease_id}


@app.get("/api/safety/leases")
async def list_leases():
    """List all active (non-expired, non-revoked) leases."""
    mgr = _get_lease_mgr()
    return {"leases": mgr.list_active_leases()}


# ── Agent Safety: Instruction Persistence Warden ─────────────────────────────

_warden_singleton = None

def _get_warden():
    global _warden_singleton
    if _warden_singleton is None:
        from agenticqa.security.instruction_persistence_warden import InstructionPersistenceWarden
        _warden_singleton = InstructionPersistenceWarden()
    return _warden_singleton


class WardCheckRequest(BaseModel):
    session_id: str
    messages: list = []           # [{role, content}, ...]
    recent_output: str = ""


class GuardrailRegisterRequest(BaseModel):
    session_id: str
    guardrails: list              # [{name, content, drift_signals?, priority?}]


@app.post("/api/safety/warden/register")
async def register_guardrails(req: GuardrailRegisterRequest):
    """Register immutable guardrail blocks for a session."""
    from agenticqa.security.instruction_persistence_warden import GuardrailBlock
    warden = _get_warden()
    blocks = [
        GuardrailBlock(
            name=g.get("name", f"guardrail_{i}"),
            content=g.get("content", ""),
            drift_signals=g.get("drift_signals", []),
            priority=g.get("priority", 0),
        )
        for i, g in enumerate(req.guardrails)
    ]
    warden.register_guardrails(req.session_id, blocks)
    return {"registered": len(blocks), "session_id": req.session_id}


@app.post("/api/safety/warden/check")
async def warden_check(req: WardCheckRequest):
    """Check compaction risk and constraint drift for a session."""
    warden = _get_warden()
    report = warden.check(req.session_id, req.messages, req.recent_output)
    return report.to_dict()


@app.get("/api/safety/warden/prompt/{session_id}")
async def get_reinforced_prompt(session_id: str, base_prompt: str = ""):
    """Get a system prompt with all guardrail blocks re-injected."""
    warden = _get_warden()
    prompt = warden.get_reinforced_system_prompt(session_id, base_prompt)
    return {"session_id": session_id, "reinforced_prompt": prompt}


# ── Release Readiness Scorer ──────────────────────────────────────────────────

try:
    from src.agenticqa.scoring.release_readiness import ReleaseReadinessScorer
except ImportError:
    from agenticqa.scoring.release_readiness import ReleaseReadinessScorer

_readiness_scorer = ReleaseReadinessScorer()


class ReadinessRequest(BaseModel):
    sdet_result: Optional[Dict[str, Any]] = None
    security_findings: Optional[List[Dict[str, Any]]] = None
    cve_result: Optional[Dict[str, Any]] = None
    perf_result: Optional[Dict[str, Any]] = None
    compliance_result: Optional[Dict[str, Any]] = None
    architecture_result: Optional[Dict[str, Any]] = None


@app.post("/api/release-readiness")
async def release_readiness(req: ReadinessRequest):
    """
    Aggregate all AgenticQA signals into a single 0-100 Release Readiness Score.
    Returns SHIP IT / REVIEW REQUIRED / DO NOT SHIP with per-signal breakdown.
    Any subset of signals can be provided — missing ones are excluded from scoring.
    """
    report = _readiness_scorer.score(
        sdet_result=req.sdet_result,
        security_findings=req.security_findings,
        cve_result=req.cve_result,
        perf_result=req.perf_result,
        compliance_result=req.compliance_result,
        architecture_result=req.architecture_result,
    )
    return {"success": True, **report.to_dict()}


# ── Intent-to-Code Verifier ───────────────────────────────────────────────────

try:
    from src.agenticqa.security.intent_verifier import IntentToCodeVerifier
except ImportError:
    from agenticqa.security.intent_verifier import IntentToCodeVerifier

_intent_verifier = IntentToCodeVerifier(static_only=True)


class IntentVerifyRequest(BaseModel):
    intent: str
    code_diff: str
    file_path: str = ""
    llm_assisted: bool = False


@app.post("/api/security/intent-verify")
async def intent_verify(req: IntentVerifyRequest):
    """
    Verify that an LLM-generated code diff actually implements the stated intent.
    Detects: hallucinated APIs, intent gaps, stub-only implementations, syntax errors.
    Set llm_assisted=true to enable Claude Haiku semantic analysis (requires ANTHROPIC_API_KEY).
    """
    verifier = IntentToCodeVerifier(static_only=not req.llm_assisted)
    result = verifier.verify(
        intent=req.intent,
        code_diff=req.code_diff,
        file_path=req.file_path,
    )
    return {"success": True, **result.to_dict()}


# ── OWASP Top 10 Scanner ──────────────────────────────────────────────────────

try:
    from src.agenticqa.security.owasp_scanner import OWASPScanner
except ImportError:
    from agenticqa.security.owasp_scanner import OWASPScanner


@app.get("/api/security/owasp-scan")
async def owasp_scan(repo_path: str = "."):
    """
    Static analysis covering OWASP Top 10 (2021): Injection, Broken Auth,
    Crypto Failures, Misconfiguration, SSRF, Insecure Deserialisation, and more.
    Returns findings grouped by OWASP category with severity and CWE references.
    """
    result = OWASPScanner().scan(repo_path)
    return {"success": True, **result.to_dict()}


# ── Blast Radius Analyzer ─────────────────────────────────────────────────────

try:
    from src.agenticqa.security.blast_radius import BlastRadiusAnalyzer
except ImportError:
    from agenticqa.security.blast_radius import BlastRadiusAnalyzer


class BlastRadiusRequest(BaseModel):
    repo_path: str = "."
    changed_files: List[str] = []


@app.post("/api/security/blast-radius")
async def blast_radius(req: BlastRadiusRequest):
    """
    Analyze which modules are affected by a set of changed files.
    Returns directly/transitively affected files, critical paths, and a 0-100 risk score.
    """
    result = BlastRadiusAnalyzer().analyze(req.repo_path, req.changed_files)
    return {"success": True, **result.to_dict()}


# ── Mutation Testing Runner ───────────────────────────────────────────────────

try:
    from src.agenticqa.testing.mutation_runner import MutationRunner
except ImportError:
    from agenticqa.testing.mutation_runner import MutationRunner


class MutationRequest(BaseModel):
    repo_path: str = "."
    target_files: Optional[List[str]] = None


@app.post("/api/testing/mutation")
async def mutation_test(req: MutationRequest):
    """
    Run mutation testing via mutmut and report the kill rate.
    Returns verdict: STRONG | ADEQUATE | WEAK | UNTESTED.
    Falls back to UNTESTED if mutmut is not installed.
    """
    result = MutationRunner().run(repo_path=req.repo_path, target_files=req.target_files)
    return {"success": True, **result.to_dict()}


# ── Secrets History Scanner ───────────────────────────────────────────────────

try:
    from src.agenticqa.security.secrets_scanner import SecretsHistoryScanner
except ImportError:
    from agenticqa.security.secrets_scanner import SecretsHistoryScanner


class SecretsScanRequest(BaseModel):
    repo_path: str = "."
    scan_history: bool = True
    max_commits: int = 100


@app.post("/api/security/secrets-scan")
async def secrets_scan(req: SecretsScanRequest):
    """
    Scan git commit history and current HEAD for accidentally committed secrets.
    Detects AWS keys, GitHub tokens, Stripe keys, PEM keys, passwords, and more.
    Pure Python regex — no external tools required.
    """
    result = SecretsHistoryScanner().scan(
        repo_path=req.repo_path,
        scan_history=req.scan_history,
        max_commits=req.max_commits,
    )
    return {"success": True, **result.to_dict()}


# ── Pre-flight Deploy Checklist Generator ─────────────────────────────────────

try:
    from src.agenticqa.security.preflight_checklist import PreflightChecklistGenerator
except ImportError:
    from agenticqa.security.preflight_checklist import PreflightChecklistGenerator


class PreflightChecklistRequest(BaseModel):
    changed_files: List[str] = []
    diff_content: str = ""


@app.post("/api/security/preflight-checklist")
async def preflight_checklist(req: PreflightChecklistRequest):
    """
    Generate a personalized deploy checklist based on changed files and diff content.
    Returns MUST / SHOULD / CONSIDER items grouped by category (AUTH, DATABASE, API, etc.).
    """
    result = PreflightChecklistGenerator().generate(
        changed_files=req.changed_files,
        diff_content=req.diff_content,
    )
    return {"success": True, **result.to_dict()}


# ── Container & Infrastructure Security Scanner ───────────────────────────────

try:
    from src.agenticqa.security.container_scanner import ContainerScanner
except ImportError:
    from agenticqa.security.container_scanner import ContainerScanner


@app.get("/api/security/container-scan")
async def container_scan(repo_path: str = "."):
    """
    Scan Dockerfiles, docker-compose files, and Kubernetes YAML for security issues.
    Detects: root user, privileged mode, docker.sock mounts, host networking, secrets in ENV, etc.
    Pure static analysis — no external tools.
    """
    result = ContainerScanner().scan(repo_path)
    return {"success": True, **result.to_dict()}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
