"""
Tests for adaptive strategy selection (Phase 5).
"""

import pytest
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from agenticqa.verification.strategy_selector import StrategySelector, STRATEGIES, ExecutionStrategy
from agenticqa.verification.outcome_tracker import OutcomeTracker
from agenticqa.rag.relational_store import RelationalStore


@pytest.fixture
def tmp_db(tmp_path):
    return str(tmp_path / "test.db")


@pytest.mark.unit
class TestStrategySelector:

    def test_standard_with_no_data(self):
        selector = StrategySelector()
        strategy = selector.select_strategy("qa")
        assert strategy.name == "standard"

    def test_standard_with_insufficient_data(self, tmp_db):
        store = RelationalStore(db_path=tmp_db)
        # Only 3 samples — below MIN_SAMPLES (5)
        for i in range(3):
            store.store_execution(f"run-{i}", "qa", "test", "passed", True)
        selector = StrategySelector(relational_store=store)
        strategy = selector.select_strategy("qa")
        assert strategy.name == "standard"

    def test_aggressive_with_high_success(self, tmp_db):
        store = RelationalStore(db_path=tmp_db)
        for i in range(20):
            store.store_execution(f"run-{i}", "qa", "test", "passed", True)
        selector = StrategySelector(relational_store=store)
        strategy = selector.select_strategy("qa")
        assert strategy.name == "aggressive"

    def test_conservative_with_low_success(self, tmp_db):
        store = RelationalStore(db_path=tmp_db)
        for i in range(20):
            store.store_execution(
                f"run-{i}", "qa", "test",
                "passed" if i < 8 else "failed",
                i < 8,
            )
        selector = StrategySelector(relational_store=store)
        strategy = selector.select_strategy("qa")
        assert strategy.name == "conservative"

    def test_standard_with_moderate_success(self, tmp_db):
        store = RelationalStore(db_path=tmp_db)
        for i in range(20):
            store.store_execution(
                f"run-{i}", "qa", "test",
                "passed" if i < 15 else "failed",
                i < 15,
            )
        selector = StrategySelector(relational_store=store)
        strategy = selector.select_strategy("qa")
        assert strategy.name == "standard"

    def test_falls_back_to_outcome_tracker(self, tmp_db):
        """Uses OutcomeTracker when RelationalStore has no data."""
        ot = OutcomeTracker(db_path=tmp_db)
        for i in range(10):
            ot.record_prediction(f"d-{i}", "A", "B", "task", 0.8)
            ot.record_outcome(f"d-{i}", actual_success=True)

        selector = StrategySelector(outcome_tracker=ot)
        strategy = selector.select_strategy("qa")
        assert strategy.name == "aggressive"
        ot.close()

    def test_confidence_multiplier_values(self):
        assert STRATEGIES["aggressive"].confidence_multiplier < 1.0
        assert STRATEGIES["standard"].confidence_multiplier == 1.0
        assert STRATEGIES["conservative"].confidence_multiplier > 1.0

    def test_max_recommendations_capped(self):
        assert STRATEGIES["conservative"].max_recommendations < STRATEGIES["standard"].max_recommendations
        assert STRATEGIES["standard"].max_recommendations < STRATEGIES["aggressive"].max_recommendations

    def test_conservative_requires_high_confidence(self):
        assert STRATEGIES["conservative"].require_high_confidence is True
        assert STRATEGIES["standard"].require_high_confidence is False
        assert STRATEGIES["aggressive"].require_high_confidence is False
