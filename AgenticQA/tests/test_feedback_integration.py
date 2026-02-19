"""
Tests for the closed feedback loop in BaseAgent.

Verifies that:
1. Retrieved doc IDs are tracked during RAG augmentation
2. Feedback is recorded after execution (boost on success, penalize on failure)
3. Reranking is applied during augmentation using feedback scores
4. System degrades gracefully when feedback module is unavailable
"""

import pytest
import os
import sys
from unittest.mock import MagicMock, Mock, patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from agenticqa.verification.feedback_loop import RelevanceFeedback


@pytest.fixture
def tmp_db(tmp_path):
    """Return a path for a temp SQLite db."""
    return str(tmp_path / "test.db")


@pytest.fixture
def feedback_db(tmp_path):
    """Return a path for a temp feedback db."""
    return str(tmp_path / "feedback.db")


@pytest.fixture
def outcome_db(tmp_path):
    """Return a path for a temp outcome db."""
    return str(tmp_path / "outcome.db")


def _make_mock_rag_with_doc_ids():
    """Create a mock RAG that returns recommendations with doc_ids."""
    rag = MagicMock()
    rag.augment_agent_context = Mock(return_value={
        "rag_recommendations": [
            {
                "type": "test_pattern",
                "insight": "Similar test failed with timeout",
                "confidence": 0.85,
                "source": {"doc_id": "doc-001", "test_name": "test_login"},
            },
            {
                "type": "test_pattern",
                "insight": "Test passed after retry",
                "confidence": 0.72,
                "source": {"doc_id": "doc-002", "test_name": "test_auth"},
            },
            {
                "type": "test_pattern",
                "insight": "Low confidence pattern",
                "confidence": 0.40,
                "source": {"doc_id": "doc-003", "test_name": "test_misc"},
            },
        ],
        "rag_insights_count": 3,
        "high_confidence_insights": [
            {
                "type": "test_pattern",
                "insight": "Similar test failed with timeout",
                "confidence": 0.85,
                "source": {"doc_id": "doc-001", "test_name": "test_login"},
            },
        ],
    })
    return rag


