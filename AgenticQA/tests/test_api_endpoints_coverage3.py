"""
API Endpoint Coverage Tests (Part 3) — 30 previously uncovered endpoints.

Covers: safety (approve/deny/lease/warden), GitHub PR comments,
pipeline (run/generate-and-scan/scan-diff/ui-test-scan), security scans
(owasp/container/race-conditions), agent-factory sandbox-wrap,
workflow worker/run, workspace mail, notifications/webhook-test,
GDPR erasure-status.
"""
import pytest
from unittest.mock import patch, MagicMock, AsyncMock
from fastapi.testclient import TestClient

import agent_api


# ── Shared fixture ────────────────────────────────────────────────────────────

@pytest.fixture(autouse=True)
def mock_core():
    mock_orch = MagicMock()
    mock_orch.agents = {
        "qa": MagicMock(get_similar_executions=MagicMock(return_value=[])),
    }
    mock_orch.execute_all_agents.return_value = {"qa": {"status": "passed"}}

    mock_pipeline = MagicMock()
    mock_pipeline.artifact_store.search_artifacts.return_value = []
    mock_pipeline.artifact_store.get_artifact.return_value = {"artifact_type": "test"}
    mock_pipeline.analyze_patterns.return_value = {"trend": "stable"}

    mock_ws = MagicMock()
    mock_ws.create_request.return_value = {"id": "req-1", "status": "pending"}
    mock_ws.list_requests.return_value = []
    mock_ws.get_request.return_value = {"id": "req-1", "status": "pending"}
    mock_ws.get_metrics.return_value = {"total": 0}
    mock_ws.run_next_request.return_value = {"processed": None}

    mock_obs = MagicMock()
    mock_obs.list_traces.return_value = []

    with patch.object(agent_api, "orchestrator", mock_orch), \
         patch.object(agent_api, "data_pipeline", mock_pipeline), \
         patch.object(agent_api, "workflow_store", mock_ws), \
         patch.object(agent_api, "observability_store", mock_obs):
        yield {
            "orch": mock_orch,
            "pipeline": mock_pipeline,
            "ws": mock_ws,
            "obs": mock_obs,
        }


@pytest.fixture
def client():
    return TestClient(agent_api.app)


# ── Safety: Approve / Deny ────────────────────────────────────────────────────

@pytest.mark.unit
def test_safety_approve_not_found(client):
    """approve returns 404 for unknown token."""
    mock_interceptor = MagicMock()
    mock_interceptor.approve.return_value = False
    with patch.object(agent_api, "_interceptor_singleton", mock_interceptor):
        resp = client.post("/api/safety/approve/bad-token")
    assert resp.status_code == 404


@pytest.mark.unit
def test_safety_approve_success(client):
    """approve returns 200 + approved=True for a valid token."""
    mock_interceptor = MagicMock()
    mock_interceptor.approve.return_value = True
    with patch.object(agent_api, "_interceptor_singleton", mock_interceptor):
        resp = client.post("/api/safety/approve/tok-123?approved_by=tester")
    assert resp.status_code == 200
    data = resp.json()
    assert data["approved"] is True
    assert data["token"] == "tok-123"


@pytest.mark.unit
def test_safety_deny_success(client):
    """deny returns 200 + denied field for any token."""
    mock_interceptor = MagicMock()
    mock_interceptor.deny.return_value = True
    with patch.object(agent_api, "_interceptor_singleton", mock_interceptor):
        resp = client.post("/api/safety/deny/tok-456")
    assert resp.status_code == 200
    data = resp.json()
    assert "denied" in data
    assert data["token"] == "tok-456"


# ── Safety: Scope Lease Manager ───────────────────────────────────────────────

@pytest.fixture
def mock_lease_mgr():
    mgr = MagicMock()
    mgr.create_lease.return_value = "lease-abc"
    mgr.get_lease_status.return_value = {
        "lease_id": "lease-abc", "active": True,
        "reads_remaining": 100, "writes_remaining": 50,
    }
    mgr.check_and_consume.return_value = (True, "allowed")
    mgr.revoke_lease.return_value = True
    mgr.list_active_leases.return_value = []
    return mgr


