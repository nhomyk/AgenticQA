from agenticqa.rag.vector_store import VectorStore


def test_add_search_delete_and_stats():
    store = VectorStore(max_documents=10)

    d1 = store.add_document("alpha", [1.0, 0.0], {"k": 1}, "test_result")
    d2 = store.add_document("beta", [0.0, 1.0], {"k": 2}, "error")

    assert d1 != d2
    assert store.stats()["total_documents"] == 2
    assert store.stats()["documents_by_type"]["test_result"] == 1

    results = store.search([1.0, 0.0], doc_type="test_result", k=5, threshold=0.5)
    assert len(results) == 1
    assert results[0][0].content == "alpha"

    assert store.delete_document(d2) is True
    assert store.delete_document("missing") is False
    assert store.stats()["total_documents"] == 1


def test_json_roundtrip_and_clear():
    store = VectorStore(max_documents=10)
    store.add_document("a", [1.0, 0.0], {}, "test_result")
    store.add_document("b", [0.0, 1.0], {}, "error")

    serialized = store.to_json()

    restored = VectorStore(max_documents=10)
    restored.from_json(serialized)

    assert restored.stats()["total_documents"] == 2
    assert len(restored.get_documents_by_type("error")) == 1

    restored.clear()
    assert restored.stats()["total_documents"] == 0


def test_evict_oldest_when_capacity_exceeded():
    store = VectorStore(max_documents=3)

    for i in range(4):
        store.add_document(f"doc-{i}", [1.0, 0.0], {}, "test_result")

    # Capacity enforcement should trigger eviction
    assert store.stats()["total_documents"] <= 3


def test_cosine_similarity_handles_zero_norm_and_sorting():
    store = VectorStore()
    assert store._cosine_similarity([0.0, 0.0], [1.0, 0.0]) == 0.0

    store.add_document("close", [1.0, 0.0], {}, "test_result")
    store.add_document("far", [0.0, 1.0], {}, "test_result")

    results = store.search([1.0, 0.0], doc_type="test_result", k=2, threshold=0.0)
    assert len(results) == 2
    assert results[0][1] >= results[1][1]
