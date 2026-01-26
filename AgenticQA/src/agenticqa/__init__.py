"""
AgenticQA - Intelligent Autonomous QA Platform

A comprehensive QA platform powered by specialized agents that learn from historical patterns,
analyze real-time data, and make intelligent deployment decisions with RAG-enhanced insights.

Example:
    >>> from agenticqa.rag import VectorStore, MultiAgentRAG
    >>> 
    >>> vector_store = VectorStore(max_documents=10000)
    >>> rag = MultiAgentRAG(vector_store)
    >>> 
    >>> augmented = rag.augment_agent_context("qa", context)
    >>> rag.log_agent_execution("qa", result)
"""

from agenticqa.rag import (
    VectorStore,
    VectorDocument,
    SimpleHashEmbedder,
    SemanticEmbedder,
    EmbedderFactory,
    RAGRetriever,
    MultiAgentRAG,
)

__version__ = "2.0.0"
__author__ = "Nicholas Homyk"
__license__ = "MIT"

__all__ = [
    "VectorStore",
    "VectorDocument",
    "SimpleHashEmbedder",
    "SemanticEmbedder",
    "EmbedderFactory",
    "RAGRetriever",
    "MultiAgentRAG",
]