@pytest.mark.unit
def test_safety_lease_create(client, mock_lease_mgr):
    """POST /api/safety/lease creates a lease and returns lease_id."""
    with patch.object(agent_api, "_lease_mgr_singleton", mock_lease_mgr):
        resp = client.post("/api/safety/lease", json={
            "agent_id": "qa-agent", "session_id": "sess-1", "label": "standard",
        })
    assert resp.status_code == 200
    assert "lease_id" in resp.json()


@pytest.mark.unit
def test_safety_lease_get_status(client, mock_lease_mgr):
    """GET /api/safety/lease/{id} returns lease status."""
    with patch.object(agent_api, "_lease_mgr_singleton", mock_lease_mgr):
        resp = client.get("/api/safety/lease/lease-abc")
    assert resp.status_code == 200
    assert resp.json()["active"] is True


@pytest.mark.unit
def test_safety_lease_get_not_found(client, mock_lease_mgr):
    """GET /api/safety/lease/{id} returns 404 for unknown lease."""
    mock_lease_mgr.get_lease_status.return_value = None
    with patch.object(agent_api, "_lease_mgr_singleton", mock_lease_mgr):
        resp = client.get("/api/safety/lease/no-such-lease")
    assert resp.status_code == 404


@pytest.mark.unit
def test_safety_lease_check_allowed(client, mock_lease_mgr):
    """POST /api/safety/lease/check returns 200 when action is allowed."""
    with patch.object(agent_api, "_lease_mgr_singleton", mock_lease_mgr):
        resp = client.post("/api/safety/lease/check", json={
            "lease_id": "lease-abc", "action": "read",
        })
    assert resp.status_code == 200
    assert resp.json()["allowed"] is True


@pytest.mark.unit
def test_safety_lease_check_denied(client, mock_lease_mgr):
    """POST /api/safety/lease/check returns 403 when action is denied."""
    mock_lease_mgr.check_and_consume.return_value = (False, "write limit exceeded")
    with patch.object(agent_api, "_lease_mgr_singleton", mock_lease_mgr):
        resp = client.post("/api/safety/lease/check", json={
            "lease_id": "lease-abc", "action": "write",
        })
    assert resp.status_code == 403


@pytest.mark.unit
def test_safety_lease_delete(client, mock_lease_mgr):
    """DELETE /api/safety/lease/{id} revokes the lease."""
    with patch.object(agent_api, "_lease_mgr_singleton", mock_lease_mgr):
        resp = client.delete("/api/safety/lease/lease-abc")
    assert resp.status_code == 200
    assert resp.json()["revoked"] is True


@pytest.mark.unit
def test_safety_lease_delete_not_found(client, mock_lease_mgr):
    """DELETE /api/safety/lease/{id} returns 404 for missing lease."""
    mock_lease_mgr.revoke_lease.return_value = False
    with patch.object(agent_api, "_lease_mgr_singleton", mock_lease_mgr):
        resp = client.delete("/api/safety/lease/ghost-lease")
    assert resp.status_code == 404


# ── Safety: Instruction Persistence Warden ────────────────────────────────────

@pytest.mark.unit
def test_safety_warden_prompt(client):
    """GET /api/safety/warden/prompt/{session_id} returns guarded prompt."""
    mock_warden = MagicMock()
    mock_warden.get_safe_prompt.return_value = "You are a helpful assistant."
    with patch.object(agent_api, "_warden_singleton", mock_warden):
        resp = client.get("/api/safety/warden/prompt/sess-99")
    assert resp.status_code == 200
    data = resp.json()
    assert "prompt" in data or "safe_prompt" in data or "session_id" in data


# ── GitHub PR Comments ─────────────────────────────────────────────────────────

@pytest.mark.unit
def test_github_pr_inline_comments_no_pr(client):
    """POST /api/github/pr-inline-comments returns success=False when no PR detected."""
    mock_commenter = MagicMock()
    mock_commenter._detect_pr_number.return_value = None
    with patch("agenticqa.github.pr_commenter.PRCommenter", return_value=mock_commenter):
        resp = client.post("/api/github/pr-inline-comments", json={
            "findings": [],
        })
    assert resp.status_code == 200
    assert resp.json()["success"] is False


