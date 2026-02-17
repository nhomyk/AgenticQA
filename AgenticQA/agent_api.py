"""FastAPI integration for agent orchestration and data store access"""

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Dict, Any, Optional, List
from datetime import UTC, datetime

from src.agents import AgentOrchestrator
from src.data_store import SecureDataPipeline
try:
    from src.agenticqa.workflow_requests import PromptWorkflowStore
except Exception:
    from agenticqa.workflow_requests import PromptWorkflowStore

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


@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "timestamp": datetime.now(UTC).isoformat(),
        "agents_ready": 4,
    }


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


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
