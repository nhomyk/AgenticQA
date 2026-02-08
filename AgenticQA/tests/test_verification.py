"""
Tests for the pipeline verification module.

Covers all 6 verification components:
1. RagasTracker - score persistence and regression detection
2. OutcomeTracker - prediction calibration and accuracy
3. BenchmarkSuite - golden answer regression testing
4. RelevanceFeedback - document score boosting/penalizing
5. Tracer - end-to-end span recording
6. ABComparison - with-RAG vs without-RAG
"""

import pytest
import os
import tempfile
from unittest.mock import MagicMock

import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from agenticqa.verification import (
    RagasTracker,
    OutcomeTracker,
    BenchmarkSuite, BenchmarkCase, get_default_benchmarks,
    RelevanceFeedback,
    Tracer,
    ABComparison,
)


# ── Fixtures ──────────────────────────────────────────────────────────

@pytest.fixture
def tmp_db(tmp_path):
    """Return a path for a temp SQLite db."""
    return str(tmp_path / "test.db")


# ── 1. RagasTracker ──────────────────────────────────────────────────

class TestRagasTracker:

    def test_record_and_retrieve(self, tmp_db):
        tracker = RagasTracker(db_path=tmp_db)
        tracker.record_scores(
            run_id="run-1", commit_sha="abc123",
            scores={"faithfulness": 0.9, "context_precision": 0.85},
        )
        summary = tracker.get_run_summary("run-1")
        assert summary["faithfulness"] == 0.9
        assert summary["context_precision"] == 0.85
        tracker.close()

    def test_baseline_calculation(self, tmp_db):
        tracker = RagasTracker(db_path=tmp_db)
        for i in range(5):
            tracker.record_scores(
                run_id=f"run-{i}", commit_sha=f"sha{i}",
                scores={"faithfulness": 0.8 + i * 0.02},
            )
        baseline = tracker.get_baseline("faithfulness", window=5)
        assert baseline is not None
        assert 0.84 <= baseline <= 0.88
        tracker.close()

    def test_regression_detection(self, tmp_db):
        tracker = RagasTracker(db_path=tmp_db)
        for i in range(5):
            tracker.record_scores(
                run_id=f"run-{i}", commit_sha=f"sha{i}",
                scores={"faithfulness": 0.9},
            )
        regressions = tracker.check_regression({"faithfulness": 0.80})
        assert "faithfulness" in regressions
        assert regressions["faithfulness"]["delta"] < 0

    def test_no_regression_when_above_baseline(self, tmp_db):
        tracker = RagasTracker(db_path=tmp_db)
        for i in range(5):
            tracker.record_scores(
                run_id=f"run-{i}", commit_sha=f"sha{i}",
                scores={"faithfulness": 0.9},
            )
        regressions = tracker.check_regression({"faithfulness": 0.91})
        assert len(regressions) == 0
        tracker.close()

    def test_trend(self, tmp_db):
        tracker = RagasTracker(db_path=tmp_db)
        for i in range(3):
            tracker.record_scores(
                run_id=f"run-{i}", commit_sha=f"sha{i}",
                scores={"answer_relevancy": 0.7 + i * 0.05},
            )
        trend = tracker.get_trend("answer_relevancy", limit=3)
        assert len(trend) == 3
        # Most recent first
        assert trend[0].score >= trend[-1].score
        tracker.close()


# ── 2. OutcomeTracker ────────────────────────────────────────────────

class TestOutcomeTracker:

    def test_record_prediction_and_outcome(self, tmp_db):
        ot = OutcomeTracker(db_path=tmp_db)
        ot.record_prediction("d-1", "SDET", "SRE", "deploy", 0.85)
        ot.record_outcome("d-1", actual_success=True, duration_ms=250.0)
        acc = ot.get_accuracy()
        assert acc["total_predictions"] == 1
        assert acc["correct_predictions"] == 1
        ot.close()

    def test_calibration_buckets(self, tmp_db):
        ot = OutcomeTracker(db_path=tmp_db)
        # High confidence, success
        for i in range(5):
            ot.record_prediction(f"h-{i}", "A", "B", "task", 0.9)
            ot.record_outcome(f"h-{i}", actual_success=True)
        # Low confidence, failure
        for i in range(5):
            ot.record_prediction(f"l-{i}", "A", "B", "task", 0.2)
            ot.record_outcome(f"l-{i}", actual_success=False)

        buckets = ot.get_calibration(bucket_size=0.5)
        assert len(buckets) >= 1
        ot.close()

    def test_agent_pair_accuracy(self, tmp_db):
        ot = OutcomeTracker(db_path=tmp_db)
        ot.record_prediction("d-1", "QA", "SRE", "deploy", 0.9)
        ot.record_outcome("d-1", True)
        ot.record_prediction("d-2", "QA", "SRE", "deploy", 0.8)
        ot.record_outcome("d-2", False)
        pairs = ot.get_agent_pair_accuracy()
        assert len(pairs) == 1
        assert pairs[0]["total"] == 2
        ot.close()


