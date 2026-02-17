"""
Adaptive Strategy Selection

Selects agent execution strategy based on recent outcomes.
- aggressive: Lower thresholds, more recommendations. High success rate.
- standard: Default behavior. Moderate or unknown success rate.
- conservative: Higher thresholds, fewer recommendations. High failure rate.
"""

from typing import Optional
from dataclasses import dataclass


@dataclass
class ExecutionStrategy:
    name: str
    confidence_multiplier: float
    max_recommendations: int
    require_high_confidence: bool
    description: str


STRATEGIES = {
    "aggressive": ExecutionStrategy(
        name="aggressive",
        confidence_multiplier=0.8,
        max_recommendations=10,
        require_high_confidence=False,
        description="High success rate: accepting broader range of RAG insights",
    ),
    "standard": ExecutionStrategy(
        name="standard",
        confidence_multiplier=1.0,
        max_recommendations=5,
        require_high_confidence=False,
        description="Normal operation: balanced RAG usage",
    ),
    "conservative": ExecutionStrategy(
        name="conservative",
        confidence_multiplier=1.3,
        max_recommendations=2,
        require_high_confidence=True,
        description="Elevated failure rate: using only high-confidence insights",
    ),
}


class StrategySelector:
    """Selects execution strategy based on historical outcomes."""

    AGGRESSIVE_MIN_SUCCESS_RATE = 0.85
    CONSERVATIVE_MAX_SUCCESS_RATE = 0.60
    MIN_SAMPLES = 5

    def __init__(self, relational_store=None, outcome_tracker=None):
        self.relational_store = relational_store
        self.outcome_tracker = outcome_tracker

    def select_strategy(self, agent_type: str) -> ExecutionStrategy:
        """Select strategy based on agent's recent performance."""
        success_rate = self._get_recent_success_rate(agent_type)

        if success_rate is None:
            return STRATEGIES["standard"]

        if success_rate >= self.AGGRESSIVE_MIN_SUCCESS_RATE:
            return STRATEGIES["aggressive"]
        elif success_rate <= self.CONSERVATIVE_MAX_SUCCESS_RATE:
            return STRATEGIES["conservative"]
        else:
            return STRATEGIES["standard"]

    def _get_recent_success_rate(self, agent_type: str) -> Optional[float]:
        """Get recent success rate from available data sources."""
        if self.relational_store:
            try:
                rate, successes, total = self.relational_store.get_success_rate(
                    agent_type, limit=20
                )
                if total >= self.MIN_SAMPLES:
                    return rate
            except Exception:
                pass

        if self.outcome_tracker:
            try:
                accuracy = self.outcome_tracker.get_accuracy()
                if accuracy.get("total_predictions", 0) >= self.MIN_SAMPLES:
                    return accuracy.get("accuracy", None)
            except Exception:
                pass

        return None
