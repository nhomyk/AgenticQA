"""
RAG (Retrieval-Augmented Generation) Module

Provides semantic retrieval over test results, errors, compliance rules, and performance patterns.
Enhances agent decision-making with historical context and pattern recognition.

Storage Options:
- Vector Store (Weaviate): Semantic search, unstructured data, pattern matching
- Relational Store (SQLite/PostgreSQL): Structured metrics, exact queries, aggregations
- Hybrid RAG: Combines both for optimal cost and performance

Hybrid Approach:
- Deterministic validation gates remain unchanged
- RAG provides semantic insights and recommendations
- Agents use rag_recommendations for better decision-making
- Smart routing between vector and relational stores
"""

from .weaviate_store import VectorStore, VectorDocument, WeaviateVectorStore
from .qdrant_store import QdrantVectorStore
from .dual_write_store import DualWriteVectorStore
from .embeddings import (
    Embedder,
    SimpleHashEmbedder,
    SemanticEmbedder,
    EmbedderFactory,
    TestResultEmbedder,
    ErrorEmbedder,
    ComplianceRuleEmbedder,
    PerformancePatternEmbedder,
)
from .retriever import RAGRetriever, RetrievalResult, MultiAgentRAG
from .relational_store import RelationalStore, PostgreSQLStore, StructuredMetric
from .hybrid_retriever import HybridRAG, HybridResult
from .migration import (
    CanonicalVectorRecord,
    MigrationValidationError,
    export_vector_store_to_jsonl,
    import_jsonl_to_vector_store,
    validate_jsonl_schema,
    parity_report,
)
from .config import (
    RAGConfig,
    WeaviateConfig,
    QdrantConfig,
    DeploymentMode,
    VectorProvider,
    create_vector_store,
    create_vector_store_for_provider,
    create_rag_system,
)

__all__ = [
    # Vector Store
    "VectorStore",
    "WeaviateVectorStore",
    "QdrantVectorStore",
    "DualWriteVectorStore",
    "VectorDocument",
    # Embeddings
    "Embedder",
    "SimpleHashEmbedder",
    "SemanticEmbedder",
    "EmbedderFactory",
    "TestResultEmbedder",
    "ErrorEmbedder",
    "ComplianceRuleEmbedder",
    "PerformancePatternEmbedder",
    # Retrieval
    "RAGRetriever",
    "RetrievalResult",
    "MultiAgentRAG",
    # Relational Store
    "RelationalStore",
    "PostgreSQLStore",
    "StructuredMetric",
    # Hybrid RAG
    "HybridRAG",
    "HybridResult",
    # Migration
    "CanonicalVectorRecord",
    "MigrationValidationError",
    "export_vector_store_to_jsonl",
    "import_jsonl_to_vector_store",
    "validate_jsonl_schema",
    "parity_report",
    # Configuration
    "RAGConfig",
    "WeaviateConfig",
    "QdrantConfig",
    "DeploymentMode",
    "VectorProvider",
    "create_vector_store",
    "create_vector_store_for_provider",
    "create_rag_system",
]
