"""Unit tests for ModelRegressionTester — @pytest.mark.unit"""
import pytest
from unittest.mock import MagicMock, patch

from agenticqa.regression.model_regression import (
    GoldenSnapshot,
    ModelRegressionTester,
    RegressionResult,
)


def make_tester(store=None) -> ModelRegressionTester:
    return ModelRegressionTester(store=store)


def _snap(text: str = "hello world", agent: str = "qa", model: str = "m1") -> GoldenSnapshot:
    t = ModelRegressionTester()
    return GoldenSnapshot(
        agent_name=agent,
        model_id=model,
        input_hash="abc123",
        output_text=text,
        embedding=t._embed_tfidf(text),
        timestamp="2026-01-01T00:00:00+00:00",
        run_id="test",
    )


# ---------------------------------------------------------------------------
# Hash
# ---------------------------------------------------------------------------

@pytest.mark.unit
class TestHashInput:
    def test_same_input_same_hash(self):
        t = make_tester()
        assert t._hash_input({"a": 1}) == t._hash_input({"a": 1})

    def test_different_input_different_hash(self):
        t = make_tester()
        assert t._hash_input({"a": 1}) != t._hash_input({"a": 2})

    def test_hash_is_16_chars(self):
        t = make_tester()
        assert len(t._hash_input("some input")) == 16


# ---------------------------------------------------------------------------
# Embedding + cosine
# ---------------------------------------------------------------------------

@pytest.mark.unit
class TestEmbedding:
    def test_tfidf_returns_list_of_floats(self):
        t = make_tester()
        emb = t._embed_tfidf("the quick brown fox")
        assert isinstance(emb, list)
        assert all(isinstance(x, float) for x in emb)
        assert len(emb) == 256

    def test_cosine_identical_texts(self):
        t = make_tester()
        v = t._embed_tfidf("hello world")
        assert abs(t._cosine(v, v) - 1.0) < 1e-6

    def test_cosine_orthogonal_vectors(self):
        # Two vectors with no overlap
        a = [1.0] + [0.0] * 255
        b = [0.0] + [1.0] + [0.0] * 254
        t = make_tester()
        assert t._cosine(a, b) == 0.0

    def test_cosine_different_texts_low_similarity(self):
        t = make_tester()
        v1 = t._embed_tfidf("software engineering test coverage")
        v2 = t._embed_tfidf("chocolate cake recipe baking flour")
        assert t._cosine(v1, v2) < 0.5

    def test_embed_fallback_no_fastembed(self):
        """When fastembed is unavailable, _embed() falls back to TF-IDF."""
        t = make_tester()
        with patch.object(t, "_embed_fastembed", side_effect=ImportError("no fastembed")):
            emb = t._embed("test text")
        assert len(emb) == 256


# ---------------------------------------------------------------------------
# capture_golden
# ---------------------------------------------------------------------------

@pytest.mark.unit
class TestCaptureGolden:
    def test_capture_calls_store_store_artifact(self):
        mock_store = MagicMock()
        t = make_tester(store=mock_store)
        snap = t.capture_golden("qa", "model-x", {"input": "data"}, "output text", run_id="r1")
        assert isinstance(snap, GoldenSnapshot)
        assert snap.agent_name == "qa"
        assert snap.model_id == "model-x"
        mock_store.store_artifact.assert_called_once()

    def test_capture_no_store_does_not_raise(self):
        t = make_tester(store=None)
        t._get_store = lambda: None
        snap = t.capture_golden("qa", "model-x", {}, "output", run_id="r1")
        assert snap.output_text == "output"


# ---------------------------------------------------------------------------
# compare
# ---------------------------------------------------------------------------

@pytest.mark.unit
class TestCompare:
    def test_identical_output_score_1(self):
        text = "the system is running correctly"
        snap = _snap(text)
        mock_store = MagicMock()
        mock_store.get_artifact.return_value = {
            "data": {
                "agent_name": snap.agent_name, "model_id": snap.model_id,
                "input_hash": snap.input_hash, "output_text": snap.output_text,
                "embedding": snap.embedding, "timestamp": snap.timestamp, "run_id": snap.run_id,
            }
        }
        t = make_tester(store=mock_store)
        result = t.compare("qa", "m1", "m2", text, {"input": "data"})
        assert abs(result.similarity_score - 1.0) < 0.01
        assert result.regression_detected is False

    def test_different_output_detected(self):
        snap = _snap("software testing coverage quality")
        mock_store = MagicMock()
        mock_store.get_artifact.return_value = {
            "data": {
                "agent_name": snap.agent_name, "model_id": snap.model_id,
                "input_hash": snap.input_hash, "output_text": snap.output_text,
                "embedding": snap.embedding, "timestamp": snap.timestamp, "run_id": snap.run_id,
            }
        }
        t = make_tester(store=mock_store)
        result = t.compare("qa", "m1", "m2",
                           "chocolate cake recipe baking flour sugar eggs",
                           {"input": "data"})
        assert result.similarity_score < 0.5

    def test_no_baseline_returns_none_snapshot(self):
        mock_store = MagicMock()
        mock_store.get_artifact.return_value = None
        t = make_tester(store=mock_store)
        result = t.compare("qa", "m1", "m2", "some output", {"x": 1})
        assert result.baseline_snapshot is None
        assert result.regression_detected is False

    def test_regression_detected_below_threshold(self):
        snap = _snap("aaa bbb ccc ddd eee fff ggg hhh iii jjj")
        mock_store = MagicMock()
        mock_store.get_artifact.return_value = {
            "data": {
                "agent_name": snap.agent_name, "model_id": snap.model_id,
                "input_hash": snap.input_hash, "output_text": snap.output_text,
                "embedding": snap.embedding, "timestamp": snap.timestamp, "run_id": snap.run_id,
            }
        }
        t = make_tester(store=mock_store)
        # Use a very dissimilar candidate
        result = t.compare("qa", "m1", "m2",
                           "zzz yyy xxx www vvv uuu ttt sss rrr qqq ppp",
                           {"input": "data"})
        # If similarity < DEFAULT_THRESHOLD (0.75), regression_detected=True
        assert result.regression_detected == (result.similarity_score < t.DEFAULT_THRESHOLD)

    def test_no_regression_above_threshold(self):
        text = "the agent produced a good response about software quality"
        snap = _snap(text)
        mock_store = MagicMock()
        mock_store.get_artifact.return_value = {
            "data": {
                "agent_name": snap.agent_name, "model_id": snap.model_id,
                "input_hash": snap.input_hash, "output_text": snap.output_text,
                "embedding": snap.embedding, "timestamp": snap.timestamp, "run_id": snap.run_id,
            }
        }
        t = make_tester(store=mock_store)
        result = t.compare("qa", "m1", "m2", text, {"input": "data"})
        assert result.regression_detected is False
        assert result.similarity_score >= t.DEFAULT_THRESHOLD
