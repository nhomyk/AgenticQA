"""
API Endpoint Coverage Tests — Verify all claimed endpoints return valid responses.

Tests the HTTP layer (serialization, status codes, error handling) for endpoints
that previously only had unit tests on the underlying modules. Uses FastAPI
TestClient — no live server or external services needed.
"""
import pytest
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient

import agent_api


@pytest.fixture(autouse=True)
def mock_core():
    """Patch module-level dependencies for all tests."""
    mock_orch = MagicMock()
    mock_orch.agents = {"qa": MagicMock(), "sre": MagicMock()}
    mock_orch.execute_all_agents.return_value = {"qa": {"status": "passed"}}

    mock_pipeline = MagicMock()
    mock_pipeline.artifact_store.search_artifacts.return_value = []
    mock_pipeline.artifact_store.get_artifact.return_value = {"data": "test"}
    mock_pipeline.analyze_patterns.return_value = {"trend": "stable"}

    with patch.object(agent_api, "orchestrator", mock_orch), \
         patch.object(agent_api, "data_pipeline", mock_pipeline):
        yield


@pytest.fixture
def client():
    return TestClient(agent_api.app)


# ── Health & System ──────────────────────────────────────────────────────────

@pytest.mark.unit
def test_health_dataflow(client):
    with patch("agenticqa.monitoring.dataflow_health.DataflowHealthMonitor") as Mock:
        mock = Mock.return_value
        mock.check_all.return_value = MagicMock(
            healthy=True, broken_nodes=[], degraded_nodes=[],
            to_dict=lambda: {"healthy": True, "broken_nodes": [], "degraded_nodes": []},
        )
        resp = client.get("/api/health/dataflow")
    assert resp.status_code == 200
    assert resp.json()["healthy"] is True


# ── Security Scanners ────────────────────────────────────────────────────────

@pytest.mark.unit
def test_architecture_scan(client, tmp_path):
    (tmp_path / "clean.py").write_text("x = 1\n")
    resp = client.get("/api/security/architecture-scan", params={"repo_path": str(tmp_path)})
    assert resp.status_code == 200
    data = resp.json()
    assert data["success"] is True
    assert "attack_surface_score" in data
    assert "integration_areas" in data


@pytest.mark.unit
def test_cve_reachability(client, tmp_path):
    (tmp_path / "app.py").write_text("import requests\n")
    resp = client.get("/api/security/cve-reachability", params={"repo_path": str(tmp_path)})
    assert resp.status_code == 200
    data = resp.json()
    assert "findings" in data or "total_findings" in data or "success" in data


@pytest.mark.unit
def test_legal_risk(client, tmp_path):
    (tmp_path / "app.py").write_text("x = 1\n")
    resp = client.get("/api/compliance/legal-risk", params={"repo_path": str(tmp_path)})
    assert resp.status_code == 200


@pytest.mark.unit
def test_hipaa(client, tmp_path):
    (tmp_path / "app.py").write_text("x = 1\n")
    resp = client.get("/api/compliance/hipaa", params={"repo_path": str(tmp_path)})
    assert resp.status_code == 200


@pytest.mark.unit
def test_ai_act(client, tmp_path):
    (tmp_path / "app.py").write_text("x = 1\n")
    resp = client.get("/api/compliance/ai-act", params={"repo_path": str(tmp_path)})
    assert resp.status_code == 200


@pytest.mark.unit
def test_ai_model_sbom(client, tmp_path):
    (tmp_path / "app.py").write_text("x = 1\n")
    resp = client.get("/api/compliance/ai-model-sbom", params={"repo_path": str(tmp_path)})
    assert resp.status_code == 200


@pytest.mark.unit
def test_prompt_injection(client, tmp_path):
    (tmp_path / "app.py").write_text("x = 1\n")
    resp = client.get("/api/redteam/prompt-injection", params={"repo_path": str(tmp_path)})
    assert resp.status_code == 200


@pytest.mark.unit
def test_agent_trust_graph(client, tmp_path):
    (tmp_path / "app.py").write_text("x = 1\n")
    resp = client.get("/api/redteam/agent-trust-graph", params={"repo_path": str(tmp_path)})
    assert resp.status_code == 200


@pytest.mark.unit
def test_mcp_scan(client, tmp_path):
    (tmp_path / "server.ts").write_text("const x = 1;\n")
    resp = client.get("/api/security/mcp-scan", params={"repo_path": str(tmp_path)})
    assert resp.status_code == 200


@pytest.mark.unit
def test_owasp_scan(client, tmp_path):
    (tmp_path / "app.py").write_text("x = 1\n")
    resp = client.get("/api/security/owasp-scan", params={"repo_path": str(tmp_path)})
    assert resp.status_code == 200


