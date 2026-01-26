"""
AgenticQA - Agentic Quality Assurance Platform

RAG-enhanced multi-agent system for intelligent code quality and testing insights.
Supports both local development and cloud production deployments.

Quick Start (Local):
    >>> from agenticqa.rag import VectorStore, MultiAgentRAG
    >>> vector_store = VectorStore(host="localhost", port=8080)
    >>> rag = MultiAgentRAG(vector_store)

Quick Start (Cloud):
    >>> from agenticqa.rag import create_rag_system
    >>> # Set environment variables:
    >>> # export AGENTICQA_RAG_MODE=cloud
    >>> # export WEAVIATE_HOST=cluster.weaviate.network
    >>> # export WEAVIATE_API_KEY=your-api-key
    >>> rag = create_rag_system()
"""

from .rag import (
    # Vector Store
    VectorStore,
    WeaviateVectorStore,
    VectorDocument,
    # Embeddings
    Embedder,
    SimpleHashEmbedder,
    SemanticEmbedder,
    EmbedderFactory,
    TestResultEmbedder,
    ErrorEmbedder,
    ComplianceRuleEmbedder,
    PerformancePatternEmbedder,
    # Retrieval & Orchestration
    RAGRetriever,
    RetrievalResult,
    MultiAgentRAG,
    # Configuration (for cloud/pipeline deployments)
    RAGConfig,
    WeaviateConfig,
    DeploymentMode,
    create_rag_system,
)

__version__ = "2.0.0"

__all__ = [
    # Vector Store
    "VectorStore",
    "WeaviateVectorStore",
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
    # Retrieval & Orchestration
    "RAGRetriever",
    "RetrievalResult",
    "MultiAgentRAG",
    # Configuration
    "RAGConfig",
    "WeaviateConfig",
    "DeploymentMode",
    "create_rag_system",
]
