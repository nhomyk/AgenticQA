"""Tests for evaluation harness and reliability scorecard."""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from agenticqa.verification import (
    BenchmarkSuite,
    BenchmarkCase,
    EvalHarness,
    EvalThresholds,
    OutcomeTracker,
    RagasTracker,
)


def _execute(agent_type, input_data):
    return {
        "status": "success",
        "agent": "QA" if agent_type == "qa" else "Other",
    }


def test_eval_harness_passes_all_gates(tmp_path):
    ragas_db = str(tmp_path / "ragas.db")
    outcome_db = str(tmp_path / "outcomes.db")

    ragas_tracker = RagasTracker(db_path=ragas_db)
    outcome_tracker = OutcomeTracker(db_path=outcome_db)

    # Seed outcomes with good calibration
    for i in range(10):
        delegation_id = f"d-{i}"
        outcome_tracker.record_prediction(delegation_id, "QA", "SRE", "deploy", 0.9)
        outcome_tracker.record_outcome(delegation_id, actual_success=True)

    suite = BenchmarkSuite()
    suite.add_case(
        BenchmarkCase(
            id="case-1",
            agent_type="qa",
            description="qa pass",
            input_data={},
            expected_status="success",
            expected_fields={"agent": "QA"},
        )
    )

    # Seed baseline then run a strong score
    ragas_tracker.record_scores("baseline", "sha0", {"faithfulness": 0.90})

    harness = EvalHarness(
        benchmark_suite=suite,
        ragas_tracker=ragas_tracker,
        outcome_tracker=outcome_tracker,
        thresholds=EvalThresholds(
            min_benchmark_pass_rate=0.9,
            min_outcome_accuracy=0.7,
            max_ragas_regressions=0,
        ),
    )

    result = harness.run(
        run_id="run-1",
        execute_fn=_execute,
        ragas_scores={"faithfulness": 0.91},
        commit_sha="abc123",
    )

    assert result.passed is True
    assert result.gates["benchmark_pass_rate"] is True
    assert result.gates["outcome_accuracy"] is True
    assert result.gates["ragas_regression"] is True
    assert result.reliability_scorecard["grade"] in {"A", "A-"}

    outcome_tracker.close()
    ragas_tracker.close()


def test_eval_harness_detects_regression_and_fails(tmp_path):
    ragas_db = str(tmp_path / "ragas.db")
    ragas_tracker = RagasTracker(db_path=ragas_db)

    # Strong baseline then weak current score
    for i in range(5):
        ragas_tracker.record_scores(f"base-{i}", "sha0", {"faithfulness": 0.95})

    suite = BenchmarkSuite()
    suite.add_case(
        BenchmarkCase(
            id="case-1",
            agent_type="qa",
            description="qa pass",
            input_data={},
            expected_status="success",
            expected_fields={"agent": "QA"},
        )
    )

    harness = EvalHarness(
        benchmark_suite=suite,
        ragas_tracker=ragas_tracker,
        outcome_tracker=None,
        thresholds=EvalThresholds(max_ragas_regressions=0),
    )

    result = harness.run(
        run_id="run-2",
        execute_fn=_execute,
        ragas_scores={"faithfulness": 0.70},
        commit_sha="def456",
    )

    assert result.gates["ragas_regression"] is False
    assert result.passed is False
    assert result.ragas_summary["regression_count"] >= 1
    assert result.reliability_scorecard["all_gates_passed"] is False

    ragas_tracker.close()
