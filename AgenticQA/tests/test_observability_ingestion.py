"""Tests for cross-platform agent ingestion.

Simulates a LangGraph execution (chain → tool → LLM call) flowing through
the ingest layer and verifies all observability endpoints work on the result.
"""

import sys
import os
import uuid
from unittest.mock import patch, MagicMock

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))


# ------------------------------------------------------------------ #
# Unit: event schema normalization                                     #
# ------------------------------------------------------------------ #

@pytest.mark.unit
class TestNormalizeEvent:

    def test_langchain_fields_mapped_correctly(self):
        from agenticqa.ingestion.event_schema import normalize_event
        payload = {
            "run_id": "run-abc",
            "parent_run_id": "run-parent",
            "name": "my_chain",
            "status": "end",
            "token_usage": {"prompt_tokens": 150, "completion_tokens": 80},
        }
        evt = normalize_event(payload)
        assert evt.span_id == "run-abc"
        assert evt.parent_span_id == "run-parent"
        assert evt.agent == "my_chain"
        assert evt.status == "COMPLETED"
        assert evt.llm_prompt_tokens == 150
        assert evt.llm_completion_tokens == 80

    def test_crewai_fields_mapped(self):
        from agenticqa.ingestion.event_schema import normalize_event
        payload = {
            "crew_id": "crew-xyz",
            "task_id": "task-001",
            "sender": "ResearchAgent",
            "message_type": "task_result",
            "status": "success",
        }
        evt = normalize_event(payload)
        assert evt.trace_id == "crew-xyz"
        assert evt.agent == "ResearchAgent"
        assert evt.status == "COMPLETED"

    def test_generic_passthrough(self):
        from agenticqa.ingestion.event_schema import normalize_event
        payload = {
            "trace_id": "t1",
            "agent": "my_agent",
            "action": "classify",
            "status": "FAILED",
            "error": "timeout",
        }
        evt = normalize_event(payload)
        assert evt.trace_id == "t1"
        assert evt.status == "FAILED"
        assert evt.error == "timeout"

    def test_status_aliases_normalised(self):
        from agenticqa.ingestion.event_schema import normalize_event
        for raw, expected in [("start", "STARTED"), ("error", "FAILED"), ("done", "COMPLETED")]:
            evt = normalize_event({"trace_id": "t", "agent": "a", "action": "x", "status": raw})
            assert evt.status == expected, f"Expected {expected} for raw='{raw}'"


# ------------------------------------------------------------------ #
# Unit: LangChainCallbackAdapter (no LangChain dependency)            #
# ------------------------------------------------------------------ #

@pytest.mark.unit
class TestLangChainCallbackAdapter:

    def _make_adapter(self, tmp_path):
        from agenticqa.observability import ObservabilityStore
        from agenticqa.ingestion.adapters import LangChainCallbackAdapter
        store = ObservabilityStore(db_path=str(tmp_path / "obs.db"))
        adapter = LangChainCallbackAdapter(
            store=store, trace_id="langgraph-trace-001", agent_name="MyLangGraphAgent"
        )
        return adapter, store

    def test_chain_start_end_creates_completed_span(self, tmp_path):
        adapter, store = self._make_adapter(tmp_path)
        run_id = str(uuid.uuid4())
        adapter.on_chain_start({"name": "MyChain"}, {"question": "hi"}, run_id=run_id)
        adapter.on_chain_end({"answer": "hello"}, run_id=run_id)

        events = store.list_events(trace_id="langgraph-trace-001")
        statuses = {e["status"] for e in events}
        assert "STARTED" in statuses
        assert "COMPLETED" in statuses

    def test_tool_error_creates_failed_span(self, tmp_path):
        adapter, store = self._make_adapter(tmp_path)
        run_id = str(uuid.uuid4())
        adapter.on_tool_start({"name": "search"}, "query", run_id=run_id)
        adapter.on_tool_error(RuntimeError("search timeout"), run_id=run_id)

        events = store.list_events(trace_id="langgraph-trace-001")
        failed = [e for e in events if e["status"] == "FAILED"]
        assert len(failed) == 1
        assert "search timeout" in (failed[0]["error"] or "")

    def test_llm_end_records_token_usage(self, tmp_path):
        adapter, store = self._make_adapter(tmp_path)
        run_id = str(uuid.uuid4())

        class FakeLLMResult:
            llm_output = {"token_usage": {"prompt_tokens": 200, "completion_tokens": 90}}

        adapter.on_llm_end(FakeLLMResult(), run_id=run_id)

        c = store.conn.cursor()
        rows = c.execute(
            "SELECT llm_prompt_tokens, llm_completion_tokens FROM agent_complexity_metrics"
        ).fetchall()
        assert len(rows) == 1
        assert rows[0][0] == 200
        assert rows[0][1] == 90

    def test_full_langgraph_sequence_produces_valid_trace(self, tmp_path):
        """Simulate: LangGraph node → tool call → LLM → chain end. Verify audit report works."""
        from agenticqa.observability import ObservabilityStore
        from agenticqa.ingestion.adapters import LangChainCallbackAdapter
        from agenticqa.audit_report import build_audit_report

        store = ObservabilityStore(db_path=str(tmp_path / "obs2.db"))
        trace_id = "langgraph-e2e-001"
        adapter = LangChainCallbackAdapter(store=store, trace_id=trace_id, agent_name="ResearchNode")

        chain_run = str(uuid.uuid4())
        tool_run = str(uuid.uuid4())
        llm_run = str(uuid.uuid4())

        # Chain (LangGraph node) starts
        adapter.on_chain_start({"name": "ResearchNode"}, {"query": "test"}, run_id=chain_run)
        # Tool call within node
        adapter.on_tool_start({"name": "web_search"}, "test query", run_id=tool_run, parent_run_id=chain_run)
        adapter.on_tool_end("results...", run_id=tool_run)
        # LLM synthesis
        class FakeResult:
            llm_output = {"token_usage": {"prompt_tokens": 512, "completion_tokens": 128}}
        adapter.on_llm_end(FakeResult(), run_id=llm_run)
        # Chain ends
        adapter.on_chain_end({"answer": "42"}, run_id=chain_run)

        # Verify audit report builds without error on externally ingested trace
        report = build_audit_report(trace_id=trace_id, obs_store=store)
        assert report["trace_id"] == trace_id
        assert report["verdict"] in {"PASS", "FAIL"}
        assert "ResearchNode" in report["summary"]["agents_involved"]
        assert "markdown_body" in report

        # Verify complexity trends capture token usage
        trends = store.get_complexity_trends(agent="ResearchNode", window_days=1)
        assert trends["summary"]["total_llm_prompt_tokens"] == 512
        assert trends["summary"]["total_llm_completion_tokens"] == 128

        store.close()