# ── 3. BenchmarkSuite ───────────────────────────────────────────────

class TestBenchmarkSuite:

    def test_all_pass(self):
        suite = BenchmarkSuite()
        suite.add_case(BenchmarkCase(
            id="t1", agent_type="qa", description="test",
            input_data={}, expected_status="success",
            expected_fields={"agent": "QA"},
        ))

        def mock_execute(agent_type, data):
            return {"status": "success", "agent": "QA"}

        results = suite.run(mock_execute)
        assert results[0].passed
        assert suite.summary()["pass_rate"] == 1.0

    def test_status_mismatch_fails(self):
        suite = BenchmarkSuite()
        suite.add_case(BenchmarkCase(
            id="t1", agent_type="qa", description="test",
            input_data={}, expected_status="success",
            expected_fields={},
        ))

        def mock_execute(agent_type, data):
            return {"status": "error"}

        results = suite.run(mock_execute)
        assert not results[0].passed

    def test_field_mismatch_fails(self):
        suite = BenchmarkSuite()
        suite.add_case(BenchmarkCase(
            id="t1", agent_type="qa", description="test",
            input_data={}, expected_status="success",
            expected_fields={"count": 10},
        ))

        def mock_execute(agent_type, data):
            return {"status": "success", "count": 5}

        results = suite.run(mock_execute)
        assert not results[0].passed
        assert "count" in results[0].errors[0]

    def test_numeric_tolerance(self):
        suite = BenchmarkSuite()
        suite.add_case(BenchmarkCase(
            id="t1", agent_type="perf", description="test",
            input_data={}, expected_status="success",
            expected_fields={"score": 0.95}, tolerance=0.1,
        ))

        def mock_execute(agent_type, data):
            return {"status": "success", "score": 0.90}

        results = suite.run(mock_execute)
        assert results[0].passed  # within tolerance

    def test_default_benchmarks_exist(self):
        suite = get_default_benchmarks()
        assert len(suite.cases) >= 5

    def test_save_and_load(self, tmp_path):
        suite = BenchmarkSuite()
        suite.add_case(BenchmarkCase(
            id="t1", agent_type="qa", description="d",
            input_data={"k": "v"}, expected_status="success",
            expected_fields={"a": 1},
        ))
        path = str(tmp_path / "bench.json")
        suite.save_to_file(path)

        loaded = BenchmarkSuite()
        loaded.load_from_file(path)
        assert len(loaded.cases) == 1
        assert loaded.cases[0].id == "t1"


# ── 4. RelevanceFeedback ────────────────────────────────────────────

class TestRelevanceFeedback:

    def test_boost_on_success(self, tmp_db):
        fb = RelevanceFeedback(db_path=tmp_db)
        fb.record_retrieval("doc-1", "test_result")
        fb.record_feedback("doc-1", success=True)
        score = fb.get_effective_score("doc-1")
        assert score > 1.0
        fb.close()

    def test_penalty_on_failure(self, tmp_db):
        fb = RelevanceFeedback(db_path=tmp_db)
        fb.record_retrieval("doc-1", "test_result")
        fb.record_feedback("doc-1", success=False)
        score = fb.get_effective_score("doc-1")
        assert score < 1.0
        fb.close()

    def test_score_clamped(self, tmp_db):
        fb = RelevanceFeedback(db_path=tmp_db)
        fb.record_retrieval("doc-1", "test_result")
        # Many penalties should not go below 0.5
        for _ in range(50):
            fb.record_feedback("doc-1", success=False)
        score = fb.get_effective_score("doc-1")
        assert score >= 0.5
        fb.close()

    def test_rerank_results(self, tmp_db):
        fb = RelevanceFeedback(db_path=tmp_db)
        fb.record_retrieval("good", "test_result")
        fb.record_retrieval("bad", "test_result")
        for _ in range(5):
            fb.record_feedback("good", success=True)
            fb.record_feedback("bad", success=False)

        results = [
            {"doc_id": "bad", "similarity": 0.95},
            {"doc_id": "good", "similarity": 0.90},
        ]
        reranked = fb.rerank_results(results)
        # "good" should be first despite lower raw similarity
        assert reranked[0]["doc_id"] == "good"
        fb.close()

    def test_document_stats(self, tmp_db):
        fb = RelevanceFeedback(db_path=tmp_db)
        fb.record_retrieval("doc-1", "error")
        fb.record_feedback("doc-1", success=True)
        fb.record_feedback("doc-1", success=False)
        stats = fb.get_document_stats("doc-1")
        assert stats["times_helpful"] == 1
        assert stats["times_unhelpful"] == 1
        fb.close()


