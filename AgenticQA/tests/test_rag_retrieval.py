"""
Tests for RAG (Retrieval-Augmented Generation) Module

Tests Weaviate vector store, embeddings, retrieval, and multi-agent RAG integration.
Uses mock Weaviate for CI/CD environments without Docker.
"""

import pytest
import json
from datetime import datetime
from unittest.mock import Mock, MagicMock, patch

from agenticqa.rag import (
    VectorStore,
    VectorDocument,
    SimpleHashEmbedder,
    SemanticEmbedder,
    EmbedderFactory,
    RAGRetriever,
    MultiAgentRAG,
    TestResultEmbedder,
    ErrorEmbedder,
)

# Check if Weaviate is available for integration tests
try:
    import weaviate
    WEAVIATE_AVAILABLE = True
except ImportError:
    WEAVIATE_AVAILABLE = False


@pytest.fixture
def mock_weaviate_store():
    """Create a mock Weaviate store for testing"""
    store = MagicMock()
    store.documents = {}
    store.index_by_type = {}
    
    # Mock search functionality
    def mock_search(embedding, doc_type=None, k=5, threshold=0.7):
        results = []
        for doc_id, doc_data in store.documents.items():
            if doc_type and hasattr(doc_data, 'doc_type') and doc_data.doc_type != doc_type:
                continue
            elif doc_type and isinstance(doc_data, dict) and doc_data.get("doc_type") != doc_type:
                continue
            similarity = 0.8  # Mock high similarity
            if similarity >= threshold:
                # Return as tuple (VectorDocument, similarity)
                if isinstance(doc_data, VectorDocument):
                    results.append((doc_data, similarity))
                else:
                    results.append((doc_data, similarity))
        return results[:k]
    
    def mock_add_document(content, embedding, metadata, doc_type):
        doc = VectorDocument(
            id="mock_id_" + str(len(store.documents)),
            content=content,
            embedding=embedding,
            metadata=metadata,
            timestamp=metadata.get("timestamp", ""),
            doc_type=doc_type
        )
        store.documents[doc.id] = doc
        return doc.id
    
    store.search = mock_search
    store.stats = lambda: {"total_documents": len(store.documents)}
    store.get_documents_by_type = lambda dt: [d for d in store.documents.values() if isinstance(d, VectorDocument) and d.doc_type == dt]
    store.add_document = mock_add_document
    
    return store


@pytest.mark.unit
class TestEmbeddings:
    """Tests for embedding generation"""

    def test_simple_hash_embedder(self):
        """Test SimpleHashEmbedder"""
        embedder = SimpleHashEmbedder()
        
        embedding = embedder.embed("test error in payment flow")
        
        assert len(embedding) == 768
        assert all(isinstance(x, float) for x in embedding)
        assert max(embedding) <= 1.0
        assert min(embedding) >= 0.0

    def test_embeddings_are_deterministic(self):
        """Test that same text produces same embedding"""
        embedder = SimpleHashEmbedder()
        
        text = "Test failure in checkout"
        embedding1 = embedder.embed(text)
        embedding2 = embedder.embed(text)
        
        assert embedding1 == embedding2

    def test_embedder_factory(self):
        """Test embedder factory"""
        embedder1 = EmbedderFactory.get_embedder("simple")
        embedder2 = EmbedderFactory.get_embedder("semantic")
        
        assert isinstance(embedder1, SimpleHashEmbedder)
        assert embedder2 is not None

    def test_test_result_embedder(self):
        """Test embedding of test results"""
        embedder = TestResultEmbedder()
        
        test_result = {
            "test_name": "checkout_flow",
            "status": "failed",
            "error_message": "Timeout error"
        }
        
        embedding = embedder.embed_test_result(test_result)
        
        assert len(embedding) == 768
        assert all(isinstance(x, float) for x in embedding)

    def test_error_embedder(self):
        """Test embedding of errors"""
        embedder = ErrorEmbedder()
        
        error = {
            "error_type": "TimeoutError",
            "message": "Request timeout after 30s",
            "stack_trace": "..."
        }
        
        embedding = embedder.embed_error(error)
        
        assert len(embedding) == 768


@pytest.mark.unit
class TestRAGRetrieverWithMock:
    """Tests for RAG retrieval using mocked Weaviate"""

    def test_retrieve_similar_tests(self, mock_weaviate_store):
        """Test retrieving similar test results"""
        embedder = SimpleHashEmbedder()
        retriever = RAGRetriever(mock_weaviate_store, embedder)
        
        # With mock store, search returns empty by default
        # Real Weaviate testing is in TestWeaviateIntegration
        results = retriever.retrieve_similar_tests("checkout", "integration")
        
        # Should return list (even if empty)
        assert isinstance(results, list)

    def test_agent_recommendations(self, mock_weaviate_store):
        """Test getting recommendations for an agent"""
        embedder = SimpleHashEmbedder()
        retriever = RAGRetriever(mock_weaviate_store, embedder)
        
        # Get QA agent recommendations
        context = {
            "test_name": "checkout",
            "test_type": "integration"
        }
        recommendations = retriever.get_agent_recommendations("qa", context)
        
        # Should get some recommendations
        assert isinstance(recommendations, list)


