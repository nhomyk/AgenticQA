"""
Tests for pattern-driven execution strategy (Phase 3).
"""

import pytest
import os
import sys
from unittest.mock import MagicMock, Mock, patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))


def _make_agent_with_patterns(patterns):
    """Create a QAAssistantAgent with mocked pattern insights."""
    from agents import QAAssistantAgent

    agent = QAAssistantAgent.__new__(QAAssistantAgent)
    agent.agent_name = "QA_Assistant"
    agent.use_rag = False
    agent.use_data_store = True
    agent.rag = None
    agent.feedback = None
    agent.outcome_tracker = None
    agent._threshold_calibrator = None
    agent._strategy_selector = None
    agent._last_retrieved_doc_ids = []
    agent.execution_history = []
    agent.pipeline = MagicMock()
    agent.pipeline.analyze_patterns = Mock(return_value=patterns)
    return agent


@pytest.mark.unit
class TestPatternDrivenStrategy:

    def test_standard_strategy_when_no_issues(self):
        """Default strategy when no failure patterns detected."""
        patterns = {
            "errors": {"total_failures": 0, "failure_by_type": {}},
            "performance": {"avg_latency_ms": 500},
            "flakiness": {"flaky_agents": {}},
        }
        agent = _make_agent_with_patterns(patterns)
        strategy = agent._get_execution_strategy()

        assert strategy["extra_caution"] is False
        assert strategy["confidence_adjustment"] == 1.0
        assert strategy["recent_failure_rate"] == 0.0

    def test_cautious_strategy_when_flaky(self):
        """Extra caution when agent is identified as flaky."""
        patterns = {
            "errors": {"total_failures": 5, "failure_by_type": {"timeout": 3}},
            "performance": {"avg_latency_ms": 500},
            "flakiness": {
                "flaky_agents": {
                    "QA_Assistant": {"fail_rate": 0.45, "pass": 6, "fail": 5}
                }
            },
        }
        agent = _make_agent_with_patterns(patterns)
        strategy = agent._get_execution_strategy()

        assert strategy["extra_caution"] is True
        assert strategy["confidence_adjustment"] == 1.2
        assert strategy["recent_failure_rate"] == 0.45

    def test_known_failure_types_populated(self):
        """Strategy includes top failure types from pattern analysis."""
        patterns = {
            "errors": {
                "total_failures": 10,
                "failure_by_type": {"timeout": 5, "assertion": 3, "connection": 2},
            },
            "performance": {"avg_latency_ms": 500},
            "flakiness": {"flaky_agents": {}},
        }
        agent = _make_agent_with_patterns(patterns)
        strategy = agent._get_execution_strategy()

        assert "timeout" in strategy["known_failure_types"]
        assert len(strategy["known_failure_types"]) <= 5

    def test_high_latency_triggers_caution(self):
        """High average latency triggers extra caution."""
        patterns = {
            "errors": {"total_failures": 0, "failure_by_type": {}},
            "performance": {"avg_latency_ms": 6000},
            "flakiness": {"flaky_agents": {}},
        }
        agent = _make_agent_with_patterns(patterns)
        strategy = agent._get_execution_strategy()

        assert strategy["extra_caution"] is True

    def test_graceful_without_data_store(self):
        """Strategy returns defaults when data store disabled."""
        from agents import QAAssistantAgent

        agent = QAAssistantAgent.__new__(QAAssistantAgent)
        agent.agent_name = "QA_Assistant"
        agent.use_data_store = False
        agent.use_rag = False
        agent.rag = None
        agent.feedback = None
        agent.outcome_tracker = None
        agent._threshold_calibrator = None
        agent._strategy_selector = None
        agent._last_retrieved_doc_ids = []
        agent.execution_history = []

        strategy = agent._get_execution_strategy()
        assert strategy["extra_caution"] is False
        assert strategy["confidence_adjustment"] == 1.0