# ── 5. Tracer ────────────────────────────────────────────────────────

class TestTracer:

    def test_span_records_duration(self, tmp_db):
        tracer = Tracer(db_path=tmp_db)
        trace_id = tracer.new_trace()
        with tracer.span(trace_id, "agent_execute", agent="qa"):
            pass  # simulate work
        spans = tracer.get_trace(trace_id)
        assert len(spans) == 1
        assert spans[0]["status"] == "success"
        assert spans[0]["duration_ms"] >= 0
        tracer.close()

    def test_nested_spans(self, tmp_db):
        tracer = Tracer(db_path=tmp_db)
        trace_id = tracer.new_trace()
        with tracer.span(trace_id, "agent_execute", agent="qa") as parent:
            with tracer.span(trace_id, "rag_retrieve", parent_span_id=parent):
                pass
            with tracer.span(trace_id, "delegation", parent_span_id=parent):
                pass
        spans = tracer.get_trace(trace_id)
        assert len(spans) == 3
        tracer.close()

    def test_error_span(self, tmp_db):
        tracer = Tracer(db_path=tmp_db)
        trace_id = tracer.new_trace()
        with pytest.raises(ValueError):
            with tracer.span(trace_id, "validation"):
                raise ValueError("bad input")
        spans = tracer.get_trace(trace_id)
        assert spans[0]["status"] == "error"
        tracer.close()

    def test_trace_summary(self, tmp_db):
        tracer = Tracer(db_path=tmp_db)
        trace_id = tracer.new_trace()
        with tracer.span(trace_id, "agent_execute"):
            pass
        with tracer.span(trace_id, "rag_retrieve"):
            pass
        summary = tracer.get_trace_summary(trace_id)
        assert summary["spans"] == 2
        assert "agent_execute" in summary["by_operation"]
        tracer.close()


# ── 6. ABComparison ──────────────────────────────────────────────────

class TestABComparison:

    def test_rag_improvement_detected(self):
        ab = ABComparison()
        ab.add_case("c1", "qa", {"test_results": {}})

        def with_rag(agent, data):
            return {"status": "success", "rag_recommendations": [{"insight": "fix"}]}

        def without_rag(agent, data):
            return {"status": "success"}

        results = ab.run(with_rag, without_rag)
        assert results[0].rag_improved
        assert ab.summary()["improvement_rate"] == 1.0

    def test_equivalent_outcomes(self):
        ab = ABComparison()
        ab.add_case("c1", "qa", {})

        def same_fn(agent, data):
            return {"status": "success"}

        results = ab.run(same_fn, same_fn)
        assert not results[0].rag_improved

    def test_custom_quality_function(self):
        ab = ABComparison()
        ab.add_case("c1", "qa", {})

        def with_rag(agent, data):
            return {"quality": 0.95}

        def without_rag(agent, data):
            return {"quality": 0.70}

        def quality_fn(result):
            return result.get("quality", 0.0)

        results = ab.run(with_rag, without_rag, quality_fn=quality_fn)
        assert results[0].rag_improved
        assert "0.95" in results[0].improvement_details

    def test_summary_latency(self):
        ab = ABComparison()
        ab.add_case("c1", "qa", {})

        def fast_fn(agent, data):
            return {"status": "success"}

        results = ab.run(fast_fn, fast_fn)
        summary = ab.summary()
        assert summary["total_cases"] == 1
        assert "latency_overhead_ms" in summary

    def test_error_handling(self):
        ab = ABComparison()
        ab.add_case("c1", "qa", {})

        def crash_fn(agent, data):
            raise RuntimeError("boom")

        def ok_fn(agent, data):
            return {"status": "success"}

        results = ab.run(ok_fn, crash_fn)
        assert results[0].rag_improved
