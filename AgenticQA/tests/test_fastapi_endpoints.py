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


class TestObservabilityEndpoints:
    """Tests for observability trace/quality APIs."""

    def test_observability_quality_returns_summary(self, client):
        mock_obs = MagicMock()
        mock_obs.get_quality_summary.return_value = {
            "trace_count": 2,
            "avg_completeness_ratio": 0.98,
            "min_completeness_ratio": 0.95,
            "below_threshold_count": 0,
            "status": "pass",
        }
        with patch.object(agent_api, "observability_store", mock_obs):
            response = client.get("/api/observability/quality")
            assert response.status_code == 200
            data = response.json()
            assert data["success"] is True
            assert data["quality"]["trace_count"] == 2

    def test_observability_trace_analysis_returns_payload(self, client):
        mock_obs = MagicMock()
        mock_obs.list_events.return_value = [{"trace_id": "tr_x", "status": "STARTED"}]
        mock_obs.analyze_trace.return_value = {
            "trace_id": "tr_x",
            "span_count": 1,
            "completeness_ratio": 0.0,
            "critical_path_ms": 0.0,
        }
        with patch.object(agent_api, "observability_store", mock_obs):
            response = client.get("/api/observability/traces/tr_x/analysis")
            assert response.status_code == 200
            data = response.json()
            assert data["success"] is True
            assert data["trace_id"] == "tr_x"
            assert data["analysis"]["span_count"] == 1

    def test_observability_counterfactuals_returns_payload(self, client):
        mock_obs = MagicMock()
        mock_obs.get_counterfactual_recommendations.return_value = {
            "trace_id": "tr_cf",
            "event_count": 2,
            "recommendations": [
                {
                    "agent": "SDET_Agent",
                    "action": "sdet_test_loop",
                    "status": "FAILED",
                    "root_cause": "PYTEST_FAILURE",
                    "counterfactuals": ["Increase max iterations"],
                }
            ],
        }
        with patch.object(agent_api, "observability_store", mock_obs):
            response = client.get("/api/observability/traces/tr_cf/counterfactuals")
            assert response.status_code == 200
            data = response.json()
            assert data["success"] is True
            assert data["counterfactuals"]["trace_id"] == "tr_cf"

    def test_observability_insights_returns_payload(self, client):
        mock_obs = MagicMock()
        mock_obs.get_global_insights.return_value = {
            "quality": {"trace_count": 3},
            "failures": {"failed_events": 1, "failure_rate": 0.1},
            "policy_impact": {"policy_blocked_runs": 0, "policy_block_rate": 0.0},
        }
        with patch.object(agent_api, "observability_store", mock_obs):
            response = client.get("/api/observability/insights")
            assert response.status_code == 200
            data = response.json()
            assert data["success"] is True
            assert data["insights"]["quality"]["trace_count"] == 3

    def test_audit_report_returns_structured_payload(self, client):
        mock_obs = MagicMock()
        mock_obs.list_events.return_value = [
            {"id": 1, "status": "COMPLETED", "agent": "qa", "action": "run_checks",
             "decision": {"result": "ok"}, "span_id": "s1", "parent_span_id": None,
             "latency_ms": 120, "event_type": "action", "error": None, "metadata": {}},
        ]
        mock_obs.analyze_trace.return_value = {
            "trace_id": "tr_audit",
            "span_count": 1,
            "root_spans": ["s1"],
            "started_span_count": 1,
            "terminal_span_count": 1,
            "completeness_ratio": 1.0,
            "orphan_span_count": 0,
            "critical_path_ms": 120.0,
            "by_agent_action": [{"agent": "qa", "action": "run_checks", "count": 1, "failures": 0, "avg_latency_ms": 120.0}],
            "event_type_counts": {"action": 1},
            "spans": [],
        }
        mock_obs.get_counterfactual_recommendations.return_value = {
            "trace_id": "tr_audit", "event_count": 1, "recommendations": []
        }
        with patch.object(agent_api, "observability_store", mock_obs), \
             patch.object(agent_api, "build_audit_report", wraps=agent_api.build_audit_report):
            response = client.get("/api/observability/traces/tr_audit/audit-report")
            assert response.status_code == 200
            data = response.json()
            assert data["success"] is True
            assert data["trace_id"] == "tr_audit"
            report = data["report"]
            assert "audit_id" in report
            assert "verdict" in report
            assert "decision_quality" in report
            assert "recommendations" in report
            assert "markdown_body" in report

    def test_audit_report_markdown_format(self, client):
        mock_obs = MagicMock()
        mock_obs.list_events.return_value = [
            {"id": 2, "status": "FAILED", "agent": "sdet", "action": "sdet_test_loop",
             "decision": {}, "span_id": "s2", "parent_span_id": None,
             "latency_ms": 50, "event_type": "action",
             "error": "sdet_loop_failed: assertion error", "metadata": {}},
        ]
        mock_obs.analyze_trace.return_value = {
            "trace_id": "tr_md", "span_count": 1, "root_spans": ["s2"],
            "started_span_count": 1, "terminal_span_count": 1,
            "completeness_ratio": 1.0, "orphan_span_count": 0,
            "critical_path_ms": 50.0,
            "by_agent_action": [{"agent": "sdet", "action": "sdet_test_loop", "count": 1, "failures": 1, "avg_latency_ms": 50.0}],
            "event_type_counts": {"action": 1}, "spans": [],
        }
        mock_obs.get_counterfactual_recommendations.return_value = {
            "trace_id": "tr_md", "event_count": 1,
            "recommendations": [{"event_id": 2, "agent": "sdet", "action": "sdet_test_loop",
                                  "event_type": "action", "status": "FAILED",
                                  "root_cause": "PYTEST_FAILURE", "error": "sdet_loop_failed",
                                  "counterfactuals": ["Increase max_sdet_iterations by 1"]}],
        }
        with patch.object(agent_api, "observability_store", mock_obs):
            response = client.get("/api/observability/traces/tr_md/audit-report?format=markdown")
            assert response.status_code == 200
            data = response.json()
            assert data["success"] is True
            assert "markdown_body" in data
            assert "AgenticQA Decision Audit" in data["markdown_body"]

    def test_audit_report_unknown_trace_returns_404(self, client):
        mock_obs = MagicMock()
        mock_obs.list_events.return_value = []
        with patch.object(agent_api, "observability_store", mock_obs):
            response = client.get("/api/observability/traces/no_such_trace/audit-report")
            assert response.status_code == 404
            assert "no_such_trace" in response.json()["detail"]

    def test_agent_complexity_returns_trends_for_named_agent(self, client):
        mock_obs = MagicMock()
        mock_obs.get_complexity_trends.return_value = {
            "agent": "QA_Assistant",
            "window_days": 14,
            "daily": [{"date": "2026-02-18", "avg_rag_docs": 4.0, "avg_similarity": 0.78, "avg_patterns": 2.0, "actions": 3}],
            "summary": {"total_actions": 3, "avg_rag_docs": 4.0, "avg_similarity": 0.78},
            "anomaly": False,
            "anomaly_reason": None,
        }
        with patch.object(agent_api, "observability_store", mock_obs):
            response = client.get("/api/observability/agent-complexity?agent=QA_Assistant")
            assert response.status_code == 200
            data = response.json()
            assert data["success"] is True
            assert data["complexity"]["agent"] == "QA_Assistant"
            assert data["complexity"]["anomaly"] is False

    def test_agent_complexity_returns_all_agents_when_no_filter(self, client):
        mock_obs = MagicMock()
        mock_obs.conn.cursor.return_value.execute.return_value.fetchall.return_value = [("QA_Assistant",)]
        mock_obs.get_complexity_trends.return_value = {
            "agent": "QA_Assistant", "window_days": 14, "daily": [],
            "summary": {"total_actions": 0, "avg_rag_docs": 0.0, "avg_similarity": 0.0},
            "anomaly": False, "anomaly_reason": None,
        }
        with patch.object(agent_api, "observability_store", mock_obs):
            response = client.get("/api/observability/agent-complexity")
            assert response.status_code == 200
            data = response.json()
            assert data["success"] is True
            assert "agents" in data
            assert "anomalies" in data


