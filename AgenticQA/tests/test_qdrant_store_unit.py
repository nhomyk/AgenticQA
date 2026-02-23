import types

import agenticqa.rag.qdrant_store as qs


class _FakePoint:
    def __init__(self, pid, score=0.9, payload=None, vector=None):
        self.id = pid
        self.score = score
        self.payload = payload or {}
        self.vector = vector


class _FakeCount:
    def __init__(self, count):
        self.count = count


class _FakeClient:
    def __init__(self):
        self._exists = False
        self.created = False
        self.upserts = []
        self.deleted = []

    def collection_exists(self, name):
        return self._exists

    def create_collection(self, collection_name, vectors_config):
        self.created = True
        self._exists = True

    def upsert(self, collection_name, points, wait=True):
        self.upserts.append((collection_name, points, wait))

    def search(self, collection_name, query_vector, query_filter=None, limit=5, with_payload=True, with_vectors=True):
        return [
            _FakePoint(
                "1",
                score=0.95,
                payload={"content": "alpha", "doc_type": "test_result", "metadata": {"x": 1}, "timestamp": "2026"},
                vector=[1.0, 0.0],
            ),
            _FakePoint("2", score=0.2, payload={"content": "beta"}, vector=[0.0, 1.0]),
        ]

    def scroll(self, collection_name, scroll_filter=None, limit=10000, with_payload=True, with_vectors=False):
        point = _FakePoint("3", payload={"content": "listed", "doc_type": "error", "metadata": {}, "timestamp": "2026"}, vector=[0.0, 1.0])
        return [point], None

    def delete(self, collection_name, points_selector, wait=True):
        self.deleted.append((collection_name, points_selector, wait))

    def delete_collection(self, collection_name):
        self._exists = False

    def count(self, collection_name, count_filter=None, exact=True):
        return _FakeCount(3)


class _Models:
    class VectorParams:
        def __init__(self, size, distance):
            self.size = size
            self.distance = distance

    class Distance:
        COSINE = "cosine"

    class PointStruct:
        def __init__(self, id, vector, payload):
            self.id = id
            self.vector = vector
            self.payload = payload

    class Filter:
        def __init__(self, must=None):
            self.must = must or []

    class FieldCondition:
        def __init__(self, key, match):
            self.key = key
            self.match = match

    class MatchValue:
        def __init__(self, value):
            self.value = value

    class PointIdsList:
        def __init__(self, points):
            self.points = points


def _patch_qdrant(monkeypatch, fake_client):
    monkeypatch.setattr(qs, "QDRANT_AVAILABLE", True)
    monkeypatch.setattr(qs, "models", _Models)
    monkeypatch.setattr(qs, "QdrantClient", lambda **kwargs: fake_client)


def test_connect_and_add_document(monkeypatch):
    fake = _FakeClient()
    _patch_qdrant(monkeypatch, fake)

    store = qs.QdrantVectorStore(host="localhost", port=6333)
    doc_id = store.add_document("hello", [1.0, 0.0], {"id": "doc-1"}, "test_result")

    assert doc_id == "doc-1"
    assert fake.created is True
    assert len(fake.upserts) == 1


def test_add_document_validates_embedding(monkeypatch):
    fake = _FakeClient()
    _patch_qdrant(monkeypatch, fake)

    store = qs.QdrantVectorStore(url="http://qdrant.local")
    with __import__("pytest").raises(ValueError):
        store.add_document("bad", [], {}, "error")


def test_search_list_delete_and_stats(monkeypatch):
    fake = _FakeClient()
    fake._exists = True
    _patch_qdrant(monkeypatch, fake)

    store = qs.QdrantVectorStore(host="localhost")

    results = store.search([1.0, 0.0], doc_type="test_result", k=5, threshold=0.7)
    assert len(results) == 1
    assert results[0][0].content == "alpha"

    docs = store.get_documents_by_type("error")
    listed = store.list_documents(doc_type="error", include_vectors=True)
    assert len(docs) == 1
    assert len(listed) == 1

    assert store.delete_document("3") is True
    stats = store.stats()
    assert stats["backend"] == "qdrant"


def test_delete_document_failure_and_clear(monkeypatch):
    class _FailClient(_FakeClient):
        def delete(self, collection_name, points_selector, wait=True):
            raise RuntimeError("fail")

    fake = _FailClient()
    fake._exists = True
    _patch_qdrant(monkeypatch, fake)

    store = qs.QdrantVectorStore(host="localhost")
    assert store.delete_document("x") is False

    store.clear()
    assert fake._exists is False

    # context manager coverage
    with store as cm:
        assert cm is store
