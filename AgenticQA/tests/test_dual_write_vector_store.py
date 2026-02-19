"""Tests for dual-write vector store wrapper."""

from dataclasses import dataclass

from src.agenticqa.rag.dual_write_store import DualWriteVectorStore


@dataclass
class _Doc:
    id: str
    content: str
    embedding: list
    metadata: dict
    timestamp: str
    doc_type: str


class _Store:
    def __init__(self):
        self.docs = []
        self.fail_search = False

    def add_document(self, content, embedding, metadata, doc_type):
        doc_id = metadata.get("id", f"id-{len(self.docs)+1}")
        self.docs.append(
            _Doc(
                id=doc_id,
                content=content,
                embedding=embedding,
                metadata=metadata,
                timestamp=metadata.get("timestamp", ""),
                doc_type=doc_type,
            )
        )
        return doc_id

    def search(self, embedding, doc_type=None, k=5, threshold=0.7):
        if self.fail_search:
            raise RuntimeError("search failed")
        out = []
        for d in self.docs:
            if doc_type is None or d.doc_type == doc_type:
                out.append((d, 0.9))
        return out[:k]

    def get_documents_by_type(self, doc_type):
        return [d for d in self.docs if d.doc_type == doc_type]

    def list_documents(self, doc_type=None, include_vectors=True, limit=10000):
        docs = self.docs
        if doc_type:
            docs = [d for d in docs if d.doc_type == doc_type]
        return docs[:limit]

    def delete_document(self, doc_id):
        before = len(self.docs)
        self.docs = [d for d in self.docs if d.id != doc_id]
        return len(self.docs) < before

    def clear(self):
        self.docs = []

    def stats(self):
        by_type = {}
        for d in self.docs:
            by_type[d.doc_type] = by_type.get(d.doc_type, 0) + 1
        return {"total_documents": len(self.docs), "documents_by_type": by_type}


class TestDualWriteVectorStore:
    def test_replicates_writes(self):
        primary = _Store()
        secondary = _Store()
        store = DualWriteVectorStore(primary, secondary, "weaviate", "qdrant")

        store.add_document("hello", [0.1], {"id": "d1", "timestamp": "2026-01-01"}, "error")

        assert len(primary.docs) == 1
        assert len(secondary.docs) == 1
        assert secondary.docs[0].metadata.get("source_id") == "d1"

    def test_search_falls_back_to_secondary(self):
        primary = _Store()
        secondary = _Store()
        secondary.add_document("fallback", [0.2], {"id": "d2"}, "error")
        primary.fail_search = True

        store = DualWriteVectorStore(primary, secondary, "weaviate", "qdrant")
        results = store.search([0.2], doc_type="error")

        assert len(results) == 1
        assert results[0][0].id == "d2"

    def test_union_get_documents_by_type(self):
        primary = _Store()
        secondary = _Store()
        primary.add_document("a", [0.1], {"id": "x1"}, "error")
        secondary.add_document("a-copy", [0.1], {"id": "y1", "source_id": "x1"}, "error")
        secondary.add_document("b", [0.2], {"id": "x2"}, "error")

        store = DualWriteVectorStore(primary, secondary)
        docs = store.get_documents_by_type("error")

        ids = sorted([d.id for d in docs])
        assert ids == ["x1", "x2"]
