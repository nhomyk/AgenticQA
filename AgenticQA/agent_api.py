"""FastAPI integration for agent orchestration and data store access"""

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Dict, Any, Optional, List
from datetime import UTC, datetime
from pathlib import Path
import os

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

app = FastAPI(title="AgenticQA API", version="1.0.0")

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
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


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
