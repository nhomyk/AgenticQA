"""Evaluation harness and reliability scorecards for AgenticQA."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional

from .benchmark import BenchmarkSuite, BenchmarkResult
from .outcome_tracker import OutcomeTracker
from .ragas_tracker import RagasTracker


@dataclass(frozen=True)
class EvalThresholds:
    """Minimum thresholds required to pass CI quality gates."""

    min_benchmark_pass_rate: float = 0.95
    min_outcome_accuracy: float = 0.70
    max_ragas_regressions: int = 0


@dataclass
class EvalRunResult:
    """Normalized output from a single evaluation harness run."""

    run_id: str
    benchmark_summary: Dict[str, Any]
    outcome_summary: Dict[str, Any]
    ragas_summary: Dict[str, Any]
    gates: Dict[str, bool]
    reliability_scorecard: Dict[str, Any]
    passed: bool


class EvalHarness:
    """Orchestrates benchmark, outcome, and RAGAS checks into one scorecard."""

    def __init__(
        self,
        benchmark_suite: BenchmarkSuite,
        ragas_tracker: Optional[RagasTracker] = None,
        outcome_tracker: Optional[OutcomeTracker] = None,
        thresholds: Optional[EvalThresholds] = None,
    ):
        self.benchmark_suite = benchmark_suite
        self.ragas_tracker = ragas_tracker
        self.outcome_tracker = outcome_tracker
        self.thresholds = thresholds or EvalThresholds()

    def run(
        self,
        run_id: str,
        execute_fn: Callable[[str, Dict[str, Any]], Dict[str, Any]],
        ragas_scores: Optional[Dict[str, float]] = None,
        commit_sha: str = "local",
        branch: str = "local",
    ) -> EvalRunResult:
        benchmark_results: List[BenchmarkResult] = self.benchmark_suite.run(execute_fn)
        benchmark_summary = self.benchmark_suite.summary()

        ragas_summary = self._evaluate_ragas(run_id, ragas_scores or {}, commit_sha, branch)
        outcome_summary = self._evaluate_outcomes()

        gates = {
            "benchmark_pass_rate": benchmark_summary.get("pass_rate", 0.0)
            >= self.thresholds.min_benchmark_pass_rate,
            "outcome_accuracy": outcome_summary.get("accuracy", 0.0)
            >= self.thresholds.min_outcome_accuracy,
            "ragas_regression": ragas_summary.get("regression_count", 0)
            <= self.thresholds.max_ragas_regressions,
        }

        reliability_scorecard = self._build_scorecard(
            benchmark_summary=benchmark_summary,
            outcome_summary=outcome_summary,
            ragas_summary=ragas_summary,
            gates=gates,
        )

        return EvalRunResult(
            run_id=run_id,
            benchmark_summary=benchmark_summary,
            outcome_summary=outcome_summary,
            ragas_summary=ragas_summary,
            gates=gates,
            reliability_scorecard=reliability_scorecard,
            passed=all(gates.values()),
        )

    def _evaluate_ragas(
        self,
        run_id: str,
        ragas_scores: Dict[str, float],
        commit_sha: str,
        branch: str,
    ) -> Dict[str, Any]:
        if not self.ragas_tracker or not ragas_scores:
            return {
                "scores": ragas_scores,
                "regressions": {},
                "regression_count": 0,
                "tracked": False,
            }

        regressions = self.ragas_tracker.check_regression(ragas_scores)
        self.ragas_tracker.record_scores(
            run_id=run_id,
            commit_sha=commit_sha,
            scores=ragas_scores,
            branch=branch,
            metadata={"source": "eval_harness"},
        )
        return {
            "scores": ragas_scores,
            "regressions": regressions,
            "regression_count": len(regressions),
            "tracked": True,
        }

    def _evaluate_outcomes(self) -> Dict[str, Any]:
        if not self.outcome_tracker:
            return {
                "total_predictions": 0,
                "correct_predictions": 0,
                "accuracy": 1.0,
                "mean_absolute_error": 0.0,
                "tracked": False,
            }

        stats = self.outcome_tracker.get_accuracy()
        stats["tracked"] = True
        return stats

    def _build_scorecard(
        self,
        benchmark_summary: Dict[str, Any],
        outcome_summary: Dict[str, Any],
        ragas_summary: Dict[str, Any],
        gates: Dict[str, bool],
    ) -> Dict[str, Any]:
        benchmark_score = benchmark_summary.get("pass_rate", 0.0)
        outcome_score = outcome_summary.get("accuracy", 1.0)

        # Penalize each RAGAS regression by 0.1 (capped at zero)
        ragas_score = max(0.0, 1.0 - (0.1 * ragas_summary.get("regression_count", 0)))

        weighted_score = (
            (benchmark_score * 0.5)
            + (outcome_score * 0.3)
            + (ragas_score * 0.2)
        )

        return {
            "timestamp": datetime.utcnow().isoformat(),
            "components": {
                "benchmark": benchmark_score,
                "outcome_accuracy": outcome_score,
                "ragas_stability": ragas_score,
            },
            "weights": {
                "benchmark": 0.5,
                "outcome_accuracy": 0.3,
                "ragas_stability": 0.2,
            },
            "weighted_score": weighted_score,
            "grade": self._score_to_grade(weighted_score),
            "all_gates_passed": all(gates.values()),
        }

    @staticmethod
    def _score_to_grade(score: float) -> str:
        if score >= 0.95:
            return "A"
        if score >= 0.90:
            return "A-"
        if score >= 0.85:
            return "B+"
        if score >= 0.80:
            return "B"
        if score >= 0.70:
            return "C"
        return "D"
