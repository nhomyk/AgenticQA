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

    def test_strategy_has_flakiness_trend_and_error_signatures_keys(self):
        """Strategy dict always includes flakiness_trend and error_signatures keys."""
        patterns = {
            "errors": {"total_failures": 0, "failure_by_type": {}},
            "performance": {"avg_latency_ms": 200},
            "flakiness": {"flaky_agents": {}},
        }
        agent = _make_agent_with_patterns(patterns)
        agent.pattern_analyzer = None  # no store attached
        strategy = agent._get_execution_strategy()

        assert "flakiness_trend" in strategy
        assert "error_signatures" in strategy
        assert isinstance(strategy["error_signatures"], list)

    def test_accelerating_flakiness_escalates_confidence_adjustment(self):
        """Accelerating flakiness trend raises confidence_adjustment to at least 1.3."""
        patterns = {
            "errors": {"total_failures": 3, "failure_by_type": {}},
            "performance": {"avg_latency_ms": 300},
            "flakiness": {
                "flaky_agents": {
                    "QA_Assistant": {
                        "fail_rate": 0.45,
                        "pass": 6,
                        "fail": 5,
                        "ewma_fail_rate": 0.35,
                        "trend": "accelerating",
                    }
                }
            },
        }
        agent = _make_agent_with_patterns(patterns)
        strategy = agent._get_execution_strategy()

        assert strategy["extra_caution"] is True
        assert strategy["confidence_adjustment"] >= 1.3
        assert strategy["flakiness_trend"] == "accelerating"


@pytest.mark.unit
class TestPatternAnalyzerEWMA:

    def _make_analyzer(self, artifacts_by_day):
        """Build a PatternAnalyzer with a mocked store returning pre-bucketed artifacts."""
        from data_store.pattern_analyzer import PatternAnalyzer

        mock_store = MagicMock()
        mock_store.patterns_dir = MagicMock()
        mock_store.patterns_dir.__truediv__ = lambda self, other: MagicMock()

        all_artifacts = []
        for day, entries in artifacts_by_day.items():
            for i, (status, source) in enumerate(entries):
                aid = f"{day}-{source}-{i}"
                all_artifacts.append({
                    "artifact_id": aid,
                    "timestamp": f"{day}T12:00:00",
                    "source": source,
                })
                mock_store.get_artifact.side_effect = lambda aid, _map={
                    f"{day}-{source}-{i}": {"status": status}
                    for day, entries in artifacts_by_day.items()
                    for i, (status, source) in enumerate(entries)
                }: _map.get(aid, {"status": "unknown"})

        mock_store.search_artifacts.return_value = all_artifacts
        analyzer = PatternAnalyzer.__new__(PatternAnalyzer)
        analyzer.store = mock_store
        analyzer.patterns_dir = MagicMock()
        analyzer.patterns_dir.__truediv__ = lambda self, other: MagicMock(
            write_text=lambda *a, **kw: None
        )
        # Patch open() so flakiness.json write doesn't fail
        return analyzer

    def test_analyze_flakiness_returns_trend_key(self):
        """Flaky agents now expose a 'trend' key."""
        from data_store.pattern_analyzer import PatternAnalyzer

        analyzer = PatternAnalyzer.__new__(PatternAnalyzer)
        analyzer.patterns_dir = MagicMock()
        mock_store = MagicMock()
        mock_store.search_artifacts.return_value = []
        analyzer.store = mock_store

        # Call with no data — flaky_agents should be empty dict, no crash
        with patch("builtins.open", MagicMock()):
            result = analyzer.analyze_flakiness()
        assert "flaky_agents" in result

    def test_compute_ewma_single_value(self):
        """EWMA of a single value is that value."""
        from data_store.pattern_analyzer import PatternAnalyzer
        assert PatternAnalyzer._compute_ewma([0.5]) == 0.5

    def test_compute_ewma_converges(self):
        """EWMA of constant series equals that constant."""
        from data_store.pattern_analyzer import PatternAnalyzer
        result = PatternAnalyzer._compute_ewma([0.4, 0.4, 0.4, 0.4])
        assert abs(result - 0.4) < 0.01

    def test_compute_ewma_empty_returns_zero(self):
        from data_store.pattern_analyzer import PatternAnalyzer
        assert PatternAnalyzer._compute_ewma([]) == 0.0

    def test_get_error_signatures_returns_ranked_list(self):
        """get_error_signatures returns dicts with signature/count/last_seen, ranked by count."""
        from data_store.pattern_analyzer import PatternAnalyzer
        from datetime import datetime, timedelta

        mock_store = MagicMock()
        today = datetime.utcnow()
        mock_store.search_artifacts.return_value = [
            {"artifact_id": "e1", "timestamp": (today - timedelta(days=1)).isoformat(), "source": "qa"},
            {"artifact_id": "e2", "timestamp": (today - timedelta(days=2)).isoformat(), "source": "qa"},
            {"artifact_id": "e3", "timestamp": (today - timedelta(days=1)).isoformat(), "source": "sdet"},
        ]
        mock_store.get_artifact.side_effect = lambda aid: {
            "e1": {"error_type": "TimeoutError", "message": "connection.timeout at line 42"},
            "e2": {"error_type": "TimeoutError", "message": "connection.timeout at line 42"},
            "e3": {"error_type": "AssertionError", "message": "assert False"},
        }.get(aid, {})

        analyzer = PatternAnalyzer.__new__(PatternAnalyzer)
        analyzer.store = mock_store

        sigs = analyzer.get_error_signatures("qa")
        assert isinstance(sigs, list)
        assert len(sigs) >= 1
        assert "signature" in sigs[0]
        assert "count" in sigs[0]
        assert sigs[0]["count"] == 2  # TimeoutError seen twice for "qa"
        assert "TimeoutError" in sigs[0]["signature"]


