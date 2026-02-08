"""
A/B RAG Comparison

Runs the same inputs through agents with and without RAG augmentation,
then compares outcomes to quantify RAG's measurable impact.
"""

import time
import json
from typing import Dict, List, Any, Optional, Callable
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path


@dataclass
class ABResult:
    """Result of a single A/B comparison."""
    case_id: str
    agent_type: str
    with_rag: Dict[str, Any]
    without_rag: Dict[str, Any]
    rag_duration_ms: float
    no_rag_duration_ms: float
    rag_improved: bool
    improvement_details: str


class ABComparison:
    """
    Compares agent execution with and without RAG augmentation.

    Usage:
        ab = ABComparison()
        ab.add_case("test-1", "qa", {"test_results": {...}})
        results = ab.run(agent_with_rag_fn, agent_without_rag_fn)
        print(ab.summary())
    """

    def __init__(self):
        self.cases: List[Dict[str, Any]] = []
        self.results: List[ABResult] = []

    def add_case(self, case_id: str, agent_type: str, input_data: Dict[str, Any]):
        self.cases.append({
            "case_id": case_id,
            "agent_type": agent_type,
            "input_data": input_data,
        })

    def run(
        self,
        with_rag_fn: Callable[[str, Dict], Dict],
        without_rag_fn: Callable[[str, Dict], Dict],
        quality_fn: Optional[Callable[[Dict], float]] = None,
    ) -> List[ABResult]:
        """
        Run all cases through both code paths.

        Args:
            with_rag_fn: Function(agent_type, input) -> result (RAG enabled)
            without_rag_fn: Function(agent_type, input) -> result (RAG disabled)
            quality_fn: Optional function to score result quality (0.0-1.0)
        """
        self.results = []
        for case in self.cases:
            # Run with RAG
            start = time.time()
            try:
                rag_result = with_rag_fn(case["agent_type"], case["input_data"])
            except Exception as e:
                rag_result = {"status": "error", "error": str(e)}
            rag_ms = (time.time() - start) * 1000

            # Run without RAG
            start = time.time()
            try:
                no_rag_result = without_rag_fn(case["agent_type"], case["input_data"])
            except Exception as e:
                no_rag_result = {"status": "error", "error": str(e)}
            no_rag_ms = (time.time() - start) * 1000

            # Compare
            improved, details = self._compare_results(
                rag_result, no_rag_result, quality_fn
            )

            self.results.append(ABResult(
                case_id=case["case_id"],
                agent_type=case["agent_type"],
                with_rag=rag_result,
                without_rag=no_rag_result,
                rag_duration_ms=rag_ms,
                no_rag_duration_ms=no_rag_ms,
                rag_improved=improved,
                improvement_details=details,
            ))

        return self.results

    def _compare_results(
        self,
        rag_result: Dict,
        no_rag_result: Dict,
        quality_fn: Optional[Callable] = None,
    ) -> tuple:
        """Compare two results and determine if RAG improved the outcome."""
        # If custom quality function provided, use it
        if quality_fn:
            rag_score = quality_fn(rag_result)
            no_rag_score = quality_fn(no_rag_result)
            improved = rag_score > no_rag_score
            delta = rag_score - no_rag_score
            return improved, f"quality delta: {delta:+.3f} (rag={rag_score:.3f}, no_rag={no_rag_score:.3f})"

        # Default comparison: more insights = better
        rag_insights = len(rag_result.get("rag_recommendations", []))
        rag_status = rag_result.get("status", "error")
        no_rag_status = no_rag_result.get("status", "error")

        if rag_status == "success" and no_rag_status != "success":
            return True, "RAG enabled success where baseline failed"
        if rag_insights > 0:
            return True, f"RAG provided {rag_insights} additional insights"
        if rag_status == no_rag_status:
            return False, "equivalent outcomes"
        return False, f"rag={rag_status}, no_rag={no_rag_status}"

    def summary(self) -> Dict[str, Any]:
        """Summarize A/B comparison results."""
        total = len(self.results)
        improved = sum(1 for r in self.results if r.rag_improved)
        avg_rag_ms = sum(r.rag_duration_ms for r in self.results) / total if total else 0
        avg_no_rag_ms = sum(r.no_rag_duration_ms for r in self.results) / total if total else 0

        return {
            "total_cases": total,
            "rag_improved": improved,
            "rag_neutral_or_worse": total - improved,
            "improvement_rate": improved / total if total > 0 else 0.0,
            "avg_rag_latency_ms": round(avg_rag_ms, 1),
            "avg_no_rag_latency_ms": round(avg_no_rag_ms, 1),
            "latency_overhead_ms": round(avg_rag_ms - avg_no_rag_ms, 1),
            "timestamp": datetime.utcnow().isoformat(),
            "details": [
                {
                    "case_id": r.case_id,
                    "improved": r.rag_improved,
                    "details": r.improvement_details,
                }
                for r in self.results
            ],
        }
