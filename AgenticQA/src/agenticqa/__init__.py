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

try:
    from .rag import (
        # Vector Store
        VectorStore,
        WeaviateVectorStore,
        QdrantVectorStore,
        DualWriteVectorStore,
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
        QdrantConfig,
        DeploymentMode,
        VectorProvider,
        create_vector_store,
        create_vector_store_for_provider,
        create_rag_system,
    )
except Exception:  # pragma: no cover - RAG deps optional for lightweight usage
    VectorStore = None
    WeaviateVectorStore = None
    QdrantVectorStore = None
    DualWriteVectorStore = None
    VectorDocument = None
    Embedder = None
    SimpleHashEmbedder = None
    SemanticEmbedder = None
    EmbedderFactory = None
    TestResultEmbedder = None
    ErrorEmbedder = None
    ComplianceRuleEmbedder = None
    PerformancePatternEmbedder = None
    RAGRetriever = None
    RetrievalResult = None
    MultiAgentRAG = None
    RAGConfig = None
    WeaviateConfig = None
    QdrantConfig = None
    DeploymentMode = None
    VectorProvider = None
    create_vector_store = None
    create_vector_store_for_provider = None
    create_rag_system = None

try:
    from agents import AgentOrchestrator
except Exception:  # pragma: no cover - optional compatibility import
    AgentOrchestrator = None

try:
    from data_store.artifact_store import TestArtifactStore
    from data_store.secure_pipeline import SecureDataPipeline
    from data_store.data_quality_pipeline import DataQualityValidatedPipeline
    from .data_store.code_change_tracker import CodeChangeTracker
    from .data_store.snapshot_pipeline import SnapshotValidatingPipeline
except Exception:  # pragma: no cover - optional data_store imports
    TestArtifactStore = None
    SecureDataPipeline = None
    DataQualityValidatedPipeline = None
    CodeChangeTracker = None
    SnapshotValidatingPipeline = None

__version__ = "2.0.0"

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
    # Retrieval & Orchestration
    "RAGRetriever",
    "RetrievalResult",
    "MultiAgentRAG",
    # Configuration
    "RAGConfig",
    "WeaviateConfig",
    "QdrantConfig",
    "DeploymentMode",
    "VectorProvider",
    "create_vector_store",
    "create_vector_store_for_provider",
    "create_rag_system",
    "AgentOrchestrator",
    # Data store (optional, requires data_store package on path)
    "TestArtifactStore",
    "SecureDataPipeline",
    "DataQualityValidatedPipeline",
    "CodeChangeTracker",
    "SnapshotValidatingPipeline",
]