@pytest.mark.unit
def test_ci_scan(client, tmp_path):
    (tmp_path / ".github" / "workflows").mkdir(parents=True)
    (tmp_path / ".github" / "workflows" / "ci.yml").write_text("name: CI\non: push\njobs: {}\n")
    resp = client.get("/api/security/ci-scan", params={"repo_path": str(tmp_path)})
    assert resp.status_code == 200


@pytest.mark.unit
def test_container_scan(client, tmp_path):
    (tmp_path / "Dockerfile").write_text("FROM python:3.11\nRUN pip install flask\n")
    resp = client.get("/api/security/container-scan", params={"repo_path": str(tmp_path)})
    assert resp.status_code == 200


@pytest.mark.unit
def test_secrets_scan(client, tmp_path):
    (tmp_path / "app.py").write_text("x = 1\n")
    resp = client.post("/api/security/secrets-scan", json={"repo_path": str(tmp_path)})
    assert resp.status_code == 200


@pytest.mark.unit
def test_race_conditions(client, tmp_path):
    (tmp_path / "app.py").write_text("x = 1\n")
    resp = client.get("/api/security/race-conditions", params={"repo_path": str(tmp_path)})
    assert resp.status_code == 200


@pytest.mark.unit
def test_data_flow_trace(client, tmp_path):
    (tmp_path / "app.py").write_text("x = 1\n")
    resp = client.get("/api/security/data-flow-trace", params={"repo_path": str(tmp_path)})
    assert resp.status_code == 200


# ── Provenance & Regression ──────────────────────────────────────────────────

@pytest.mark.unit
def test_provenance_verify(client):
    resp = client.get("/api/provenance/verify", params={
        "output_hash": "abc123", "agent": "sre_agent",
    })
    assert resp.status_code == 200
    data = resp.json()
    assert "valid" in data or "reason" in data


@pytest.mark.unit
def test_provenance_chain(client):
    resp = client.get("/api/provenance/chain", params={
        "agent": "sre_agent", "limit": "5",
    })
    assert resp.status_code == 200


@pytest.mark.unit
def test_regression_compare(client):
    resp = client.get("/api/regression/compare", params={
        "agent": "sre_agent",
        "baseline_model": "claude-sonnet-4-6",
        "candidate_model": "claude-haiku-4-5",
    })
    assert resp.status_code == 200


# ── Learning & Profiles ──────────────────────────────────────────────────────

@pytest.mark.unit
def test_developer_profiles(client):
    resp = client.get("/api/developer-profiles")
    assert resp.status_code == 200


@pytest.mark.unit
def test_org_memory(client):
    resp = client.get("/api/org-memory")
    assert resp.status_code == 200


@pytest.mark.unit
def test_learning_metrics(client):
    resp = client.get("/api/learning-metrics")
    assert resp.status_code == 200


@pytest.mark.unit
def test_repo_profile(client):
    resp = client.get("/api/repo-profile")
    assert resp.status_code == 200


@pytest.mark.unit
def test_temporal_violations(client):
    resp = client.get("/api/temporal/violations", params={"repo_id": "test-repo"})
    assert resp.status_code == 200


# ── Safety Module ────────────────────────────────────────────────────────────

@pytest.mark.unit
def test_safety_intercept(client):
    resp = client.post("/api/safety/intercept", json={
        "agent_name": "sre_agent",
        "tool_name": "subprocess.run",
        "arguments": {"cmd": "ls"},
    })
    assert resp.status_code == 200
    data = resp.json()
    assert "classification" in data or "verdict" in data or "action" in data


@pytest.mark.unit
def test_safety_pending(client):
    resp = client.get("/api/safety/pending")
    assert resp.status_code == 200


@pytest.mark.unit
def test_safety_lease_create(client):
    resp = client.post("/api/safety/lease", json={
        "agent_id": "sre_agent",
        "session_id": "test-session",
        "label": "standard",
        "max_reads": 100,
        "max_writes": 10,
        "max_deletes": 0,
        "max_executes": 5,
        "lease_ttl_seconds": 300,
    })
    assert resp.status_code == 200
    data = resp.json()
    assert "lease_id" in data or "id" in data or "success" in data


@pytest.mark.unit
def test_safety_leases_list(client):
    resp = client.get("/api/safety/leases")
    assert resp.status_code == 200


@pytest.mark.unit
def test_safety_warden_register(client):
    resp = client.post("/api/safety/warden/register", json={
        "session_id": "test-session",
        "guardrails": [
            {"name": "no_destructive_ops", "content": "Never run destructive commands"},
            {"name": "require_ci_pass", "content": "CI must pass before deploy"},
        ],
    })
    assert resp.status_code == 200


@pytest.mark.unit
def test_safety_warden_check(client):
    resp = client.post("/api/safety/warden/check", json={
        "session_id": "test-session",
        "compaction_pct": 0.5,
    })
    assert resp.status_code == 200