class TestPortabilityScorecardEndpoints:
    """Tests for portability scorecard APIs."""

    def test_get_portability_scorecard_returns_payload(self, client):
        with patch.object(agent_api, "detect_repo_profile") as mock_profile, \
             patch.object(agent_api.workflow_store, "get_metrics") as mock_metrics, \
             patch.object(agent_api.observability_store, "get_global_insights") as mock_insights, \
             patch.object(agent_api, "load_baseline") as mock_load_baseline, \
             patch.object(agent_api, "build_portability_scorecard") as mock_build:
            mock_profile.return_value.to_dict.return_value = {
                "primary_language": "python",
                "package_managers": ["pip"],
                "test_runner_hints": ["pytest"],
                "ci_provider": "github_actions",
                "has_tests_dir": True,
            }
            mock_metrics.return_value = {"pass_rate": 0.9}
            mock_insights.return_value = {
                "quality": {
                    "avg_completeness_ratio": 0.98,
                    "avg_decision_quality_score": 0.82,
                }
            }
            mock_load_baseline.return_value = None
            mock_build.return_value = {
                "scores": {"overall": 88.1},
                "delta": None,
                "quick_wins": [],
            }

            response = client.get("/api/workflows/portability-scorecard?repo=.")
            assert response.status_code == 200
            data = response.json()
            assert data["success"] is True
            assert data["has_baseline"] is False
            assert data["scorecard"]["scores"]["overall"] == 88.1

    def test_save_portability_scorecard_baseline_returns_saved_baseline(self, client):
        with patch.object(agent_api, "detect_repo_profile") as mock_profile, \
             patch.object(agent_api.workflow_store, "get_metrics") as mock_metrics, \
             patch.object(agent_api.observability_store, "get_global_insights") as mock_insights, \
             patch.object(agent_api, "load_baseline") as mock_load_baseline, \
             patch.object(agent_api, "build_portability_scorecard") as mock_build, \
             patch.object(agent_api, "save_baseline") as mock_save:
            mock_profile.return_value.to_dict.return_value = {
                "primary_language": "python",
                "package_managers": ["pip"],
                "test_runner_hints": ["pytest"],
                "ci_provider": "github_actions",
                "has_tests_dir": True,
            }
            mock_metrics.return_value = {"pass_rate": 0.92}
            mock_insights.return_value = {
                "quality": {
                    "avg_completeness_ratio": 0.97,
                    "avg_decision_quality_score": 0.80,
                }
            }
            mock_load_baseline.return_value = None
            mock_build.return_value = {
                "scores": {"overall": 86.4},
                "delta": None,
                "quick_wins": [],
            }
            mock_save.return_value = {
                "repo_root": "/tmp/repo",
                "saved_at": "2026-01-01T00:00:00+00:00",
                "note": "first baseline",
                "scorecard": {"scores": {"overall": 86.4}},
            }

            response = client.post(
                "/api/workflows/portability-scorecard/baseline",
                json={"repo": ".", "note": "first baseline"},
            )
            assert response.status_code == 200
            data = response.json()
            assert data["success"] is True
            assert data["baseline"]["note"] == "first baseline"

    def test_get_portability_roi_report_returns_payload(self, client):
        with patch.object(agent_api, "detect_repo_profile") as mock_profile, \
             patch.object(agent_api.workflow_store, "get_metrics") as mock_metrics, \
             patch.object(agent_api.observability_store, "get_global_insights") as mock_insights, \
             patch.object(agent_api, "load_baseline") as mock_load_baseline, \
             patch.object(agent_api, "build_portability_scorecard") as mock_build_scorecard, \
             patch.object(agent_api, "build_portability_roi_report") as mock_build_report:
            mock_profile.return_value.to_dict.return_value = {
                "primary_language": "python",
                "package_managers": ["pip"],
                "test_runner_hints": ["pytest"],
                "ci_provider": "github_actions",
                "has_tests_dir": True,
            }
            mock_metrics.return_value = {"pass_rate": 0.93}
            mock_insights.return_value = {
                "quality": {
                    "avg_completeness_ratio": 0.98,
                    "avg_decision_quality_score": 0.84,
                }
            }
            mock_load_baseline.return_value = {"scorecard": {"scores": {"overall": 80.0}}}
            mock_build_scorecard.return_value = {
                "scores": {"overall": 87.0},
                "delta": {
                    "baseline_overall": 80.0,
                    "current_overall": 87.0,
                    "overall_delta": 7.0,
                    "trend": "improved",
                },
                "quick_wins": [],
            }
            mock_build_report.return_value = {
                "trend": "improved",
                "rows": [
                    {
                        "kpi": "Portability overall score",
                        "baseline": 80.0,
                        "current": 87.0,
                        "delta": 7.0,
                        "direction": "improved",
                    }
                ],
                "quick_wins": [],
            }

            response = client.get("/api/workflows/portability-scorecard/roi-report?repo=.")
            assert response.status_code == 200
            data = response.json()
            assert data["success"] is True
            assert data["has_baseline"] is True
            assert data["report"]["trend"] == "improved"


