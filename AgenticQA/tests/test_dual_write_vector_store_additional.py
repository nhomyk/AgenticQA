from dataclasses import dataclass

from agenticqa.rag.dual_write_store import DualWriteVectorStore


@dataclass
class _Doc:
    id: str
    metadata: dict


class _Store:
    def __init__(self, fail=None):
        self.fail = fail or set()
        self.docs = {}
        self.closed = False

    def add_document(self, content, embedding, metadata, doc_type):
        if "add" in self.fail:
            raise RuntimeError("add failed")
        did = metadata.get("id", "id-1")
        self.docs[did] = _Doc(id=did, metadata=metadata)
        return did

    def search(self, embedding, doc_type=None, k=5, threshold=0.7):
        if "search" in self.fail:
            raise RuntimeError("search failed")
        return [(_Doc(id="id-1", metadata={}), 0.9)]

    def get_documents_by_type(self, doc_type):
        if "get" in self.fail:
            raise RuntimeError("get failed")
        return list(self.docs.values())

    def list_documents(self, doc_type=None, include_vectors=True, limit=10000):
        if "list" in self.fail:
            raise RuntimeError("list failed")
        return list(self.docs.values())

    def delete_document(self, doc_id):
        if "delete" in self.fail:
            raise RuntimeError("delete failed")
        return self.docs.pop(doc_id, None) is not None

    def clear(self):
        if "clear" in self.fail:
            raise RuntimeError("clear failed")
        self.docs.clear()

    def stats(self):
        if "stats" in self.fail:
            raise RuntimeError("stats failed")
        return {"total_documents": len(self.docs), "documents_by_type": {"error": len(self.docs)}}

    def close(self):
        self.closed = True


def test_replication_warning_path_and_delete_paths():
    primary = _Store()
    secondary = _Store(fail={"add", "delete"})
    dw = DualWriteVectorStore(primary, secondary, "p", "s")

    did = dw.add_document("x", [1.0], {"id": "d1"}, "error")
    assert did == "d1"

    # primary deletes successfully
    assert dw.delete_document("d1") is True

    # both fail path
    p2 = _Store(fail={"delete"})
    s2 = _Store(fail={"delete"})
    dw2 = DualWriteVectorStore(p2, s2)
    assert dw2.delete_document("x") is False


def test_union_and_list_with_partial_failures_and_stats_clear_close():
    primary = _Store()
    secondary = _Store(fail={"get", "list", "stats", "clear"})
    primary.add_document("x", [1.0], {"id": "d1"}, "error")
    secondary.docs["s1"] = _Doc(id="s1", metadata={"source_id": "d1"})

    dw = DualWriteVectorStore(primary, secondary)

    docs = dw.get_documents_by_type("error")
    listed = dw.list_documents(doc_type="error")
    assert len(docs) == 1
    assert len(listed) == 1

    stats = dw.stats()
    assert stats["backend"] == "dual-write"
    assert "error" in stats["secondary"]

    dw.clear()  # secondary clear failure should be swallowed
    dw.close()
    assert primary.closed is True
    assert secondary.closed is True


def test_search_primary_failure_fallback_to_secondary():
    primary = _Store(fail={"search"})
    secondary = _Store()
    dw = DualWriteVectorStore(primary, secondary, "primary", "secondary")

    results = dw.search([1.0])
    assert len(results) == 1