# ── Scoring ──────────────────────────────────────────────────────────────────

@pytest.mark.unit
def test_pr_risk_score(client):
    resp = client.post("/api/scoring/pr-risk", json={
        "author_email": "dev@example.com",
        "changed_files": ["src/auth/login.py"],
        "diff_lines": "+password = 'hunter2'\n",
    })
    assert resp.status_code == 200
    data = resp.json()
    assert "risk_score" in data
    assert "recommendation" in data


# ── Red Team ─────────────────────────────────────────────────────────────────

@pytest.mark.unit
def test_red_team_scan(client):
    resp = client.post("/api/red-team/scan", json={
        "mode": "fast",
        "target": "both",
        "auto_patch": False,
    })
    assert resp.status_code == 200
    data = resp.json()
    assert "bypass_attempts" in data or "scanner_strength" in data


# ── Compliance Drift & Risk Gate ─────────────────────────────────────────────

@pytest.mark.unit
def test_compliance_drift(client):
    resp = client.get("/api/compliance/drift")
    assert resp.status_code == 200


@pytest.mark.unit
def test_risk_gate(client):
    resp = client.get("/api/risk-gate")
    assert resp.status_code == 200


# ── SARIF Export ─────────────────────────────────────────────────────────────

@pytest.mark.unit
def test_sarif_export(client):
    resp = client.post("/api/export/sarif", json={
        "sre_results": {"total_errors": 5, "fixes_applied": 3, "fixes": []},
    })
    assert resp.status_code == 200
    data = resp.json()
    assert "sarif" in data or "$schema" in data or "runs" in data


# ── Pipeline / Demo ──────────────────────────────────────────────────────────

@pytest.mark.unit
def test_demo_submit(client, tmp_path):
    (tmp_path / "api").mkdir()
    (tmp_path / "api" / "main.py").write_text("items = {}\n")
    resp = client.post("/api/demo/submit", json={
        "description": "Add a health check endpoint",
        "repo_path": str(tmp_path),
    })
    # May succeed or fail depending on demo setup, but should not 500
    assert resp.status_code in (200, 422, 400)


# ── Onboarding ───────────────────────────────────────────────────────────────

@pytest.mark.unit
def test_onboarding_status(client):
    resp = client.get("/api/onboarding/status")
    assert resp.status_code == 200


# ── GDPR ─────────────────────────────────────────────────────────────────────

@pytest.mark.unit
def test_gdpr_erasure_request(client):
    resp = client.post("/api/gdpr/erasure-request", json={
        "tenant_id": "test-tenant-123",
        "subject_id": "test-user-456",
    })
    assert resp.status_code == 200


# ── Blast Radius ─────────────────────────────────────────────────────────────

@pytest.mark.unit
def test_blast_radius(client, tmp_path):
    (tmp_path / "app.py").write_text("import os\n")
    resp = client.post("/api/security/blast-radius", json={
        "repo_path": str(tmp_path),
        "changed_files": ["app.py"],
    })
    assert resp.status_code == 200


# ── Preflight Checklist ──────────────────────────────────────────────────────

@pytest.mark.unit
def test_preflight_checklist(client):
    resp = client.post("/api/security/preflight-checklist", json={
        "repo_path": ".",
        "target_env": "production",
    })
    assert resp.status_code == 200


# ── Intent Verify ────────────────────────────────────────────────────────────

@pytest.mark.unit
def test_intent_verify(client):
    resp = client.post("/api/security/intent-verify", json={
        "intent": "Add a greeting function",
        "code_diff": "+def hello():\n+    return 'hi'\n",
        "file_path": "app.py",
    })
    assert resp.status_code == 200


# ── Skill Scan ───────────────────────────────────────────────────────────────

@pytest.mark.unit
def test_skill_scan(client, tmp_path):
    (tmp_path / "app.py").write_text("x = 1\n")
    resp = client.get("/api/security/skill-scan", params={"repo_path": str(tmp_path)})
    assert resp.status_code == 200


# ── Audit Chain ──────────────────────────────────────────────────────────────

@pytest.mark.unit
def test_audit_chain(client):
    resp = client.get("/api/security/audit-chain")
    assert resp.status_code == 200


# ── Classify Intent ──────────────────────────────────────────────────────────

@pytest.mark.unit
def test_classify_intent(client):
    resp = client.post("/api/security/classify-intent", json={
        "text": "delete all user data from production",
    })
    assert resp.status_code == 200


# ── Release Readiness ────────────────────────────────────────────────────────

@pytest.mark.unit
def test_release_readiness(client):
    resp = client.post("/api/release-readiness", json={
        "repo_path": ".",
    })
    assert resp.status_code == 200
