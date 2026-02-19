"""
Tests for GraphRAG-informed delegation (Phase 4).
"""

import pytest
import os
import sys
from unittest.mock import MagicMock, Mock, PropertyMock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from agenticqa.verification.outcome_tracker import OutcomeTracker


@pytest.fixture
def tmp_db(tmp_path):
    return str(tmp_path / "test.db")


def _make_agent_with_registry(graph_store=None, outcome_db=None):
    """Create a BaseAgent subclass with mocked registry."""
    from agents import QAAssistantAgent

    agent = QAAssistantAgent.__new__(QAAssistantAgent)
    agent.agent_name = "QA_Assistant"
    agent.use_rag = False
    agent.use_data_store = False
    agent.rag = None
    agent.feedback = None
    agent._last_retrieved_doc_ids = []
    agent.execution_history = []
    agent._delegation_depth = 0
    agent._threshold_calibrator = None
    agent._strategy_selector = None

    # Mock registry
    registry = MagicMock()
    registry.delegate_task = Mock(return_value={"status": "success", "result": "ok"})
    if graph_store:
        registry.tracker = MagicMock()
        registry.tracker.graph_store = graph_store
    agent.agent_registry = registry

    # Outcome tracker
    if outcome_db:
        agent.outcome_tracker = OutcomeTracker(db_path=outcome_db)
    else:
        agent.outcome_tracker = None

    return agent


@pytest.mark.unit
class TestGraphRAGDelegation:

    def test_delegation_works_without_graph_store(self):
        """Static delegation unchanged when Neo4j unavailable."""
        agent = _make_agent_with_registry()
        result = agent.delegate_to_agent("SRE_Agent", {"task": "fix_lint"})

        assert result["status"] == "success"
        agent.agent_registry.delegate_task.assert_called_once()
        call_kwargs = agent.agent_registry.delegate_task.call_args
        assert call_kwargs[1]["to_agent"] == "SRE_Agent"

    def test_high_risk_triggers_recommendation(self):
        """When failure risk is high, GraphRAG alternative is used."""
        graph_store = MagicMock()
        graph_store.predict_delegation_failure_risk = Mock(return_value={
            "risk_level": "high",
            "failure_probability": 0.8,
            "confidence": 0.7,
        })
        graph_store.recommend_delegation_target = Mock(return_value={
            "recommended_agent": "SDET_Agent",
            "success_count": 5,
            "priority_score": 8.0,
        })

        agent = _make_agent_with_registry(graph_store=graph_store)
        result = agent.delegate_to_agent("SRE_Agent", {"task_type": "generate_tests"})

        assert result["status"] == "success"
        call_kwargs = agent.agent_registry.delegate_task.call_args
        assert call_kwargs[1]["to_agent"] == "SDET_Agent"

    def test_low_risk_keeps_original_target(self):
        """When failure risk is low, original target is kept."""
        graph_store = MagicMock()
        graph_store.predict_delegation_failure_risk = Mock(return_value={
            "risk_level": "low",
            "failure_probability": 0.1,
            "confidence": 0.8,
        })

        agent = _make_agent_with_registry(graph_store=graph_store)
        result = agent.delegate_to_agent("SRE_Agent", {"task": "fix_lint"})

        call_kwargs = agent.agent_registry.delegate_task.call_args
        assert call_kwargs[1]["to_agent"] == "SRE_Agent"

    def test_outcome_recorded_on_success(self, tmp_db):
        """OutcomeTracker records prediction and success outcome."""
        agent = _make_agent_with_registry(outcome_db=tmp_db)
        agent.delegate_to_agent("SRE_Agent", {"task_type": "fix_lint"})

        # Check that outcome was recorded
        cursor = agent.outcome_tracker.conn.cursor()
        cursor.execute("SELECT * FROM delegation_outcomes")
        rows = cursor.fetchall()
        assert len(rows) == 1
        row = dict(rows[0])
        assert row["actual_success"] == 1
        assert row["from_agent"] == "QA_Assistant"
        assert row["to_agent"] == "SRE_Agent"
        assert row["duration_ms"] is not None
        agent.outcome_tracker.close()

    def test_outcome_recorded_on_failure(self, tmp_db):
        """OutcomeTracker records failure when delegation raises."""
        agent = _make_agent_with_registry(outcome_db=tmp_db)
        agent.agent_registry.delegate_task = Mock(side_effect=RuntimeError("boom"))

        with pytest.raises(RuntimeError):
            agent.delegate_to_agent("SRE_Agent", {"task_type": "fix_lint"})

        cursor = agent.outcome_tracker.conn.cursor()
        cursor.execute("SELECT actual_success FROM delegation_outcomes")
        row = cursor.fetchone()
        assert row["actual_success"] == 0
        agent.outcome_tracker.close()

    def test_graphrag_failure_gracefully_falls_through(self):
        """If GraphRAG lookup fails, delegation proceeds normally."""
        graph_store = MagicMock()
        graph_store.predict_delegation_failure_risk = Mock(side_effect=Exception("neo4j down"))

        agent = _make_agent_with_registry(graph_store=graph_store)
        result = agent.delegate_to_agent("SRE_Agent", {"task": "fix"})

        assert result["status"] == "success"
        call_kwargs = agent.agent_registry.delegate_task.call_args
        assert call_kwargs[1]["to_agent"] == "SRE_Agent"