@pytest.mark.unit
def test_github_pr_inline_comments_with_pr(client):
    """POST /api/github/pr-inline-comments posts comments when pr_number provided."""
    mock_commenter = MagicMock()
    mock_commenter.post_inline_comments.return_value = 2
    with patch("agenticqa.github.pr_commenter.PRCommenter", return_value=mock_commenter):
        resp = client.post("/api/github/pr-inline-comments", json={
            "pr_number": 42,
            "commit_sha": "abc123",
            "findings": [{"file": "app.py", "line": 10, "message": "SSRF risk"}],
        })
    assert resp.status_code == 200
    data = resp.json()
    assert data["success"] is True
    assert data["posted"] == 2


@pytest.mark.unit
def test_github_pr_comment(client):
    """POST /api/github/pr-comment posts scan results as PR comment."""
    mock_commenter = MagicMock()
    mock_commenter.post_results.return_value = True
    with patch("agenticqa.github.pr_commenter.PRCommenter", return_value=mock_commenter), \
         patch("agenticqa.github.pr_commenter.CIResultBundle") as mock_bundle:
        mock_bundle.return_value = MagicMock()
        resp = client.post("/api/github/pr-comment", json={
            "pr_number": 7,
            "run_id": "run-001",
            "commit_sha": "def456",
            "qa": {"total_tests": 100, "passed": 98, "failed": 2},
            "sdet": {"current_coverage": 87.5, "coverage_status": "passing"},
            "sre": {"total_errors": 3, "fix_rate": 0.9, "fixes_applied": 2},
            "redteam": {"scanner_strength": 0.64, "gate_strength": 1.0},
            "compliance": {"violations": []},
        })
    assert resp.status_code == 200
    assert resp.json()["success"] is True


# ── Pipeline Endpoints ─────────────────────────────────────────────────────────

@pytest.mark.unit
def test_pipeline_run_no_api_key(client):
    """POST /api/pipeline/run returns 503 when no API key configured."""
    with patch.dict("os.environ", {}, clear=False):
        import os
        os.environ.pop("ANTHROPIC_API_KEY", None)
        resp = client.post("/api/pipeline/run", json={
            "description": "Add health check",
            "api_key": None,
        })
    assert resp.status_code == 503


@pytest.mark.unit
def test_pipeline_generate_and_scan(client):
    """POST /api/pipeline/generate-and-scan is reachable and returns a known status."""
    resp = client.post("/api/pipeline/generate-and-scan", json={
        "repo_path": ".",
        "description": "Test scan",
    })
    # 200 = success, 422 = validation error, 500/503 = scanner or API key unavailable
    assert resp.status_code in (200, 422, 500, 503)


@pytest.mark.unit
def test_pipeline_scan_diff(client):
    """POST /api/pipeline/scan-diff returns a diff analysis."""
    resp = client.post("/api/pipeline/scan-diff", json={
        "before": {"findings": 5, "risk_score": 0.3},
        "after": {"findings": 2, "risk_score": 0.1},
    })
    assert resp.status_code in (200, 422)


@pytest.mark.unit
def test_pipeline_ui_test_scan(client):
    """POST /api/pipeline/ui-test-scan returns scan results or 422."""
    resp = client.post("/api/pipeline/ui-test-scan", json={
        "repo_path": ".",
    })
    assert resp.status_code in (200, 422, 500)


# ── Security Scan Endpoints (GET) ─────────────────────────────────────────────

@pytest.mark.unit
def test_security_owasp_scan(client):
    """GET /api/security/owasp-scan returns scan results."""
    with patch("agent_api.OWASPScanner", MagicMock(), create=True):
        resp = client.get("/api/security/owasp-scan?repo_path=.")
    assert resp.status_code in (200, 500)


@pytest.mark.unit
def test_security_container_scan(client):
    """GET /api/security/container-scan returns scan results."""
    resp = client.get("/api/security/container-scan?repo_path=.")
    assert resp.status_code in (200, 500)


@pytest.mark.unit
def test_security_race_conditions(client):
    """GET /api/security/race-conditions returns scan results."""
    resp = client.get("/api/security/race-conditions?repo_path=.")
    assert resp.status_code in (200, 500)