@pytest.mark.unit
class TestApplyPatternGuards:
    """Tests for BaseAgent._apply_pattern_guards() (Phase 3)."""

    def _make_agent(self):
        from agents import QAAssistantAgent
        agent = QAAssistantAgent.__new__(QAAssistantAgent)
        agent.agent_name = "QA_Assistant"
        agent.use_rag = False
        agent.use_data_store = False
        agent.rag = None
        agent.feedback = None
        agent.outcome_tracker = None
        agent._threshold_calibrator = None
        agent._strategy_selector = None
        agent._last_retrieved_doc_ids = []
        agent.execution_history = []
        return agent

    def test_no_change_when_extra_caution_false(self):
        """No modifications when extra_caution is False."""
        agent = self._make_agent()
        context = {"rag_recommendations": [{"confidence": 0.5}]}
        strategy = {"extra_caution": False, "known_failure_types": [], "flakiness_trend": "stable",
                    "recent_failure_rate": 0.0, "confidence_adjustment": 1.0}
        result = agent._apply_pattern_guards(context, strategy)
        assert "pattern_warnings" not in result
        assert "flakiness_warning" not in result
        assert len(result["rag_recommendations"]) == 1  # unchanged

    def test_pattern_warnings_injected_when_extra_caution(self):
        """pattern_warnings added when extra_caution is True and known failures exist."""
        agent = self._make_agent()
        context = {}
        strategy = {"extra_caution": True, "known_failure_types": ["timeout", "assertion"],
                    "flakiness_trend": "stable", "recent_failure_rate": 0.2,
                    "confidence_adjustment": 1.2}
        result = agent._apply_pattern_guards(context, strategy)
        assert "pattern_warnings" in result
        assert result["pattern_warnings"]["extra_validation"] is True
        assert "timeout" in result["pattern_warnings"]["known_failure_types"]

    def test_flakiness_warning_injected_when_accelerating_high_rate(self):
        """flakiness_warning added when trend is accelerating and failure rate > 0.5."""
        agent = self._make_agent()
        context = {}
        strategy = {"extra_caution": True, "known_failure_types": [],
                    "flakiness_trend": "accelerating", "recent_failure_rate": 0.65,
                    "confidence_adjustment": 1.3}
        result = agent._apply_pattern_guards(context, strategy)
        assert "flakiness_warning" in result
        assert result["flakiness_warning"]["trend"] == "accelerating"

    def test_no_flakiness_warning_when_rate_below_threshold(self):
        """flakiness_warning NOT added when failure rate is low even if trend is accelerating."""
        agent = self._make_agent()
        context = {}
        strategy = {"extra_caution": True, "known_failure_types": [],
                    "flakiness_trend": "accelerating", "recent_failure_rate": 0.3,
                    "confidence_adjustment": 1.3}
        result = agent._apply_pattern_guards(context, strategy)
        assert "flakiness_warning" not in result

    def test_low_confidence_recs_filtered_when_adjustment_high(self):
        """Recs with confidence < 0.75 are dropped when confidence_adjustment > 1.2."""
        agent = self._make_agent()
        context = {
            "rag_recommendations": [
                {"confidence": 0.9, "insight": "high"},
                {"confidence": 0.6, "insight": "low"},
                {"confidence": 0.5, "insight": "very low"},
                {"confidence": 0.8, "insight": "also high"},
            ]
        }
        strategy = {"extra_caution": True, "known_failure_types": ["x"],
                    "flakiness_trend": "stable", "recent_failure_rate": 0.4,
                    "confidence_adjustment": 1.3}
        result = agent._apply_pattern_guards(context, strategy)
        remaining = result["rag_recommendations"]
        assert all(r["confidence"] >= 0.75 for r in remaining)
        assert len(remaining) == 2

    def test_recs_unchanged_when_adjustment_low(self):
        """Recs unchanged when confidence_adjustment <= 1.2."""
        agent = self._make_agent()
        context = {
            "rag_recommendations": [
                {"confidence": 0.4, "insight": "low"},
                {"confidence": 0.6, "insight": "med"},
            ]
        }
        strategy = {"extra_caution": True, "known_failure_types": ["x"],
                    "flakiness_trend": "stable", "recent_failure_rate": 0.4,
                    "confidence_adjustment": 1.1}
        result = agent._apply_pattern_guards(context, strategy)
        assert len(result["rag_recommendations"]) == 2  # unchanged


