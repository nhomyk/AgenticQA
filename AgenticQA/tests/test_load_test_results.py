"""Unit tests for agenticqa.loadtest.results — @pytest.mark.unit"""
import json
import pytest
from pathlib import Path

from agenticqa.loadtest.results import (
    EndpointStats,
    LoadTestResult,
    LoadTestAnalyzer,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_endpoint(**overrides) -> EndpointStats:
    defaults = dict(
        name="GET /health",
        method="GET",
        num_requests=100,
        num_failures=2,
        avg_response_time_ms=15.0,
        min_response_time_ms=3.0,
        max_response_time_ms=120.0,
        p50_ms=12.0,
        p95_ms=45.0,
        p99_ms=90.0,
        requests_per_sec=10.0,
    )
    defaults.update(overrides)
    return EndpointStats(**defaults)


def _make_result(**overrides) -> LoadTestResult:
    defaults = dict(
        timestamp="2026-03-04T10:00:00Z",
        host="http://localhost:8000",
        users=20,
        duration_s=60,
        spawn_rate=5,
        scenarios=["health", "agents"],
        total_requests=1200,
        total_failures=3,
        overall_rps=20.0,
        avg_response_time_ms=25.0,
        p50_ms=18.0,
        p95_ms=55.0,
        p99_ms=120.0,
        rate_limit_hits=0,
    )
    defaults.update(overrides)
    return LoadTestResult(**defaults)


def _write_history(path: Path, results: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w") as f:
        for r in results:
            f.write(json.dumps(r) + "\n")


# ---------------------------------------------------------------------------
# EndpointStats
# ---------------------------------------------------------------------------

@pytest.mark.unit
class TestEndpointStats:
    def test_to_dict_roundtrip(self):
        ep = _make_endpoint()
        d = ep.to_dict()
        assert d["name"] == "GET /health"
        assert d["method"] == "GET"
        assert d["num_requests"] == 100
        assert d["p95_ms"] == 45.0
        assert d["requests_per_sec"] == 10.0

    def test_failure_rate_calculated(self):
        ep = _make_endpoint(num_requests=200, num_failures=10)
        assert ep.failure_rate == 0.05
        assert ep.to_dict()["failure_rate"] == 0.05

    def test_failure_rate_zero_requests(self):
        ep = _make_endpoint(num_requests=0, num_failures=0)
        assert ep.failure_rate == 0.0

    def test_failure_rate_zero_failures(self):
        ep = _make_endpoint(num_requests=500, num_failures=0)
        assert ep.failure_rate == 0.0


# ---------------------------------------------------------------------------
# LoadTestResult
# ---------------------------------------------------------------------------

@pytest.mark.unit
class TestLoadTestResult:
    def test_to_dict_complete(self):
        result = _make_result()
        d = result.to_dict()
        assert d["host"] == "http://localhost:8000"
        assert d["users"] == 20
        assert d["duration_s"] == 60
        assert d["total_requests"] == 1200
        assert d["p95_ms"] == 55.0
        assert d["endpoints"] == []

    def test_to_dict_with_endpoints(self):
        ep = _make_endpoint()
        result = _make_result(endpoints=[ep])
        d = result.to_dict()
        assert len(d["endpoints"]) == 1
        assert d["endpoints"][0]["name"] == "GET /health"

    def test_overall_failure_rate(self):
        result = _make_result(total_requests=1000, total_failures=50)
        assert result.overall_failure_rate == 0.05

    def test_overall_failure_rate_zero_requests(self):
        result = _make_result(total_requests=0, total_failures=0)
        assert result.overall_failure_rate == 0.0

    def test_scenarios_list(self):
        result = _make_result(scenarios=["health", "security", "mixed"])
        assert result.to_dict()["scenarios"] == ["health", "security", "mixed"]

    def test_rate_limit_hits_tracked(self):
        result = _make_result(rate_limit_hits=15)
        assert result.to_dict()["rate_limit_hits"] == 15

    def test_json_serializable(self):
        ep = _make_endpoint()
        result = _make_result(endpoints=[ep])
        serialized = json.dumps(result.to_dict())
        parsed = json.loads(serialized)
        assert parsed["total_requests"] == 1200


# ---------------------------------------------------------------------------
# LoadTestAnalyzer — record + history
# ---------------------------------------------------------------------------

@pytest.mark.unit
class TestLoadTestAnalyzerRecordHistory:
    def test_record_creates_jsonl(self, tmp_path):
        path = tmp_path / "history.jsonl"
        analyzer = LoadTestAnalyzer(history_file=str(path))
        result = _make_result()
        analyzer.record(result)
        assert path.exists()
        lines = path.read_text().strip().split("\n")
        assert len(lines) == 1
        parsed = json.loads(lines[0])
        assert parsed["host"] == "http://localhost:8000"

    def test_record_appends_to_existing(self, tmp_path):
        path = tmp_path / "history.jsonl"
        analyzer = LoadTestAnalyzer(history_file=str(path))
        analyzer.record(_make_result(users=10))
        analyzer.record(_make_result(users=20))
        analyzer.record(_make_result(users=50))
        lines = path.read_text().strip().split("\n")
        assert len(lines) == 3

    def test_history_empty_file(self, tmp_path):
        path = tmp_path / "history.jsonl"
        path.write_text("")
        analyzer = LoadTestAnalyzer(history_file=str(path))
        assert analyzer.history() == []

    def test_history_nonexistent_file(self, tmp_path):
        path = tmp_path / "does_not_exist.jsonl"
        analyzer = LoadTestAnalyzer(history_file=str(path))
        assert analyzer.history() == []

    def test_history_returns_last_n(self, tmp_path):
        path = tmp_path / "history.jsonl"
        records = [_make_result(users=i).to_dict() for i in range(1, 11)]
        _write_history(path, records)
        analyzer = LoadTestAnalyzer(history_file=str(path))
        last_3 = analyzer.history(limit=3)
        assert len(last_3) == 3
        assert last_3[0]["users"] == 8

    def test_history_handles_corrupt_lines(self, tmp_path):
        path = tmp_path / "history.jsonl"
        path.write_text(
            json.dumps(_make_result(users=5).to_dict()) + "\n"
            + "NOT VALID JSON\n"
            + json.dumps(_make_result(users=10).to_dict()) + "\n"
        )
        analyzer = LoadTestAnalyzer(history_file=str(path))
        records = analyzer.history()
        assert len(records) == 2
        assert records[0]["users"] == 5
        assert records[1]["users"] == 10


# ---------------------------------------------------------------------------
# LoadTestAnalyzer — trend detection
# ---------------------------------------------------------------------------

@pytest.mark.unit
class TestLoadTestAnalyzerTrend:
    def test_trend_insufficient_data(self, tmp_path):
        path = tmp_path / "history.jsonl"
        _write_history(path, [_make_result(p95_ms=50.0).to_dict()])
        analyzer = LoadTestAnalyzer(history_file=str(path))
        trend = analyzer.trend()
        assert trend["direction"] == "insufficient_data"
        assert trend["records"] == 1

    def test_trend_stable(self, tmp_path):
        path = tmp_path / "history.jsonl"
        records = [_make_result(p95_ms=50.0).to_dict() for _ in range(6)]
        _write_history(path, records)
        analyzer = LoadTestAnalyzer(history_file=str(path))
        trend = analyzer.trend(window=3)
        assert trend["direction"] == "stable"

    def test_trend_degrading(self, tmp_path):
        path = tmp_path / "history.jsonl"
        # Early runs: low p95, recent runs: high p95
        early = [_make_result(p95_ms=30.0).to_dict() for _ in range(5)]
        recent = [_make_result(p95_ms=100.0).to_dict() for _ in range(5)]
        _write_history(path, early + recent)
        analyzer = LoadTestAnalyzer(history_file=str(path))
        trend = analyzer.trend(window=5)
        assert trend["direction"] == "degrading"
        assert trend["delta_p95_ms"] > 0

    def test_trend_improving(self, tmp_path):
        path = tmp_path / "history.jsonl"
        early = [_make_result(p95_ms=100.0).to_dict() for _ in range(5)]
        recent = [_make_result(p95_ms=30.0).to_dict() for _ in range(5)]
        _write_history(path, early + recent)
        analyzer = LoadTestAnalyzer(history_file=str(path))
        trend = analyzer.trend(window=5)
        assert trend["direction"] == "improving"
        assert trend["delta_p95_ms"] < 0

    def test_trend_includes_rps(self, tmp_path):
        path = tmp_path / "history.jsonl"
        records = [_make_result(p95_ms=50.0, overall_rps=20.0).to_dict() for _ in range(4)]
        _write_history(path, records)
        analyzer = LoadTestAnalyzer(history_file=str(path))
        trend = analyzer.trend()
        assert "early_avg_rps" in trend
        assert "recent_avg_rps" in trend


# ---------------------------------------------------------------------------
# LoadTestAnalyzer — regression detection
# ---------------------------------------------------------------------------

@pytest.mark.unit
class TestLoadTestAnalyzerRegression:
    def test_no_baseline(self, tmp_path):
        path = tmp_path / "history.jsonl"
        analyzer = LoadTestAnalyzer(history_file=str(path))
        result = _make_result(p95_ms=100.0)
        check = analyzer.detect_regression(result)
        assert check["regression"] is False
        assert check["reason"] == "no_baseline"

    def test_within_threshold(self, tmp_path):
        path = tmp_path / "history.jsonl"
        # Baseline: avg p95 = 50ms, current = 80ms (< 50 * 2 = 100ms)
        records = [_make_result(p95_ms=50.0).to_dict() for _ in range(5)]
        _write_history(path, records)
        analyzer = LoadTestAnalyzer(history_file=str(path))
        result = _make_result(p95_ms=80.0)
        check = analyzer.detect_regression(result)
        assert check["regression"] is False
        assert check["reason"] == "within_threshold"

    def test_exceeds_threshold(self, tmp_path):
        path = tmp_path / "history.jsonl"
        # Baseline: avg p95 = 50ms, current = 150ms (> 50 * 2 = 100ms)
        records = [_make_result(p95_ms=50.0).to_dict() for _ in range(5)]
        _write_history(path, records)
        analyzer = LoadTestAnalyzer(history_file=str(path))
        result = _make_result(p95_ms=150.0)
        check = analyzer.detect_regression(result)
        assert check["regression"] is True
        assert check["reason"] == "p95_exceeds_2x_baseline"
        assert check["baseline_p95_ms"] == 50.0

    def test_custom_threshold(self, tmp_path):
        path = tmp_path / "history.jsonl"
        # Baseline: avg p95 = 50ms, current = 80ms, threshold 1.5× → 75ms
        records = [_make_result(p95_ms=50.0).to_dict() for _ in range(5)]
        _write_history(path, records)
        analyzer = LoadTestAnalyzer(history_file=str(path))
        result = _make_result(p95_ms=80.0)
        check = analyzer.detect_regression(result, threshold=1.5)
        assert check["regression"] is True
        assert check["threshold_multiplier"] == 1.5

    def test_exactly_at_threshold(self, tmp_path):
        path = tmp_path / "history.jsonl"
        # Baseline: avg p95 = 50ms, current = 100ms (== 50 * 2, not > 2x)
        records = [_make_result(p95_ms=50.0).to_dict() for _ in range(5)]
        _write_history(path, records)
        analyzer = LoadTestAnalyzer(history_file=str(path))
        result = _make_result(p95_ms=100.0)
        check = analyzer.detect_regression(result)
        assert check["regression"] is False