class TestChatEndpoints:
    """Tests for dashboard chat APIs."""

    def test_create_chat_session_returns_payload(self, client):
        with patch.object(agent_api.workflow_store, "create_chat_session") as mock_create:
            mock_create.return_value = {
                "id": "cs_abc123",
                "repo": ".",
                "requester": "dashboard_chat",
                "metadata": {"source": "dashboard"},
                "created_at": "2026-01-01T00:00:00+00:00",
                "updated_at": "2026-01-01T00:00:00+00:00",
            }
            response = client.post("/api/chat/sessions", json={"repo": ".", "requester": "dashboard_chat"})
            assert response.status_code == 200
            data = response.json()
            assert data["success"] is True
            assert data["session"]["id"] == "cs_abc123"

    def test_chat_turn_persists_and_creates_workflow(self, client):
        with patch.object(agent_api.workflow_store, "get_chat_session") as mock_get_session, \
             patch.object(agent_api.workflow_store, "create_chat_session") as mock_create_session, \
             patch.object(agent_api.workflow_store, "add_chat_message") as mock_add_message, \
             patch.object(agent_api.workflow_store, "create_request") as mock_create_request:
            mock_get_session.return_value = {
                "id": "cs_abc123",
                "repo": ".",
                "requester": "dashboard_chat",
                "metadata": {},
                "created_at": "2026-01-01T00:00:00+00:00",
                "updated_at": "2026-01-01T00:00:00+00:00",
                "messages": [],
            }
            mock_create_session.return_value = mock_get_session.return_value
            mock_add_message.side_effect = [
                {
                    "id": 1,
                    "session_id": "cs_abc123",
                    "role": "user",
                    "content": "Add retries",
                    "metadata": {},
                    "request_id": None,
                    "created_at": "2026-01-01T00:00:00+00:00",
                },
                {
                    "id": 2,
                    "session_id": "cs_abc123",
                    "role": "assistant",
                    "content": "Captured your request",
                    "metadata": {"source": "chat_orchestrator"},
                    "request_id": "wr_abc123",
                    "created_at": "2026-01-01T00:00:01+00:00",
                },
            ]
            mock_create_request.return_value = {
                "id": "wr_abc123",
                "status": "AWAITING_APPROVAL",
                "next_action": "approve_to_queue",
            }

            response = client.post(
                "/api/chat/turn",
                json={
                    "session_id": "cs_abc123",
                    "message": "Add retries",
                    "repo": ".",
                    "requester": "dashboard_chat",
                    "auto_create_workflow": True,
                },
            )
            assert response.status_code == 200
            data = response.json()
            assert data["success"] is True
            assert data["session_id"] == "cs_abc123"
            assert data["workflow_request"]["id"] == "wr_abc123"

    def test_chat_turn_suggest_only_does_not_create_workflow(self, client):
        with patch.object(agent_api.workflow_store, "get_chat_session") as mock_get_session, \
             patch.object(agent_api.workflow_store, "add_chat_message") as mock_add_message, \
             patch.object(agent_api.workflow_store, "create_request") as mock_create_request:
            mock_get_session.return_value = {
                "id": "cs_abc123",
                "repo": ".",
                "requester": "dashboard_chat",
                "metadata": {},
                "created_at": "2026-01-01T00:00:00+00:00",
                "updated_at": "2026-01-01T00:00:00+00:00",
                "messages": [],
            }
            mock_add_message.side_effect = [
                {
                    "id": 1,
                    "session_id": "cs_abc123",
                    "role": "user",
                    "content": "show me scorecard",
                    "metadata": {},
                    "request_id": None,
                    "created_at": "2026-01-01T00:00:00+00:00",
                },
                {
                    "id": 2,
                    "session_id": "cs_abc123",
                    "role": "assistant",
                    "content": "Message saved",
                    "metadata": {"source": "chat_orchestrator"},
                    "request_id": None,
                    "created_at": "2026-01-01T00:00:01+00:00",
                },
            ]

            response = client.post(
                "/api/chat/turn",
                json={
                    "session_id": "cs_abc123",
                    "message": "show me scorecard",
                    "repo": ".",
                    "requester": "dashboard_chat",
                    "auto_create_workflow": True,
                    "tool_execution": "suggest_only",
                    "mode": "llm",
                },
            )
            assert response.status_code == 200
            data = response.json()
            assert data["success"] is True
            assert data["workflow_request"] is None
            assert data["tool_execution"] == "suggest_only"
            assert data["mode"] == "llm"
            assert isinstance(data["action_plan"], list)
            mock_create_request.assert_not_called()


class TestOperatorConfigEndpoints:
    """Tests for operator config endpoints."""

    def test_get_operator_config_returns_safe_payload(self, client):
        with patch.dict("os.environ", {
            "AGENTICQA_LLM_PROVIDER": "openai",
            "AGENTICQA_LLM_MODEL": "gpt-4o-mini",
            "AGENTICQA_LLM_API_KEY": "secret",
        }):
            response = client.get("/api/operator/config")
            assert response.status_code == 200
            data = response.json()
            assert data["success"] is True
            assert data["llm"]["provider"] == "openai"
            assert data["llm"]["configured"] is True

    def test_test_operator_config_connection_handles_missing_key(self, client):
        with patch.dict("os.environ", {
            "AGENTICQA_LLM_PROVIDER": "openai",
            "AGENTICQA_LLM_MODEL": "gpt-4o-mini",
            "AGENTICQA_LLM_API_KEY": "",
        }, clear=False):
            response = client.post("/api/operator/config/test-connection")
            assert response.status_code == 200
            data = response.json()
            assert data["success"] is True
            assert data["ok"] is False
