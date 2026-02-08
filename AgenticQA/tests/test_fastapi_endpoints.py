"""
FastAPI Endpoint Tests

Dedicated tests for all API endpoints in agent_api.py.
Uses FastAPI TestClient with patched orchestrator and data pipeline.
"""

import pytest
from unittest.mock import patch, MagicMock, PropertyMock
from fastapi.testclient import TestClient

import agent_api


@pytest.fixture(autouse=True)
def mock_dependencies():
    """Patch module-level orchestrator and data_pipeline for every test."""
    mock_orch = MagicMock()
    mock_orch.agents = {
        "qa": MagicMock(),
        "performance": MagicMock(),
        "compliance": MagicMock(),
        "devops": MagicMock(),
    }
    mock_orch.execute_all_agents.return_value = {
        "qa": {"status": "passed"},
        "performance": {"status": "passed"},
    }
    mock_orch.get_agent_insights.return_value = {
        "qa": {"patterns": ["flaky_test"]},
    }

    mock_pipeline = MagicMock()
    mock_pipeline.artifact_store.search_artifacts.return_value = [
        {"artifact_type": "test_result", "source": "qa", "timestamp": "2025-01-01T00:00:00Z"}
    ]
    mock_pipeline.artifact_store.get_artifact.return_value = {"data": "test"}
    mock_pipeline.artifact_store.verify_artifact_integrity.return_value = True
    mock_pipeline.analyze_patterns.return_value = {"trend": "improving"}

    with patch.object(agent_api, "orchestrator", mock_orch), \
         patch.object(agent_api, "data_pipeline", mock_pipeline):
        yield mock_orch, mock_pipeline


@pytest.fixture
def client():
    """Create a test client."""
    return TestClient(agent_api.app)


class TestHealthEndpoint:
    """Tests for GET /health"""

    def test_health_returns_200(self, client):
        response = client.get("/health")
        assert response.status_code == 200

    def test_health_response_structure(self, client):
        data = client.get("/health").json()
        assert data["status"] == "healthy"
        assert "timestamp" in data
        assert data["agents_ready"] == 4


class TestExecuteEndpoint:
    """Tests for POST /api/agents/execute"""

    def test_execute_with_full_payload(self, client):
        payload = {
            "test_results": {"total": 10, "passed": 9},
            "execution_data": {"duration": 120},
            "compliance_data": {"violations": 0},
            "deployment_config": {"target": "staging"},
        }
        response = client.post("/api/agents/execute", json=payload)
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "results" in data
        assert "timestamp" in data

    def test_execute_with_empty_payload(self, client):
        response = client.post("/api/agents/execute", json={})
        assert response.status_code == 200
        assert response.json()["success"] is True

    def test_execute_with_partial_payload(self, client):
        response = client.post("/api/agents/execute", json={"test_results": {"total": 5}})
        assert response.status_code == 200

    def test_execute_orchestrator_error_returns_500(self, client, mock_dependencies):
        mock_orch, _ = mock_dependencies
        mock_orch.execute_all_agents.side_effect = RuntimeError("agent crash")
        response = client.post("/api/agents/execute", json={})
        assert response.status_code == 500
        assert "agent crash" in response.json()["detail"]


class TestInsightsEndpoint:
    """Tests for GET /api/agents/insights"""

    def test_insights_returns_200(self, client):
        response = client.get("/api/agents/insights")
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "insights" in data

    def test_insights_error_returns_500(self, client, mock_dependencies):
        mock_orch, _ = mock_dependencies
        mock_orch.get_agent_insights.side_effect = RuntimeError("fail")
        response = client.get("/api/agents/insights")
        assert response.status_code == 500


class TestAgentHistoryEndpoint:
    """Tests for GET /api/agents/{agent_name}/history"""

    def test_history_known_agent(self, client, mock_dependencies):
        mock_orch, _ = mock_dependencies
        mock_orch.agents["qa"].get_similar_executions.return_value = [
            {"id": 1, "status": "passed"}
        ]
        response = client.get("/api/agents/qa/history")
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["agent"] == "qa"
        assert len(data["history"]) == 1

    def test_history_with_limit(self, client, mock_dependencies):
        mock_orch, _ = mock_dependencies
        mock_orch.agents["qa"].get_similar_executions.return_value = []
        response = client.get("/api/agents/qa/history?limit=5")
        assert response.status_code == 200
        mock_orch.agents["qa"].get_similar_executions.assert_called_with(limit=5)

    def test_history_unknown_agent_returns_500(self, client):
        response = client.get("/api/agents/nonexistent/history")
        assert response.status_code == 500


class TestDatastoreSearchEndpoint:
    """Tests for POST /api/datastore/search"""

    def test_search_all_artifacts(self, client):
        response = client.post("/api/datastore/search", json={})
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["count"] == 1

    def test_search_with_filters(self, client):
        response = client.post("/api/datastore/search", json={
            "artifact_type": "test_result",
            "source": "qa",
            "tags": ["regression"],
        })
        assert response.status_code == 200

    def test_search_error_returns_500(self, client, mock_dependencies):
        _, mock_pipeline = mock_dependencies
        mock_pipeline.artifact_store.search_artifacts.side_effect = RuntimeError("db error")
        response = client.post("/api/datastore/search", json={})
        assert response.status_code == 500


class TestArtifactEndpoint:
    """Tests for GET /api/datastore/artifact/{artifact_id}"""

    def test_get_artifact_success(self, client):
        response = client.get("/api/datastore/artifact/abc123")
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["artifact_id"] == "abc123"
        assert data["integrity_verified"] is True

    def test_get_artifact_not_found(self, client, mock_dependencies):
        _, mock_pipeline = mock_dependencies
        mock_pipeline.artifact_store.get_artifact.side_effect = FileNotFoundError()
        response = client.get("/api/datastore/artifact/missing")
        assert response.status_code == 404


class TestDatastoreStatsEndpoint:
    """Tests for GET /api/datastore/stats"""

    def test_stats_returns_200(self, client):
        response = client.get("/api/datastore/stats")
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["total_artifacts"] == 1
        assert "by_type" in data
        assert "by_source" in data

    def test_stats_empty_store(self, client, mock_dependencies):
        _, mock_pipeline = mock_dependencies
        mock_pipeline.artifact_store.search_artifacts.return_value = []
        response = client.get("/api/datastore/stats")
        assert response.status_code == 200
        data = response.json()
        assert data["total_artifacts"] == 0
        assert data["last_updated"] is None


class TestPatternsEndpoint:
    """Tests for GET /api/datastore/patterns"""

    def test_patterns_returns_200(self, client):
        response = client.get("/api/datastore/patterns")
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "patterns" in data
        assert "timestamp" in data
