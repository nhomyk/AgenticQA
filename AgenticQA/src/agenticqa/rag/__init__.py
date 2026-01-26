"""
RAG (Retrieval-Augmented Generation) Module

Provides semantic retrieval over test results, errors, compliance rules, and performance patterns.
Enhances agent decision-making with historical context and pattern recognition.

Hybrid Approach:
- Deterministic validation gates remain unchanged
- RAG provides semantic insights and recommendations
- Agents use rag_recommendations for better decision-making
"""

from .vector_store import VectorStore, VectorDocument
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

__all__ = [
    "VectorStore",
    "VectorDocument",
    "Embedder",
    "SimpleHashEmbedder",
    "SemanticEmbedder",
    "EmbedderFactory",
    "TestResultEmbedder",
    "ErrorEmbedder",
    "ComplianceRuleEmbedder",
    "PerformancePatternEmbedder",
    "RAGRetriever",
    "RetrievalResult",
    "MultiAgentRAG",
]
