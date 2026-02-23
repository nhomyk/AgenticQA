from types import SimpleNamespace

import pytest

import agenticqa.rag.hybrid_retriever as hr


class _RelStore:
    def __init__(self):
        self.metrics = []
        self.executions = []
        self.closed = False

    def store_metric(self, **kwargs):
        self.metrics.append(kwargs)

    def store_execution(self, **kwargs):
        self.executions.append(kwargs)

    def query_metrics(self, agent_type=None, metric_type=None, limit=5):
        if metric_type == "coverage":
            return [SimpleNamespace(metric_value=88.2, run_id="r1", metadata={"source": "cov"})]
        return []

    def get_success_rate(self, agent_type=None, limit=5, action=None):
        return (0.8, 8, 10)

    def close(self):
        self.closed = True


class _Vector:
    def __init__(self, fail_search=False, fail_close=False):
        self.fail_search = fail_search
        self.fail_close = fail_close
        self.added = []
        self.closed = False

    def add_document(self, **kwargs):
        self.added.append(kwargs)
        return "vec-1"

    def search(self, embedding, doc_type=None, k=5, threshold=0.7):
        if self.fail_search:
            raise RuntimeError("vector unavailable")
        doc = SimpleNamespace(content="similar timeout pattern", metadata={"source": "vec"})
        return [(doc, 0.91)]

    def close(self):
        self.closed = True
        if self.fail_close:
            raise RuntimeError("close failed")


class _Embedder:
    def embed(self, text):
        return [0.1, 0.2, 0.3]


def test_store_document_routes_structured_data_and_vector_fallback():
    rel = _RelStore()
    vec = _Vector()
    rag = hr.HybridRAG(vector_store=vec, relational_store=rel, embedder=_Embedder())

    # coverage -> metric
    doc_id = rag.store_document(
        content="coverage report",
        doc_type="coverage_report",
        metadata={"run_id": "r1", "agent_type": "qa", "coverage_pct": 91.5, "timestamp": "2026-01-01"},
    )
    # security -> metric
    rag.store_document(
        content="security findings",
        doc_type="security_audit",
        metadata={"run_id": "r2", "agent_type": "compliance", "vulnerability_count": 4},
    )
    # accessibility -> execution
    rag.store_document(
        content="a11y fix",
        doc_type="accessibility_fix",
        metadata={"run_id": "r3", "success": False},
    )

    assert doc_id == "vec-1"
    assert len(rel.metrics) >= 2
    assert len(rel.executions) == 1
    assert len(vec.added) == 3


def test_store_document_when_vector_add_fails_returns_run_id():
    rel = _RelStore()

    class _FailVector(_Vector):
        def add_document(self, **kwargs):
            raise RuntimeError("down")

    rag = hr.HybridRAG(vector_store=_FailVector(), relational_store=rel, embedder=_Embedder())
    out = rag.store_document("x", "coverage_report", {"run_id": "fallback-id", "coverage_pct": 33})
    assert out == "fallback-id"


def test_search_structured_semantic_and_fallback_paths():
    rel = _RelStore()
    vec = _Vector()
    rag = hr.HybridRAG(vector_store=vec, relational_store=rel, embedder=_Embedder())

    structured = rag.search("what is the success rate", "qa", k=3)
    assert structured and structured[0].source == "relational"

    semantic = rag.search("timeout stack trace in deploy", "qa", k=3)
    assert semantic and any(r.source == "vector" for r in semantic)

    # vector failure should gracefully fall back to relational when no vector results
    rag_fail = hr.HybridRAG(vector_store=_Vector(fail_search=True), relational_store=rel, embedder=_Embedder())
    fallback = rag_fail.search("non-structured semantic query", "qa", k=3)
    assert isinstance(fallback, list)


def test_vector_search_without_embedder_and_context_augmentation():
    rel = _RelStore()
    rag = hr.HybridRAG(vector_store=_Vector(), relational_store=rel, embedder=None)

    assert rag._search_vector("q", "qa", 5, 0.7) == []

    rag2 = hr.HybridRAG(vector_store=_Vector(), relational_store=rel, embedder=_Embedder())
    augmented = rag2.get_agent_context("qa", {"query": "timeout issue"})
    assert "structured_metrics" in augmented
    assert "semantic_patterns" in augmented
    assert augmented["structured_metrics"]["success_rate"] == "80.0%"


def test_postgresql_fallback_close_and_context_manager(monkeypatch):
    rel = _RelStore()

    class _BrokenPostgres:
        def __init__(self):
            raise RuntimeError("pg unavailable")

    monkeypatch.setattr(hr, "PostgreSQLStore", _BrokenPostgres)
    monkeypatch.setattr(hr, "RelationalStore", lambda: rel)

    with hr.HybridRAG(vector_store=_Vector(fail_close=True), relational_store=None, use_postgresql=True) as rag:
        assert rag.relational_store is rel

    assert rel.closed is True
