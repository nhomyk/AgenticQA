"""
Weaviate-backed Vector Store for RAG

Replaces in-memory SimpleVectorStore with enterprise-grade Weaviate vector database.
Provides persistence, scalability, and production-ready performance.
"""

from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
import json
import os

try:
    import weaviate
    from weaviate.connect import ConnectionParams
    from weaviate.classes.query import MetadataQuery
    from weaviate.classes.config import DataType
    WEAVIATE_AVAILABLE = True
except ImportError:
    WEAVIATE_AVAILABLE = False


@dataclass
class VectorDocument:
    """Document stored in vector store"""
    id: str
    content: str
    embedding: List[float]
    metadata: Dict
    timestamp: str
    doc_type: str


class WeaviateVectorStore:
    """
    Weaviate-backed vector store for RAG retrieval.
    
    Replaces in-memory SimpleVectorStore with persistent, scalable Weaviate.
    Maintains same public API for drop-in compatibility.
    """

    def __init__(
        self,
        host: str = "localhost",
        port: int = 8080,
        collection_name: str = "AgenticQADocuments",
        api_key: Optional[str] = None
    ):
        """
        Initialize Weaviate vector store.
        
        Args:
            host: Weaviate server host
            port: Weaviate server port
            collection_name: Name of collection to use
            api_key: API key if using Weaviate Cloud (optional)
        """
        if not WEAVIATE_AVAILABLE:
            raise ImportError(
                "weaviate-client not installed. "
                "Install with: pip install weaviate-client"
            )

        self.host = host
        self.port = port
        self.collection_name = collection_name
        self.api_key = api_key or os.getenv("WEAVIATE_API_KEY")

        # Connect to Weaviate
        self.client = self._connect()
        self._ensure_collection_exists()

    def _connect(self):
        """Connect to Weaviate server"""
        try:
            if self.api_key:
                # Weaviate Cloud
                client = weaviate.connect_to_weaviate_cloud(
                    cluster_url=f"https://{self.host}",
                    auth_credentials=weaviate.auth.AuthApiKey(self.api_key)
                )
            else:
                # Local Weaviate
                client = weaviate.connect_to_local(
                    host=self.host,
                    port=self.port,
                    skip_init_checks=False
                )
            
            return client
        except Exception as e:
            raise ConnectionError(
                f"Failed to connect to Weaviate at {self.host}:{self.port}. "
                f"Make sure Weaviate is running. Error: {e}"
            )

    def _ensure_collection_exists(self):
        """Ensure collection exists, create if not"""
        try:
            # Check if collection exists
            if self.client.collections.exists(self.collection_name):
                return
            
            # Create collection with vector config
            self.client.collections.create(
                name=self.collection_name,
                description="AgenticQA document embeddings",
                properties=[
                    {
                        "name": "content",
                        "data_type": DataType.TEXT,
                        "description": "Document content"
                    },
                    {
                        "name": "doc_type",
                        "data_type": DataType.TEXT,
                        "description": "Document type (test_result, error, compliance_rule, performance_pattern)"
                    },
                    {
                        "name": "metadata",
                        "data_type": DataType.TEXT,
                        "description": "JSON metadata"
                    },
                    {
                        "name": "timestamp",
                        "data_type": DataType.TEXT,
                        "description": "ISO timestamp"
                    }
                ],
                vectorizer_config=weaviate.classes.config.Configure.Vectorizer.text2vec_openai(
                    model="text-embedding-3-small"
                ) if self._has_openai() else weaviate.classes.config.Configure.Vectorizer.none()
            )
        except Exception as e:
            raise RuntimeError(f"Failed to ensure collection exists: {e}")

    def _has_openai(self) -> bool:
        """Check if OpenAI API key is available"""
        return bool(os.getenv("OPENAI_API_KEY"))

    def add_document(
        self,
        content: str,
        embedding: List[float],
        metadata: Dict,
        doc_type: str
    ) -> str:
        """Add document to Weaviate"""
        try:
            collection = self.client.collections.get(self.collection_name)
            
            # Add document
            doc_id = collection.data.insert(
                properties={
                    "content": content,
                    "doc_type": doc_type,
                    "metadata": json.dumps(metadata),
                    "timestamp": metadata.get("timestamp", "")
                },
                vector=embedding
            )
            
            return str(doc_id)
        except Exception as e:
            raise RuntimeError(f"Failed to add document to Weaviate: {e}")

    def search(
        self,
        embedding: List[float],
        doc_type: Optional[str] = None,
        k: int = 5,
        threshold: float = 0.7
    ) -> List[Tuple[VectorDocument, float]]:
        """
        Search for similar documents in Weaviate.
        
        Args:
            embedding: Query embedding vector
            doc_type: Filter by document type (optional)
            k: Number of results to return
            threshold: Minimum similarity threshold
        
        Returns:
            List of (document, similarity_score) tuples
        """
        try:
            collection = self.client.collections.get(self.collection_name)
            
            # Build where filter if doc_type specified
            where_filter = None
            if doc_type:
                where_filter = weaviate.classes.query.Filter.by_property(
                    "doc_type"
                ).equal(doc_type)
            
            # Search with vector
            results = collection.query.near_vector(
                near_vector=embedding,
                limit=k,
                filters=where_filter,
                return_properties=["content", "doc_type", "metadata", "timestamp"],
                return_metadata=MetadataQuery(distance=True),
                include_vector=True
            )

            # Convert to our format
            documents = []
            for item in results.objects:
                # Weaviate returns distance (0-2), convert to similarity (0-1)
                distance = item.metadata.distance if (hasattr(item.metadata, 'distance') and item.metadata.distance is not None) else 0.0
                similarity = 1.0 - (distance / 2.0)  # Normalize to 0-1
                
                # Only include if above threshold
                if similarity >= threshold:
                    doc = VectorDocument(
                        id=item.uuid,
                        content=item.properties.get("content", ""),
                        embedding=item.vector["default"] if item.vector else [],
                        metadata=json.loads(item.properties.get("metadata", "{}")),
                        timestamp=item.properties.get("timestamp", ""),
                        doc_type=item.properties.get("doc_type", "")
                    )
                    documents.append((doc, similarity))
            
            return documents
        except Exception as e:
            raise RuntimeError(f"Search failed: {e}")

    def get_documents_by_type(self, doc_type: str) -> List[VectorDocument]:
        """Get all documents of a specific type"""
        try:
            collection = self.client.collections.get(self.collection_name)
            
            results = collection.query.fetch_objects(
                filters=weaviate.classes.query.Filter.by_property(
                    "doc_type"
                ).equal(doc_type),
                return_properties=["content", "doc_type", "metadata", "timestamp"]
            )
            
            documents = []
            for item in results.objects:
                doc = VectorDocument(
                    id=item.uuid,
                    content=item.properties.get("content", ""),
                    embedding=[],  # Not fetched for efficiency
                    metadata=json.loads(item.properties.get("metadata", "{}")),
                    timestamp=item.properties.get("timestamp", ""),
                    doc_type=item.properties.get("doc_type", "")
                )
                documents.append(doc)
            
            return documents
        except Exception as e:
            raise RuntimeError(f"Failed to fetch documents by type: {e}")

    def delete_document(self, doc_id: str) -> bool:
        """Delete document from Weaviate"""
        try:
            collection = self.client.collections.get(self.collection_name)
            collection.data.delete_by_id(doc_id)
            return True
        except Exception as e:
            print(f"Failed to delete document: {e}")
            return False

    def clear(self):
        """Delete all documents from collection"""
        try:
            collection = self.client.collections.get(self.collection_name)
            # Get all objects and delete them
            results = collection.query.fetch_objects(limit=1000)
            for item in results.objects:
                collection.data.delete_by_id(item.uuid)
        except Exception as e:
            raise RuntimeError(f"Failed to clear collection: {e}")

    def stats(self) -> Dict:
        """Get collection statistics"""
        try:
            collection = self.client.collections.get(self.collection_name)
            
            # Count total documents
            total = collection.query.fetch_objects(limit=1).count
            
            # Count by type
            by_type = {}
            for doc_type in ["test_result", "error", "compliance_rule", "performance_pattern"]:
                results = collection.query.fetch_objects(
                    filters=weaviate.classes.query.Filter.by_property(
                        "doc_type"
                    ).equal(doc_type),
                    limit=1
                )
                by_type[doc_type] = results.count if hasattr(results, 'count') else 0
            
            return {
                "total_documents": total,
                "documents_by_type": by_type,
                "backend": "weaviate"
            }
        except Exception as e:
            raise RuntimeError(f"Failed to get stats: {e}")

    def close(self):
        """Close connection to Weaviate"""
        try:
            if self.client:
                self.client.close()
        except Exception as e:
            print(f"Error closing Weaviate connection: {e}")

    def __enter__(self):
        """Context manager entry"""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit"""
        self.close()


# Backward compatibility alias
class VectorStore(WeaviateVectorStore):
    """Alias for WeaviateVectorStore for backward compatibility"""
    pass