# ------------------------------------------------------------------ #
# API: ingest endpoints                                                #
# ------------------------------------------------------------------ #

import agent_api

@pytest.fixture
def client():
    return TestClient(agent_api.app)


@pytest.mark.unit
class TestIngestEndpoints:

    def test_single_ingest_stores_event(self, client):
        mock_obs = MagicMock()
        with patch.object(agent_api, "observability_store", mock_obs), \
             patch.object(agent_api, "_normalize_ingest_event") as mock_norm:
            mock_evt = MagicMock()
            mock_evt.trace_id = "tr-ext"
            mock_evt.agent = "LangGraphAgent"
            mock_evt.status = "COMPLETED"
            mock_evt.request_id = None
            mock_evt.span_id = None
            mock_evt.parent_span_id = None
            mock_evt.event_type = None
            mock_evt.step_key = None
            mock_evt.latency_ms = None
            mock_evt.decision = {}
            mock_evt.error = None
            mock_evt.metadata = {}
            mock_evt.llm_prompt_tokens = None
            mock_evt.llm_completion_tokens = None
            mock_norm.return_value = mock_evt

            response = client.post("/api/observability/ingest", json={
                "trace_id": "tr-ext", "agent": "LangGraphAgent",
                "action": "chain", "status": "COMPLETED",
            })
            assert response.status_code == 200
            data = response.json()
            assert data["success"] is True
            assert data["trace_id"] == "tr-ext"
            mock_obs.log_event.assert_called_once()

    def test_batch_ingest_returns_results_array(self, client):
        mock_obs = MagicMock()
        with patch.object(agent_api, "observability_store", mock_obs), \
             patch.object(agent_api, "_normalize_ingest_event") as mock_norm:
            def _make_evt(d):
                e = MagicMock()
                e.trace_id = d.get("trace_id", "t")
                e.agent = d.get("agent", "a")
                e.status = "COMPLETED"
                e.request_id = e.span_id = e.parent_span_id = None
                e.event_type = e.step_key = e.error = None
                e.latency_ms = None
                e.decision = e.metadata = {}
                e.llm_prompt_tokens = e.llm_completion_tokens = None
                return e
            mock_norm.side_effect = lambda d: _make_evt(d)

            response = client.post("/api/observability/ingest/batch", json={"events": [
                {"trace_id": "t1", "agent": "NodeA", "action": "run", "status": "COMPLETED"},
                {"trace_id": "t1", "agent": "NodeB", "action": "run", "status": "FAILED"},
            ]})
            assert response.status_code == 200
            data = response.json()
            assert data["total"] == 2
            assert data["errors"] == 0
            assert len(data["results"]) == 2

    def test_batch_ingest_with_token_counts_logs_complexity(self, client):
        mock_obs = MagicMock()
        with patch.object(agent_api, "observability_store", mock_obs), \
             patch.object(agent_api, "_normalize_ingest_event") as mock_norm:
            evt = MagicMock()
            evt.trace_id = "t2"
            evt.agent = "GPT4Agent"
            evt.status = "COMPLETED"
            evt.request_id = evt.span_id = evt.parent_span_id = None
            evt.event_type = evt.step_key = evt.error = None
            evt.latency_ms = None
            evt.decision = evt.metadata = {}
            evt.llm_prompt_tokens = 300
            evt.llm_completion_tokens = 120
            mock_norm.return_value = evt

            response = client.post("/api/observability/ingest", json={
                "trace_id": "t2", "agent": "GPT4Agent", "action": "llm_call",
                "status": "COMPLETED", "llm_prompt_tokens": 300, "llm_completion_tokens": 120,
            })
            assert response.status_code == 200
            mock_obs.log_complexity_metric.assert_called_once()
            call_kwargs = mock_obs.log_complexity_metric.call_args.kwargs
            assert call_kwargs["llm_prompt_tokens"] == 300
            assert call_kwargs["llm_completion_tokens"] == 120
