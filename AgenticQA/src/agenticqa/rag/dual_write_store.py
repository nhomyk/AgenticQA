"""Dual-write vector store wrapper for migration cutovers."""

from typing import Any, Dict, List, Optional, Tuple


class DualWriteVectorStore:
    """
    Wrap two vector stores with write replication.

    - Reads: primary first, fallback to secondary on read error
    - Writes: replicated to both stores
    """

    def __init__(
        self,
        primary_store: Any,
        secondary_store: Any,
        primary_name: str = "primary",
        secondary_name: str = "secondary",
    ):
        self.primary_store = primary_store
        self.secondary_store = secondary_store
        self.primary_name = primary_name
        self.secondary_name = secondary_name

    def add_document(
        self, content: str, embedding: List[float], metadata: Dict, doc_type: str
    ) -> str:
        """Write to primary and replicate to secondary."""
        primary_id = self.primary_store.add_document(content, embedding, metadata, doc_type)

        secondary_metadata = dict(metadata)
        secondary_metadata.setdefault("source_id", str(primary_id))
        secondary_metadata.setdefault("id", str(primary_id))

        try:
            self.secondary_store.add_document(content, embedding, secondary_metadata, doc_type)
        except Exception as exc:
            print(
                f"Warning: secondary vector write failed ({self.secondary_name}): {exc}. "
                "Primary write succeeded."
            )

        return str(primary_id)

    def search(
        self,
        embedding: List[float],
        doc_type: Optional[str] = None,
        k: int = 5,
        threshold: float = 0.7,
    ) -> List[Tuple[Any, float]]:
        """Read from primary with fallback to secondary on primary failure."""
        try:
            return self.primary_store.search(embedding, doc_type=doc_type, k=k, threshold=threshold)
        except Exception as primary_error:
            print(
                f"Warning: primary vector search failed ({self.primary_name}): {primary_error}. "
                f"Falling back to {self.secondary_name}."
            )
            return self.secondary_store.search(embedding, doc_type=doc_type, k=k, threshold=threshold)

    def get_documents_by_type(self, doc_type: str) -> List[Any]:
        """Return union of docs from both stores, de-duplicated by id/source_id."""
        docs_by_id: Dict[str, Any] = {}

        for store in (self.primary_store, self.secondary_store):
            try:
                docs = store.get_documents_by_type(doc_type)
            except Exception:
                docs = []
            for doc in docs:
                doc_id = str(getattr(doc, "id", ""))
                source_id = str((getattr(doc, "metadata", {}) or {}).get("source_id", ""))
                key = source_id or doc_id
                if key and key not in docs_by_id:
                    docs_by_id[key] = doc

        return list(docs_by_id.values())

    def list_documents(
        self,
        doc_type: Optional[str] = None,
        include_vectors: bool = True,
        limit: int = 10000,
    ) -> List[Any]:
        """Return union of listed documents from both stores."""
        docs_by_id: Dict[str, Any] = {}

        for store in (self.primary_store, self.secondary_store):
            if not hasattr(store, "list_documents"):
                continue
            try:
                docs = store.list_documents(doc_type=doc_type, include_vectors=include_vectors, limit=limit)
            except Exception:
                docs = []
            for doc in docs:
                doc_id = str(getattr(doc, "id", ""))
                source_id = str((getattr(doc, "metadata", {}) or {}).get("source_id", ""))
                key = source_id or doc_id
                if key and key not in docs_by_id:
                    docs_by_id[key] = doc

        return list(docs_by_id.values())

    def delete_document(self, doc_id: str) -> bool:
        """Delete on both stores."""
        primary_deleted = False
        secondary_deleted = False

        try:
            primary_deleted = bool(self.primary_store.delete_document(doc_id))
        except Exception:
            primary_deleted = False

        try:
            secondary_deleted = bool(self.secondary_store.delete_document(doc_id))
        except Exception:
            secondary_deleted = False

        return primary_deleted or secondary_deleted

    def clear(self):
        """Clear both stores."""
        self.primary_store.clear()
        try:
            self.secondary_store.clear()
        except Exception as exc:
            print(f"Warning: secondary vector clear failed ({self.secondary_name}): {exc}")

    def stats(self) -> Dict:
        """Get combined stats with per-store visibility."""
        primary = self.primary_store.stats()

        try:
            secondary = self.secondary_store.stats()
        except Exception as exc:
            secondary = {"error": str(exc), "backend": self.secondary_name}

        return {
            "backend": "dual-write",
            "primary": primary,
            "secondary": secondary,
            "total_documents": primary.get("total_documents", 0),
            "documents_by_type": primary.get("documents_by_type", {}),
        }

    def close(self):
        """Close both stores."""
        if hasattr(self.primary_store, "close"):
            self.primary_store.close()
        if hasattr(self.secondary_store, "close"):
            self.secondary_store.close()
