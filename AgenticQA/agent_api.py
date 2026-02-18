"""FastAPI integration for agent orchestration and data store access"""

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Dict, Any, Optional, List
from datetime import UTC, datetime
from pathlib import Path

from src.agents import AgentOrchestrator
from src.data_store import SecureDataPipeline
try:
    from src.agenticqa.workflow_requests import PromptWorkflowStore
    from src.agenticqa.workflow_worker import WorkflowExecutionWorker
    from src.agenticqa.observability import ObservabilityStore
    from src.agenticqa.reliability_evidence import build_evidence_summary, check_tcp, read_latest_jsonl
except Exception:
    from agenticqa.workflow_requests import PromptWorkflowStore
    from agenticqa.workflow_worker import WorkflowExecutionWorker
    from agenticqa.observability import ObservabilityStore
    from agenticqa.reliability_evidence import build_evidence_summary, check_tcp, read_latest_jsonl

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


class ObservabilityEventsQuery(BaseModel):
    """Optional filters for observability event queries."""

    trace_id: Optional[str] = None
    request_id: Optional[str] = None
    agent: Optional[str] = None
    action: Optional[str] = None
    limit: int = 100


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
        checks = {
            "workflow_db_writable": home.exists() or home.parent.exists(),
            "observability_db_writable": home.exists() or home.parent.exists(),
            "neo4j_tcp": check_tcp("127.0.0.1", 7687),
            "weaviate_tcp": check_tcp("127.0.0.1", 8080),
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