@pytest.mark.unit
class TestSREAgentPatternMemory:
    """SREAgent uses pattern_memory source for known failure types (Phase 3)."""

    def _make_sre_with_patterns(self, known_failure_types):
        from agents import SREAgent
        agent = SREAgent.__new__(SREAgent)
        agent.agent_name = "SRE_Agent"
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
        agent.pipeline.analyze_patterns = Mock(return_value={
            "errors": {"total_failures": 5,
                       "failure_by_type": {t: 3 for t in known_failure_types}},
            "performance": {"avg_latency_ms": 200},
            "flakiness": {
                "flaky_agents": {
                    "SRE_Agent": {"fail_rate": 0.45, "trend": "stable"}
                }
            },
        })
        agent.pipeline.execute_with_validation = Mock(return_value=(True, {"artifact_id": "x"}))
        return agent

    def test_known_rule_uses_pattern_memory_source(self):
        """When error rule is in known_failure_types, fix source is 'pattern_memory'."""
        agent = self._make_sre_with_patterns(["quotes", "semi"])
        result = agent.execute({"errors": [{"rule": "quotes", "message": "use doublequote"}]})
        fixes = result.get("fixes", [])
        assert len(fixes) == 1
        assert fixes[0]["source"] == "pattern_memory"

    def test_unknown_rule_uses_default_fix_path(self):
        """When error rule is NOT in known_failure_types, normal fix path applies."""
        agent = self._make_sre_with_patterns(["timeout"])
        result = agent.execute({"errors": [{"rule": "indent", "message": "wrong indent"}]})
        fixes = result.get("fixes", [])
        assert len(fixes) == 1
        assert fixes[0]["source"] != "pattern_memory"


@pytest.mark.unit
class TestSDETAgentFlakinesThreshold:
    """SDETAgent lowers coverage threshold when flakiness is accelerating (Phase 3)."""

    def _make_sdet_with_flakiness(self, trend):
        from agents import SDETAgent
        agent = SDETAgent.__new__(SDETAgent)
        agent.agent_name = "SDET_Agent"
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
        agent.pipeline.analyze_patterns = Mock(return_value={
            "errors": {"total_failures": 0, "failure_by_type": {}},
            "performance": {"avg_latency_ms": 200},
            "flakiness": {
                "flaky_agents": {
                    "SDET_Agent": {"fail_rate": 0.45, "trend": trend}
                }
            },
        })
        agent.pipeline.execute_with_validation = Mock(return_value=(True, {"artifact_id": "x"}))
        return agent

    def test_accelerating_flakiness_lowers_threshold(self):
        """Coverage at 75% is 'adequate' when flakiness is accelerating (threshold=70)."""
        agent = self._make_sdet_with_flakiness("accelerating")
        result = agent.execute({"coverage_percent": 75, "uncovered_files": []})
        assert result["coverage_status"] == "adequate"
        assert result.get("coverage_threshold_used") == 70

    def test_stable_trend_keeps_standard_threshold(self):
        """Coverage at 75% is 'insufficient' with stable trend (threshold=80)."""
        agent = self._make_sdet_with_flakiness("stable")
        result = agent.execute({"coverage_percent": 75, "uncovered_files": []})
        assert result["coverage_status"] == "insufficient"
        assert result.get("coverage_threshold_used") == 80
