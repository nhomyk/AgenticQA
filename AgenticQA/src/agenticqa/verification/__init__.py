"""
Pipeline Verification Module

Provides tools to prove the AgenticQA pipeline works as intended:
- RagasTracker: Persist RAGAS scores and detect quality regressions
- OutcomeTracker: Compare predicted confidence vs actual delegation outcomes
- BenchmarkSuite: Fixed test cases with golden answers for regression detection
- RelevanceFeedback: Boost/penalize retrieved documents based on outcomes
- Tracer: End-to-end trace IDs across the full pipeline
- ABComparison: A/B test agents with vs without RAG augmentation
"""

from .ragas_tracker import RagasTracker, RagasScore
from .outcome_tracker import OutcomeTracker, DelegationOutcome
from .benchmark import BenchmarkSuite, BenchmarkCase, BenchmarkResult, get_default_benchmarks
from .feedback_loop import RelevanceFeedback
from .tracing import Tracer
from .ab_comparison import ABComparison, ABResult

__all__ = [
    "RagasTracker", "RagasScore",
    "OutcomeTracker", "DelegationOutcome",
    "BenchmarkSuite", "BenchmarkCase", "BenchmarkResult", "get_default_benchmarks",
    "RelevanceFeedback",
    "Tracer",
    "ABComparison", "ABResult",
]