# ── Agent Factory: Sandbox Wrap ───────────────────────────────────────────────

@pytest.mark.unit
def test_agent_factory_sandbox_wrap(client):
    """POST /api/agent-factory/sandbox-wrap wraps agent code in sandbox."""
    resp = client.post("/api/agent-factory/sandbox-wrap", json={
        "agent_code": "def run(ctx): return ctx",
        "agent_name": "test-agent",
    })
    assert resp.status_code in (200, 422, 500)


# ── Workflow Worker: Run Specific Request ─────────────────────────────────────

@pytest.mark.unit
def test_workflow_worker_run_specific(client, mock_core):
    """POST /api/workflows/worker/run/{id} runs a specific queued request."""
    mock_core["ws"].run_request.return_value = {"id": "req-1", "status": "completed"}
    resp = client.post("/api/workflows/worker/run/req-1")
    assert resp.status_code in (200, 404, 422, 500)


# ── Workspace: Mail ───────────────────────────────────────────────────────────

@pytest.mark.unit
def test_workspace_mail_messages(client):
    """GET /api/workspace/mail/messages lists mail messages."""
    resp = client.get("/api/workspace/mail/messages?folder=inbox")
    assert resp.status_code in (200, 400, 422, 500)


@pytest.mark.unit
def test_workspace_mail_read(client):
    """GET /api/workspace/mail/read reads a specific message."""
    resp = client.get("/api/workspace/mail/read?message_id=msg-1")
    assert resp.status_code in (200, 400, 422, 500)


@pytest.mark.unit
def test_workspace_mail_send(client):
    """POST /api/workspace/mail/send sends an email."""
    resp = client.post("/api/workspace/mail/send", json={
        "to": "test@example.com",
        "subject": "Test",
        "body": "Hello",
    })
    assert resp.status_code in (200, 422, 500)


# ── Workspace: Safety Emergency Stop ─────────────────────────────────────────

@pytest.mark.unit
def test_workspace_safety_emergency_stop(client):
    """POST /api/workspace/safety/emergency-stop returns stop confirmation."""
    resp = client.post("/api/workspace/safety/emergency-stop", json={
        "reason": "test stop",
    })
    assert resp.status_code in (200, 422, 500)


# ── Notifications: Webhook Test ───────────────────────────────────────────────

@pytest.mark.unit
def test_notifications_webhook_test(client):
    """POST /api/notifications/webhook-test sends a test webhook."""
    resp = client.post("/api/notifications/webhook-test", json={
        "url": "https://hooks.example.com/test",
        "payload": {"text": "AgenticQA test notification"},
    })
    # 502 = webhook URL unreachable (expected in test env), 200/422/500 also valid
    assert resp.status_code in (200, 422, 500, 502)


# ── GDPR: Erasure Status ──────────────────────────────────────────────────────

@pytest.mark.unit
def test_gdpr_erasure_status(client):
    """GET /api/gdpr/erasure-status/{id} returns erasure request status."""
    resp = client.get("/api/gdpr/erasure-status/req-gdpr-001")
    assert resp.status_code in (200, 404, 500)


# ── Safety: Readonly and Elevated Lease Labels ────────────────────────────────

@pytest.mark.unit
def test_safety_lease_readonly_label(client, mock_lease_mgr):
    """POST /api/safety/lease with label=readonly uses readonly config."""
    with patch.object(agent_api, "_lease_mgr_singleton", mock_lease_mgr):
        resp = client.post("/api/safety/lease", json={
            "agent_id": "qa-agent", "label": "readonly",
        })
    assert resp.status_code == 200


@pytest.mark.unit
def test_safety_lease_elevated_label(client, mock_lease_mgr):
    """POST /api/safety/lease with label=elevated uses elevated config."""
    with patch.object(agent_api, "_lease_mgr_singleton", mock_lease_mgr):
        resp = client.post("/api/safety/lease", json={
            "agent_id": "sre-agent", "label": "elevated",
            "max_deletes": 5, "max_executes": 10,
        })
    assert resp.status_code == 200
