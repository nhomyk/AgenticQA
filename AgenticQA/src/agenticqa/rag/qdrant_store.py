"""
Qdrant-backed Vector Store for RAG

Provides an open-source vector database backend with the same public API used by
`WeaviateVectorStore` for drop-in provider switching.
"""

from __future__ import annotations

from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from datetime import datetime
import os
import uuid

try:
    from qdrant_client import QdrantClient
    from qdrant_client.http import models

    QDRANT_AVAILABLE = True
except ImportError:
    QDRANT_AVAILABLE = False


@dataclass
class VectorDocument:
    """Document stored in vector store"""

    id: str
    content: str
    embedding: List[float]
    metadata: Dict
    timestamp: str
    doc_type: str


class QdrantVectorStore:
    """
    Qdrant-backed vector store for RAG retrieval.

    Maintains the same API shape as `WeaviateVectorStore` for compatibility.
    """

    def __init__(
        self,
        host: str = "localhost",
        port: Optional[int] = 6333,
        collection_name: str = "AgenticQADocuments",
        api_key: Optional[str] = None,
        use_https: bool = False,
        url: Optional[str] = None,
    ):
        if not QDRANT_AVAILABLE:
            raise ImportError(
                "qdrant-client not installed. Install with: pip install qdrant-client"
            )

        self.host = host
        self.port = port or 6333
        self.collection_name = collection_name
        self.api_key = api_key or os.getenv("QDRANT_API_KEY")
        self.use_https = use_https
        self.url = url
        self._vector_size: Optional[int] = None

        self.client = self._connect()

    def _connect(self) -> QdrantClient:
        """Connect to Qdrant server"""
        try:
            if self.url:
                return QdrantClient(url=self.url, api_key=self.api_key)

            return QdrantClient(
                host=self.host,
                port=self.port,
                api_key=self.api_key,
                https=self.use_https,
            )
        except Exception as e:
            target = self.url or f"{self.host}:{self.port}"
            raise ConnectionError(
                f"Failed to connect to Qdrant at {target}. Error: {e}"
            )

    def _ensure_collection_exists(self, vector_size: int):
        """Ensure collection exists with correct vector size"""
        if self.client.collection_exists(self.collection_name):
            if self._vector_size is None:
                self._vector_size = vector_size
            return

        self.client.create_collection(
            collection_name=self.collection_name,
            vectors_config=models.VectorParams(size=vector_size, distance=models.Distance.COSINE),
        )
        self._vector_size = vector_size

    def add_document(
        self, content: str, embedding: List[float], metadata: Dict, doc_type: str
    ) -> str:
        """Add document to Qdrant"""
        if not embedding:
            raise ValueError("Embedding cannot be empty for QdrantVectorStore")

        vector_size = len(embedding)
        self._ensure_collection_exists(vector_size)

        doc_id = metadata.get("id") or str(uuid.uuid4())
        timestamp = metadata.get("timestamp", datetime.utcnow().isoformat())

        payload = {
            "content": content,
            "doc_type": doc_type,
            "metadata": metadata,
            "timestamp": timestamp,
        }

        self.client.upsert(
            collection_name=self.collection_name,
            points=[
                models.PointStruct(
                    id=doc_id,
                    vector=embedding,
                    payload=payload,
                )
            ],
            wait=True,
        )

        return str(doc_id)

    def search(
        self,
        embedding: List[float],
        doc_type: Optional[str] = None,
        k: int = 5,
        threshold: float = 0.7,
    ) -> List[Tuple[VectorDocument, float]]:
        """Search for similar documents in Qdrant"""
        if not self.client.collection_exists(self.collection_name):
            return []

        query_filter = None
        if doc_type:
            query_filter = models.Filter(
                must=[models.FieldCondition(key="doc_type", match=models.MatchValue(value=doc_type))]
            )

        results = self.client.search(
            collection_name=self.collection_name,
            query_vector=embedding,
            query_filter=query_filter,
            limit=k,
            with_payload=True,
            with_vectors=True,
        )

        documents = []
        for item in results:
            similarity = float(item.score)
            if similarity < threshold:
                continue

            payload = item.payload or {}
            metadata = payload.get("metadata") or {}
            vector = list(item.vector) if item.vector is not None else []

            doc = VectorDocument(
                id=str(item.id),
                content=payload.get("content", ""),
                embedding=vector,
                metadata=metadata,
                timestamp=payload.get("timestamp", ""),
                doc_type=payload.get("doc_type", ""),
            )
            documents.append((doc, similarity))

        return documents

    def get_documents_by_type(self, doc_type: str) -> List[VectorDocument]:
        """Get all documents of a specific type"""
        if not self.client.collection_exists(self.collection_name):
            return []

        points, _ = self.client.scroll(
            collection_name=self.collection_name,
            scroll_filter=models.Filter(
                must=[models.FieldCondition(key="doc_type", match=models.MatchValue(value=doc_type))]
            ),
            limit=10000,
            with_payload=True,
            with_vectors=False,
        )

        documents = []
        for point in points:
            payload = point.payload or {}
            documents.append(
                VectorDocument(
                    id=str(point.id),
                    content=payload.get("content", ""),
                    embedding=[],
                    metadata=payload.get("metadata") or {},
                    timestamp=payload.get("timestamp", ""),
                    doc_type=payload.get("doc_type", ""),
                )
            )

        return documents

    def list_documents(
        self,
        doc_type: Optional[str] = None,
        include_vectors: bool = True,
        limit: int = 10000,
    ) -> List[VectorDocument]:
        """List documents from collection, optionally filtered by type."""
        if not self.client.collection_exists(self.collection_name):
            return []

        scroll_filter = None
        if doc_type:
            scroll_filter = models.Filter(
                must=[models.FieldCondition(key="doc_type", match=models.MatchValue(value=doc_type))]
            )

        points, _ = self.client.scroll(
            collection_name=self.collection_name,
            scroll_filter=scroll_filter,
            limit=limit,
            with_payload=True,
            with_vectors=include_vectors,
        )

        documents = []
        for point in points:
            payload = point.payload or {}
            vector = list(point.vector) if (include_vectors and point.vector is not None) else []
            documents.append(
                VectorDocument(
                    id=str(point.id),
                    content=payload.get("content", ""),
                    embedding=vector,
                    metadata=payload.get("metadata") or {},
                    timestamp=payload.get("timestamp", ""),
                    doc_type=payload.get("doc_type", ""),
                )
            )

        return documents

    def delete_document(self, doc_id: str) -> bool:
        """Delete document from Qdrant"""
        if not self.client.collection_exists(self.collection_name):
            return False

        try:
            self.client.delete(
                collection_name=self.collection_name,
                points_selector=models.PointIdsList(points=[doc_id]),
                wait=True,
            )
            return True
        except Exception:
            return False

    def clear(self):
        """Delete all documents from collection"""
        if self.client.collection_exists(self.collection_name):
            self.client.delete_collection(self.collection_name)
        self._vector_size = None

    def stats(self) -> Dict:
        """Get collection statistics"""
        if not self.client.collection_exists(self.collection_name):
            return {
                "total_documents": 0,
                "documents_by_type": {},
                "backend": "qdrant",
            }

        total = self.client.count(
            collection_name=self.collection_name,
            count_filter=None,
            exact=True,
        ).count

        by_type = {}
        for value in ["test_result", "error", "compliance_rule", "performance_pattern"]:
            count = self.client.count(
                collection_name=self.collection_name,
                count_filter=models.Filter(
                    must=[
                        models.FieldCondition(
                            key="doc_type", match=models.MatchValue(value=value)
                        )
                    ]
                ),
                exact=True,
            ).count
            by_type[value] = count

        return {
            "total_documents": total,
            "documents_by_type": by_type,
            "backend": "qdrant",
        }

    def close(self):
        """Close connection (no-op for HTTP client)"""

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
