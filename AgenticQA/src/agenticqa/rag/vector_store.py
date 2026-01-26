"""
Vector Store for RAG (Retrieval-Augmented Generation)

Stores embeddings for test results, errors, compliance rules, and performance patterns.
Uses in-memory storage for fast access (suitable for agent orchestration).
"""

import json
import hashlib
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, asdict
from datetime import datetime
import numpy as np


@dataclass
class VectorDocument:
    """Document stored in vector store"""
    id: str
    content: str
    embedding: List[float]
    metadata: Dict
    timestamp: str
    doc_type: str  # 'test_result', 'error', 'compliance_rule', 'performance_pattern'


class VectorStore:
    """In-memory vector store for RAG retrieval"""

    def __init__(self, max_documents: int = 10000):
        self.documents: Dict[str, VectorDocument] = {}
        self.max_documents = max_documents
        self.index_by_type: Dict[str, List[str]] = {}

    def add_document(
        self,
        content: str,
        embedding: List[float],
        metadata: Dict,
        doc_type: str
    ) -> str:
        """Add document to vector store"""
        doc_id = hashlib.md5(f"{content}{datetime.utcnow().isoformat()}".encode()).hexdigest()
        
        doc = VectorDocument(
            id=doc_id,
            content=content,
            embedding=embedding,
            metadata=metadata,
            timestamp=datetime.utcnow().isoformat(),
            doc_type=doc_type
        )
        
        self.documents[doc_id] = doc
        
        # Index by type
        if doc_type not in self.index_by_type:
            self.index_by_type[doc_type] = []
        self.index_by_type[doc_type].append(doc_id)
        
        # Evict oldest if exceeds max
        if len(self.documents) > self.max_documents:
            self._evict_oldest()
        
        return doc_id

    def search(
        self,
        embedding: List[float],
        doc_type: Optional[str] = None,
        k: int = 5,
        threshold: float = 0.7
    ) -> List[Tuple[VectorDocument, float]]:
        """
        Search vector store for similar documents
        
        Args:
            embedding: Query embedding
            doc_type: Filter by document type (optional)
            k: Number of results to return
            threshold: Minimum similarity threshold (0-1)
        
        Returns:
            List of (document, similarity_score) tuples
        """
        results = []
        
        # Determine which documents to search
        if doc_type and doc_type in self.index_by_type:
            doc_ids = self.index_by_type[doc_type]
        else:
            doc_ids = self.documents.keys()
        
        # Calculate similarities
        for doc_id in doc_ids:
            doc = self.documents[doc_id]
            similarity = self._cosine_similarity(embedding, doc.embedding)
            
            if similarity >= threshold:
                results.append((doc, similarity))
        
        # Sort by similarity (highest first)
        results.sort(key=lambda x: x[1], reverse=True)
        
        return results[:k]

    def get_documents_by_type(self, doc_type: str) -> List[VectorDocument]:
        """Get all documents of a specific type"""
        doc_ids = self.index_by_type.get(doc_type, [])
        return [self.documents[doc_id] for doc_id in doc_ids]

    def delete_document(self, doc_id: str) -> bool:
        """Delete document from store"""
        if doc_id not in self.documents:
            return False
        
        doc = self.documents[doc_id]
        doc_type = doc.doc_type
        
        del self.documents[doc_id]
        self.index_by_type[doc_type].remove(doc_id)
        
        return True

    def clear(self):
        """Clear all documents"""
        self.documents.clear()
        self.index_by_type.clear()

    def stats(self) -> Dict:
        """Get store statistics"""
        return {
            'total_documents': len(self.documents),
            'documents_by_type': {
                doc_type: len(doc_ids) 
                for doc_type, doc_ids in self.index_by_type.items()
            },
            'max_documents': self.max_documents
        }

    def to_json(self) -> str:
        """Serialize store to JSON"""
        documents = [asdict(doc) for doc in self.documents.values()]
        return json.dumps(documents, indent=2)

    def from_json(self, json_str: str):
        """Load store from JSON"""
        documents = json.loads(json_str)
        for doc_data in documents:
            embedding = doc_data.pop('embedding')
            doc = VectorDocument(embedding=embedding, **doc_data)
            self.documents[doc.id] = doc
            
            if doc.doc_type not in self.index_by_type:
                self.index_by_type[doc.doc_type] = []
            self.index_by_type[doc.doc_type].append(doc.id)

    @staticmethod
    def _cosine_similarity(vec1: List[float], vec2: List[float]) -> float:
        """Calculate cosine similarity between two vectors"""
        arr1 = np.array(vec1)
        arr2 = np.array(vec2)
        
        dot_product = np.dot(arr1, arr2)
        norm1 = np.linalg.norm(arr1)
        norm2 = np.linalg.norm(arr2)
        
        if norm1 == 0 or norm2 == 0:
            return 0.0
        
        return float(dot_product / (norm1 * norm2))

    def _evict_oldest(self):
        """Evict oldest documents when exceeding max"""
        # Sort by timestamp
        sorted_docs = sorted(
            self.documents.values(),
            key=lambda d: d.timestamp
        )
        
        # Remove oldest 10%
        num_to_remove = max(1, len(sorted_docs) // 10)
        for doc in sorted_docs[:num_to_remove]:
            self.delete_document(doc.id)
