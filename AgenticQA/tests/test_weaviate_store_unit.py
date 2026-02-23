from types import SimpleNamespace

import pytest

import agenticqa.rag.weaviate_store as ws


class _FakeObject:
    def __init__(self, uuid="u1", props=None, distance=0.1, vector=None):
        self.uuid = uuid
        self.properties = props or {}
        self.metadata = SimpleNamespace(distance=distance)
        self.vector = vector


class _FakeResults:
    def __init__(self, objects=None, count=0):
        self.objects = objects or []
        self.count = count


class _FakeCollection:
    def __init__(self):
        self.inserted = []
        self.deleted = []
        self._fetch_return = _FakeResults()
        self.data = SimpleNamespace(insert=self._insert, delete_by_id=self._delete)
        self.query = SimpleNamespace(
            near_vector=self._near_vector,
            fetch_objects=self._fetch_objects,
        )

    def _insert(self, properties, vector):
        self.inserted.append((properties, vector))
        return "new-id"

    def _delete(self, doc_id):
        self.deleted.append(doc_id)

    def _near_vector(self, **kwargs):
        return _FakeResults(
            objects=[
                _FakeObject(
                    uuid="a",
                    props={"content": "c1", "doc_type": "error", "metadata": "{}", "timestamp": "t1"},
                    distance=0.1,
                    vector={"default": [1.0, 0.0]},
                ),
                _FakeObject(
                    uuid="b",
                    props={"content": "c2", "doc_type": "error", "metadata": "{}", "timestamp": "t2"},
                    distance=1.9,
                    vector={"default": [0.0, 1.0]},
                ),
            ]
        )

    def _fetch_objects(self, **kwargs):
        return self._fetch_return


class _FakeCollections:
    def __init__(self, exists=False):
        self._exists = exists
        self.created = False
        self.collection = _FakeCollection()

    def exists(self, name):
        return self._exists

    def create(self, **kwargs):
        self.created = True
        self._exists = True

    def get(self, name):
        return self.collection


class _FakeClient:
    def __init__(self, exists=False):
        self.collections = _FakeCollections(exists=exists)
        self.closed = False

    def close(self):
        self.closed = True


class _FakeFilterBuilder:
    @staticmethod
    def by_property(name):
        return SimpleNamespace(equal=lambda val: (name, val))


class _FakeMetaQuery:
    def __init__(self, distance=False):
        self.distance = distance


class _FakeConfigure:
    class Vectorizer:
        @staticmethod
        def text2vec_openai(model="text-embedding-3-small"):
            return ("openai", model)

        @staticmethod
        def none():
            return ("none",)


def _patch_weaviate(monkeypatch, client):
    fake_weaviate = SimpleNamespace(
        connect_to_local=lambda host, port, skip_init_checks=False: client,
        connect_to_weaviate_cloud=lambda cluster_url, auth_credentials: client,
        auth=SimpleNamespace(AuthApiKey=lambda key: ("api", key)),
        classes=SimpleNamespace(
            query=SimpleNamespace(Filter=_FakeFilterBuilder),
            config=SimpleNamespace(Configure=_FakeConfigure),
        ),
    )

    monkeypatch.setattr(ws, "WEAVIATE_AVAILABLE", True)
    monkeypatch.setattr(ws, "weaviate", fake_weaviate)
    monkeypatch.setattr(ws, "DataType", SimpleNamespace(TEXT="text"))
    monkeypatch.setattr(ws, "MetadataQuery", _FakeMetaQuery)


def test_init_local_and_add_search_stats(monkeypatch):
    client = _FakeClient(exists=False)
    _patch_weaviate(monkeypatch, client)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    store = ws.WeaviateVectorStore(host="localhost", port=8080, collection_name="AgenticQADocuments")

    # collection creation path
    assert client.collections.created is True

    doc_id = store.add_document("hello", [1.0, 0.0], {"timestamp": "2026"}, "error")
    assert doc_id == "new-id"

    results = store.search([1.0, 0.0], doc_type="error", k=5, threshold=0.7)
    assert len(results) == 1
    assert results[0][0].id == "a"

    # stats path
    coll = client.collections.collection
    coll._fetch_return = _FakeResults(objects=[], count=2)
    stats = store.stats()
    assert stats["backend"] == "weaviate"


def test_get_list_delete_clear_and_context_manager(monkeypatch):
    client = _FakeClient(exists=True)
    _patch_weaviate(monkeypatch, client)

    store = ws.WeaviateVectorStore(host="localhost", port=8080)
    coll = client.collections.collection

    coll._fetch_return = _FakeResults(
        objects=[
            _FakeObject(uuid="z1", props={"content": "x", "doc_type": "error", "metadata": "{}", "timestamp": "t"}, vector={"default": [1.0]}),
        ],
        count=1,
    )

    by_type = store.get_documents_by_type("error")
    listed = store.list_documents(doc_type="error", include_vectors=True, limit=10)
    assert len(by_type) == 1
    assert len(listed) == 1

    assert store.delete_document("z1") is True
    store.clear()

    with store as cm:
        assert cm is store
    assert client.closed is True


def test_cloud_mode_and_validation_paths(monkeypatch):
    client = _FakeClient(exists=True)
    _patch_weaviate(monkeypatch, client)

    monkeypatch.setenv("OPENAI_API_KEY", "key")
    store = ws.WeaviateVectorStore(host="cluster.weaviate.network", port=None, api_key="wk")
    assert store._has_openai() is True


def test_error_paths(monkeypatch):
    # connect failure path
    monkeypatch.setattr(ws, "WEAVIATE_AVAILABLE", True)

    def _boom_local(**kwargs):
        raise RuntimeError("conn")

    fake_weaviate = SimpleNamespace(
        connect_to_local=_boom_local,
        connect_to_weaviate_cloud=lambda **kwargs: (_ for _ in ()).throw(RuntimeError("conn")),
        auth=SimpleNamespace(AuthApiKey=lambda key: ("api", key)),
        classes=SimpleNamespace(query=SimpleNamespace(Filter=_FakeFilterBuilder), config=SimpleNamespace(Configure=_FakeConfigure)),
    )
    monkeypatch.setattr(ws, "weaviate", fake_weaviate)
    monkeypatch.setattr(ws, "DataType", SimpleNamespace(TEXT="text"))
    monkeypatch.setattr(ws, "MetadataQuery", _FakeMetaQuery)

    with pytest.raises(ConnectionError):
        ws.WeaviateVectorStore(host="localhost", port=8080)

    with pytest.raises(ConnectionError):
        ws.WeaviateVectorStore(host="cluster.weaviate.network", port=None, api_key="k")


def test_import_guard(monkeypatch):
    monkeypatch.setattr(ws, "WEAVIATE_AVAILABLE", False)
    with pytest.raises(ImportError):
        ws.WeaviateVectorStore()
