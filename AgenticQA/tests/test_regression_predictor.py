"""Unit tests for RegressionPredictor — @pytest.mark.unit"""
import pytest
from pathlib import Path

from agenticqa.testing.regression_predictor import (
    RegressionPredictor,
    RegressionPredictionResult,
    TestPrediction,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def pred() -> RegressionPredictor:
    return RegressionPredictor()


def write(path: Path, content: str = "pass\n") -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return path


# ---------------------------------------------------------------------------
# _compute_relevance unit tests
# ---------------------------------------------------------------------------

@pytest.mark.unit
class TestComputeRelevance:

    def test_exact_match_scores_1(self):
        score, reason = pred()._compute_relevance("tests/test_auth.py", ["auth"])
        assert score == 1.0
        assert "Exact" in reason

    def test_partial_match_scores_075(self):
        score, reason = pred()._compute_relevance("tests/test_auth_service.py", ["auth"])
        assert score == 0.75
        assert "Partial" in reason

    def test_no_match_scores_01(self):
        score, reason = pred()._compute_relevance("tests/test_unrelated.py", ["billing"])
        assert score == 0.1
        assert "No direct" in reason

    def test_integration_test_scores_03(self):
        score, reason = pred()._compute_relevance("tests/test_integration_api.py", ["billing"])
        # integration test gets at least 0.3 even with no match
        assert score >= 0.3
        assert "Integration" in reason or "Exact" in reason or "Partial" in reason

    def test_exact_match_wins_over_partial(self):
        score, _ = pred()._compute_relevance("tests/test_login.py", ["login", "auth"])
        assert score == 1.0

    def test_reason_string_populated(self):
        _, reason = pred()._compute_relevance("tests/test_auth.py", ["auth"])
        assert isinstance(reason, str)
        assert len(reason) > 0


# ---------------------------------------------------------------------------
# predict() tests
# ---------------------------------------------------------------------------

@pytest.mark.unit
class TestPredict:

    def test_empty_changed_files_returns_empty(self, tmp_path):
        write(tmp_path / "tests" / "test_auth.py")
        result = pred().predict(str(tmp_path), [])
        assert result.test_predictions == []
        assert result.priority_tests == []
        assert result.skip_candidates == []

    def test_exact_match_in_priority_tests(self, tmp_path):
        write(tmp_path / "src" / "auth.py")
        write(tmp_path / "tests" / "test_auth.py")
        result = pred().predict(str(tmp_path), ["src/auth.py"])
        assert any("test_auth.py" in t for t in result.priority_tests)

    def test_exact_match_not_in_skip_candidates(self, tmp_path):
        write(tmp_path / "src" / "auth.py")
        write(tmp_path / "tests" / "test_auth.py")
        result = pred().predict(str(tmp_path), ["src/auth.py"])
        assert not any("test_auth.py" in t for t in result.skip_candidates)

    def test_likely_fail_on_exact_match(self, tmp_path):
        write(tmp_path / "src" / "auth.py")
        write(tmp_path / "tests" / "test_auth.py")
        result = pred().predict(str(tmp_path), ["src/auth.py"])
        auth_preds = [p for p in result.test_predictions if "test_auth.py" in p.test_file]
        assert len(auth_preds) > 0
        assert auth_preds[0].predicted_outcome == "LIKELY_FAIL"

    def test_probably_pass_on_no_match(self, tmp_path):
        write(tmp_path / "tests" / "test_billing.py")
        result = pred().predict(str(tmp_path), ["src/auth.py"])
        billing_preds = [p for p in result.test_predictions if "test_billing.py" in p.test_file]
        assert len(billing_preds) > 0
        assert billing_preds[0].predicted_outcome == "PROBABLY_PASS"

    def test_sorted_by_relevance_desc(self, tmp_path):
        write(tmp_path / "tests" / "test_auth.py")
        write(tmp_path / "tests" / "test_other.py")
        result = pred().predict(str(tmp_path), ["src/auth.py"])
        scores = [p.relevance_score for p in result.test_predictions]
        assert scores == sorted(scores, reverse=True)

    def test_to_dict_fields(self, tmp_path):
        write(tmp_path / "tests" / "test_auth.py")
        result = pred().predict(str(tmp_path), ["src/auth.py"])
        d = result.to_dict()
        assert "changed_files" in d
        assert "test_predictions" in d
        assert "priority_tests" in d
        assert "skip_candidates" in d
        assert "coverage_estimate" in d

    def test_prediction_to_dict_fields(self, tmp_path):
        write(tmp_path / "tests" / "test_auth.py")
        result = pred().predict(str(tmp_path), ["src/auth.py"])
        assert len(result.test_predictions) > 0
        d = result.test_predictions[0].to_dict()
        assert "test_file" in d
        assert "relevance_score" in d
        assert "reason" in d
        assert "predicted_outcome" in d

    def test_coverage_estimate_in_range(self, tmp_path):
        write(tmp_path / "tests" / "test_auth.py")
        result = pred().predict(str(tmp_path), ["src/auth.py"])
        assert 0.0 <= result.coverage_estimate <= 1.0

    def test_priority_tests_subset_of_all_tests(self, tmp_path):
        write(tmp_path / "tests" / "test_auth.py")
        write(tmp_path / "tests" / "test_other.py")
        result = pred().predict(str(tmp_path), ["src/auth.py"])
        all_test_files = {p.test_file for p in result.test_predictions}
        for t in result.priority_tests:
            assert t in all_test_files

    def test_skip_non_overlapping_with_priority(self, tmp_path):
        write(tmp_path / "tests" / "test_auth.py")
        write(tmp_path / "tests" / "test_zzz_unrelated.py")
        result = pred().predict(str(tmp_path), ["src/auth.py"])
        priority_set = set(result.priority_tests)
        skip_set = set(result.skip_candidates)
        assert priority_set.isdisjoint(skip_set)

    def test_reason_string_in_prediction(self, tmp_path):
        write(tmp_path / "tests" / "test_auth.py")
        result = pred().predict(str(tmp_path), ["src/auth.py"])
        assert len(result.test_predictions) > 0
        assert isinstance(result.test_predictions[0].reason, str)

    def test_test_predictions_length_equals_total_tests(self, tmp_path):
        write(tmp_path / "tests" / "test_a.py")
        write(tmp_path / "tests" / "test_b.py")
        write(tmp_path / "tests" / "test_c.py")
        result = pred().predict(str(tmp_path), ["src/x.py"])
        assert len(result.test_predictions) == 3

    def test_multiple_changed_files(self, tmp_path):
        write(tmp_path / "tests" / "test_auth.py")
        write(tmp_path / "tests" / "test_billing.py")
        result = pred().predict(str(tmp_path), ["src/auth.py", "src/billing.py"])
        # Both should appear in priority
        files_in_priority = " ".join(result.priority_tests)
        assert "test_auth.py" in files_in_priority or "test_billing.py" in files_in_priority

    def test_integration_test_score_at_least_03(self, tmp_path):
        write(tmp_path / "tests" / "test_integration_api.py")
        result = pred().predict(str(tmp_path), ["src/billing.py"])
        integration_preds = [
            p for p in result.test_predictions
            if "test_integration" in p.test_file
        ]
        if integration_preds:
            assert integration_preds[0].relevance_score >= 0.3
