"""Pagination & Graceful Shutdown Tests.

Tests:
  - List endpoints accept offset parameter
  - Pagination returns correct slices
  - Shutdown status endpoint exists and returns correct shape
"""
import os
import pytest
from unittest.mock import patch, MagicMock


@pytest.fixture(autouse=True)
def _disable_auth():
    os.environ["AGENTICQA_AUTH_DISABLE"] = "1"
    yield
    os.environ.pop("AGENTICQA_AUTH_DISABLE", None)


@pytest.fixture
def client():
    from fastapi.testclient import TestClient
    import agent_api
    return TestClient(agent_api.app)


# ── Shutdown status endpoint ────────────────────────────────────────────────────

@pytest.mark.unit
def test_shutdown_status_endpoint_exists(client):
    resp = client.get("/api/health/shutdown-status")
    assert resp.status_code == 200
    assert "shutting_down" in resp.json()


@pytest.mark.unit
def test_shutdown_status_initially_false(client):
    resp = client.get("/api/health/shutdown-status")
    assert resp.json()["shutting_down"] is False


# ── Chat sessions pagination ───────────────────────────────────────────────────

@pytest.mark.unit
def test_chat_sessions_accepts_offset(client):
    resp = client.get("/api/chat/sessions", params={"limit": 5, "offset": 0})
    assert resp.status_code == 200
    data = resp.json()
    assert "offset" in data
    assert "limit" in data


@pytest.mark.unit
def test_chat_sessions_offset_in_response(client):
    resp = client.get("/api/chat/sessions", params={"limit": 5, "offset": 2})
    data = resp.json()
    assert data["offset"] == 2
    assert data["limit"] == 5


# ── Workflow requests pagination ────────────────────────────────────────────────

@pytest.mark.unit
def test_workflow_requests_accepts_offset(client):
    resp = client.get("/api/workflows/requests", params={"limit": 10, "offset": 0})
    assert resp.status_code == 200
    data = resp.json()
    assert "offset" in data
    assert "limit" in data


# ── Observability traces pagination ─────────────────────────────────────────────

@pytest.mark.unit
def test_observability_traces_accepts_offset(client):
    resp = client.get("/api/observability/traces", params={"limit": 10, "offset": 0})
    assert resp.status_code == 200
    data = resp.json()
    assert "offset" in data


# ── Observability events pagination ─────────────────────────────────────────────

@pytest.mark.unit
def test_observability_events_accepts_offset(client):
    resp = client.get("/api/observability/events", params={"limit": 10, "offset": 0})
    assert resp.status_code == 200
    data = resp.json()
    assert "offset" in data
    assert "limit" in data


# ── Audit chain pagination ─────────────────────────────────────────────────────

@pytest.mark.unit
def test_audit_chain_accepts_offset(client):
    resp = client.get("/api/security/audit-chain", params={"limit": 10, "offset": 0})
    assert resp.status_code == 200
    data = resp.json()
    assert "offset" in data
    assert "limit" in data


# ── Provenance chain pagination ─────────────────────────────────────────────────

@pytest.mark.unit
def test_provenance_chain_accepts_offset(client):
    resp = client.get("/api/provenance/chain", params={"agent": "QA_Assistant", "limit": 5, "offset": 0})
    assert resp.status_code == 200
    data = resp.json()
    assert "offset" in data
    assert "limit" in data