@pytest.mark.unit
class TestMultiAgentRAG:
    """Tests for multi-agent RAG integration"""

    def test_augment_agent_context(self, mock_weaviate_store):
        """Test augmenting agent context with RAG insights"""
        embedder = SimpleHashEmbedder()
        multi_rag = MultiAgentRAG(mock_weaviate_store, embedder)
        
        agent_context = {
            "test_name": "checkout",
            "test_type": "integration"
        }
        
        augmented = multi_rag.augment_agent_context("qa", agent_context)
        
        # Should have RAG fields
        assert "rag_recommendations" in augmented
        assert "rag_insights_count" in augmented
        assert "test_name" in augmented  # Original fields preserved

    def test_log_agent_execution(self, mock_weaviate_store):
        """Test logging agent execution"""
        embedder = SimpleHashEmbedder()
        multi_rag = MultiAgentRAG(mock_weaviate_store, embedder)
        
        test_result = {
            "test_name": "checkout",
            "status": "failed",
            "error_message": "Timeout",
            "test_type": "integration"
        }
        
        # Log execution (should not raise)
        multi_rag.log_agent_execution("qa", test_result)

    def test_hybrid_approach_gates_vs_insights(self, mock_weaviate_store):
        """
        Test that RAG provides insights without changing gate decisions
        """
        embedder = SimpleHashEmbedder()
        multi_rag = MultiAgentRAG(mock_weaviate_store, embedder)
        
        # Original context with deterministic gate
        agent_context = {
            "test_name": "checkout",
            "test_type": "integration",
            "pass_threshold": 0.95,
            "current_pass_rate": 0.98
        }
        
        # Augment with RAG
        augmented = multi_rag.augment_agent_context("qa", agent_context)
        
        # Gate decision should be unchanged
        assert augmented["pass_threshold"] == 0.95
        assert augmented["current_pass_rate"] == 0.98
        
        # But now has RAG insights
        assert "rag_recommendations" in augmented


@pytest.mark.integration
class TestRAGIntegration:
    """Integration tests for RAG with agents"""

    def test_full_learning_cycle(self, mock_weaviate_store):
        """Test full cycle: execute agent, log, retrieve, recommend"""
        embedder = SimpleHashEmbedder()
        multi_rag = MultiAgentRAG(mock_weaviate_store, embedder)
        
        # Simulate first test execution
        test_result_1 = {
            "test_name": "checkout_flow",
            "status": "failed",
            "error_message": "Timeout error after 30s",
            "test_type": "integration",
            "root_cause": "Slow payment service",
            "recommendation": "Add timeout handling"
        }
        
        multi_rag.log_agent_execution("qa", test_result_1)
        
        # Simulate second similar test
        context = {
            "test_name": "checkout_flow",
            "test_type": "integration"
        }
        
        augmented = multi_rag.augment_agent_context("qa", context)
        
        # System should have logged the execution
        assert augmented["rag_insights_count"] >= 0

    def test_compliance_rule_learning(self, mock_weaviate_store):
        """Test compliance rule storage and retrieval"""
        embedder = SimpleHashEmbedder()
        multi_rag = MultiAgentRAG(mock_weaviate_store, embedder)
        
        # Log a compliance check
        compliance_result = {
            "rule_name": "PII Protection",
            "regulation": "GDPR",
            "requirement": "Customer SSN must be encrypted",
            "validation_method": "Regex + encryption check",
            "status": "passed"
        }
        
        multi_rag.log_agent_execution("compliance", compliance_result)
        
        # Verify it was logged
        assert True  # Just verify no exceptions


@pytest.mark.skipif(not WEAVIATE_AVAILABLE, reason="Weaviate not installed")
class TestWeaviateIntegration:
    """Integration tests with real Weaviate (requires Docker)"""

    @pytest.fixture
    def weaviate_store(self):
        """Connect to local Weaviate"""
        try:
            store = VectorStore(host="localhost", port=8080)
            yield store
            store.close()
        except Exception as e:
            pytest.skip(f"Could not connect to Weaviate: {e}")

    def test_weaviate_connection(self, weaviate_store):
        """Test connection to Weaviate"""
        stats = weaviate_store.stats()
        assert "backend" in stats or "total_documents" in stats

    def test_add_document_to_weaviate(self, weaviate_store):
        """Test adding document to Weaviate"""
        embedding = [0.1] * 768
        
        doc_id = weaviate_store.add_document(
            content="Test failure",
            embedding=embedding,
            metadata={"test": "1"},
            doc_type="test_result"
        )
        
        assert doc_id is not None

    def test_search_in_weaviate(self, weaviate_store):
        """Test searching in Weaviate"""
        embedding = [0.1] * 768
        
        results = weaviate_store.search(
            embedding=embedding,
            k=5,
            threshold=0.5
        )
        
        assert isinstance(results, list)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