@pytest.mark.unit
class TestFeedbackLoopClosed:
    """Tests that the feedback loop is properly closed in BaseAgent."""

    def test_doc_ids_tracked_during_augmentation(self, feedback_db, outcome_db):
        """Retrieved doc IDs are stored on _last_retrieved_doc_ids."""
        from agents import QAAssistantAgent

        agent = QAAssistantAgent.__new__(QAAssistantAgent)
        agent.agent_name = "QA_Assistant"
        agent.use_rag = True
        agent.use_data_store = False
        agent.rag = _make_mock_rag_with_doc_ids()
        agent.feedback = RelevanceFeedback(db_path=feedback_db)
        agent.outcome_tracker = None
        agent._last_retrieved_doc_ids = []
        agent.execution_history = []

        context = {"test_name": "test_login", "test_type": "unit"}
        agent._augment_with_rag(context)

        assert len(agent._last_retrieved_doc_ids) == 3
        assert "doc-001" in agent._last_retrieved_doc_ids
        assert "doc-002" in agent._last_retrieved_doc_ids
        assert "doc-003" in agent._last_retrieved_doc_ids

        agent.feedback.close()

    def test_retrieval_recorded_in_feedback_db(self, feedback_db, outcome_db):
        """record_retrieval is called for each doc during augmentation."""
        from agents import QAAssistantAgent

        agent = QAAssistantAgent.__new__(QAAssistantAgent)
        agent.agent_name = "QA_Assistant"
        agent.use_rag = True
        agent.use_data_store = False
        agent.rag = _make_mock_rag_with_doc_ids()
        agent.feedback = RelevanceFeedback(db_path=feedback_db)
        agent.outcome_tracker = None
        agent._last_retrieved_doc_ids = []
        agent.execution_history = []

        agent._augment_with_rag({"test_name": "test_x", "test_type": "unit"})

        # Verify retrieval was recorded
        stats_1 = agent.feedback.get_document_stats("doc-001")
        stats_2 = agent.feedback.get_document_stats("doc-002")
        assert stats_1 is not None
        assert stats_1["times_retrieved"] >= 1
        assert stats_2 is not None
        assert stats_2["times_retrieved"] >= 1

        agent.feedback.close()

    def test_successful_execution_boosts_retrieved_docs(self, feedback_db):
        """After successful execution, retrieved doc scores increase."""
        from agents import QAAssistantAgent

        agent = QAAssistantAgent.__new__(QAAssistantAgent)
        agent.agent_name = "QA_Assistant"
        agent.use_rag = True
        agent.use_data_store = False
        agent.rag = _make_mock_rag_with_doc_ids()
        agent.feedback = RelevanceFeedback(db_path=feedback_db)
        agent.outcome_tracker = None
        agent._last_retrieved_doc_ids = []
        agent.execution_history = []

        # Augment to track docs
        agent._augment_with_rag({"test_name": "test_x", "test_type": "unit"})

        # Record successful execution
        agent._record_execution("success", {"total_tests": 10, "passed": 10})

        # Check scores were boosted
        score_1 = agent.feedback.get_effective_score("doc-001")
        score_2 = agent.feedback.get_effective_score("doc-002")
        assert score_1 > 1.0, f"Expected boost, got {score_1}"
        assert score_2 > 1.0, f"Expected boost, got {score_2}"

        # Verify doc IDs were cleared after feedback
        assert agent._last_retrieved_doc_ids == []

        agent.feedback.close()

    def test_failed_execution_penalizes_retrieved_docs(self, feedback_db):
        """After failed execution, retrieved doc scores decrease."""
        from agents import QAAssistantAgent

        agent = QAAssistantAgent.__new__(QAAssistantAgent)
        agent.agent_name = "QA_Assistant"
        agent.use_rag = True
        agent.use_data_store = False
        agent.rag = _make_mock_rag_with_doc_ids()
        agent.feedback = RelevanceFeedback(db_path=feedback_db)
        agent.outcome_tracker = None
        agent._last_retrieved_doc_ids = []
        agent.execution_history = []

        # Augment to track docs
        agent._augment_with_rag({"test_name": "test_x", "test_type": "unit"})

        # Record failed execution
        agent._record_execution("error", {"error": "test failure"})

        # Check scores were penalized
        score_1 = agent.feedback.get_effective_score("doc-001")
        score_2 = agent.feedback.get_effective_score("doc-002")
        assert score_1 < 1.0, f"Expected penalty, got {score_1}"
        assert score_2 < 1.0, f"Expected penalty, got {score_2}"

        agent.feedback.close()

    def test_reranking_applied_during_augmentation(self, feedback_db):
        """Documents with higher feedback scores rank higher after reranking."""
        from agents import QAAssistantAgent

        feedback = RelevanceFeedback(db_path=feedback_db)

        # Pre-seed: boost doc-003 heavily, penalize doc-001
        feedback.record_retrieval("doc-003", "test_pattern")
        feedback.record_retrieval("doc-001", "test_pattern")
        for _ in range(10):
            feedback.record_feedback("doc-003", success=True)
            feedback.record_feedback("doc-001", success=False)

        agent = QAAssistantAgent.__new__(QAAssistantAgent)
        agent.agent_name = "QA_Assistant"
        agent.use_rag = True
        agent.use_data_store = False
        agent.rag = _make_mock_rag_with_doc_ids()
        agent.feedback = feedback
        agent.outcome_tracker = None
        agent._last_retrieved_doc_ids = []
        agent.execution_history = []

        result = agent._augment_with_rag({"test_name": "test_x", "test_type": "unit"})

        recs = result.get("rag_recommendations", [])
        assert len(recs) >= 2

        # After reranking, doc-003 (boosted) should rank higher than doc-001 (penalized)
        doc_003_idx = next((i for i, r in enumerate(recs) if r.get("source", {}).get("doc_id") == "doc-003"), None)
        doc_001_idx = next((i for i, r in enumerate(recs) if r.get("source", {}).get("doc_id") == "doc-001"), None)
        assert doc_003_idx is not None and doc_001_idx is not None
        assert doc_003_idx < doc_001_idx, "Boosted doc should rank higher than penalized doc"

        feedback.close()

    def test_cumulative_feedback_over_multiple_executions(self, feedback_db):
        """Multiple successful executions compound the boost."""
        from agents import QAAssistantAgent

        agent = QAAssistantAgent.__new__(QAAssistantAgent)
        agent.agent_name = "QA_Assistant"
        agent.use_rag = True
        agent.use_data_store = False
        agent.rag = _make_mock_rag_with_doc_ids()
        agent.feedback = RelevanceFeedback(db_path=feedback_db)
        agent.outcome_tracker = None
        agent._last_retrieved_doc_ids = []
        agent.execution_history = []

        # Run 3 augment+record cycles
        for _ in range(3):
            agent._augment_with_rag({"test_name": "test_x", "test_type": "unit"})
            agent._record_execution("success", {"total_tests": 10, "passed": 10})

        score = agent.feedback.get_effective_score("doc-001")
        # 3 boosts of 0.05 each = 1.15
        assert score > 1.1, f"Expected cumulative boost, got {score}"

        agent.feedback.close()

    def test_graceful_degradation_without_feedback(self):
        """Agent works fine when feedback module is None."""
        from agents import QAAssistantAgent

        agent = QAAssistantAgent.__new__(QAAssistantAgent)
        agent.agent_name = "QA_Assistant"
        agent.use_rag = True
        agent.use_data_store = False
        agent.rag = _make_mock_rag_with_doc_ids()
        agent.feedback = None
        agent.outcome_tracker = None
        agent._last_retrieved_doc_ids = []
        agent.execution_history = []

        # Should not raise
        result = agent._augment_with_rag({"test_name": "test_x", "test_type": "unit"})
        assert "rag_recommendations" in result
        assert len(result["rag_recommendations"]) == 3

        # Record execution should not raise
        agent._record_execution("success", {"total_tests": 10, "passed": 10})

    def test_no_doc_ids_when_rag_disabled(self):
        """_last_retrieved_doc_ids is empty when RAG is disabled."""
        from agents import QAAssistantAgent

        agent = QAAssistantAgent.__new__(QAAssistantAgent)
        agent.agent_name = "QA_Assistant"
        agent.use_rag = False
        agent.use_data_store = False
        agent.rag = None
        agent.feedback = None
        agent.outcome_tracker = None
        agent._last_retrieved_doc_ids = ["stale"]
        agent.execution_history = []

        result = agent._augment_with_rag({"test_name": "test_x", "test_type": "unit"})
        assert agent._last_retrieved_doc_ids == []
        assert result == {"test_name": "test_x", "test_type": "unit"}

    def test_recommendations_without_doc_id_skipped(self, feedback_db):
        """Recommendations missing doc_id in source are not tracked."""
        from agents import QAAssistantAgent

        rag = MagicMock()
        rag.augment_agent_context = Mock(return_value={
            "rag_recommendations": [
                {
                    "type": "test_pattern",
                    "insight": "No doc_id here",
                    "confidence": 0.9,
                    "source": {"test_name": "test_no_id"},
                },
            ],
            "rag_insights_count": 1,
        })

        agent = QAAssistantAgent.__new__(QAAssistantAgent)
        agent.agent_name = "QA_Assistant"
        agent.use_rag = True
        agent.use_data_store = False
        agent.rag = rag
        agent.feedback = RelevanceFeedback(db_path=feedback_db)
        agent.outcome_tracker = None
        agent._last_retrieved_doc_ids = []
        agent.execution_history = []

        agent._augment_with_rag({"test_name": "test_x", "test_type": "unit"})

        # No doc IDs should be tracked
        assert agent._last_retrieved_doc_ids == []

        agent.feedback.close()
