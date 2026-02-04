"""
Tests for Hybrid RAG System
"""
import pytest
import os
import tempfile
from pathlib import Path

# Add src to path for testing
import sys
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

from agenticqa.rag.relational_store import RelationalStore
from agenticqa.rag.hybrid_retriever import HybridRAG, HybridResult


class TestRelationalStore:
    """Test RelationalStore functionality"""

    def test_store_and_query_metrics(self):
        """Test storing and querying metrics"""
        # Use in-memory database for testing
        store = RelationalStore(db_path=":memory:")

        # Store a metric
        store.store_metric(
            run_id="test-run-1",
            agent_type="qa",
            metric_type="coverage",
            metric_name="line_coverage",
            metric_value=87.5,
            metadata={"files": 10, "lines": 1000}
        )

        # Query metrics
        metrics = store.query_metrics(
            agent_type="qa",
            metric_type="coverage"
        )

        assert len(metrics) == 1
        assert metrics[0].metric_value == 87.5
        assert metrics[0].metric_name == "line_coverage"
        assert metrics[0].agent_type == "qa"

        store.close()

    def test_store_and_query_executions(self):
        """Test storing and querying executions"""
        store = RelationalStore(db_path=":memory:")

        # Store execution
        store.store_execution(
            run_id="test-run-1",
            agent_type="compliance",
            action="fix_accessibility",
            outcome="success",
            success=True,
            metadata={"violations_fixed": 3}
        )

        # Get success rate
        rate, successes, total = store.get_success_rate(
            agent_type="compliance",
            action="fix_accessibility"
        )

        assert rate == 1.0  # 100% success
        assert successes == 1
        assert total == 1

        store.close()

    def test_metric_stats(self):
        """Test metric statistics calculation"""
        store = RelationalStore(db_path=":memory:")

        # Store multiple metrics
        for i, value in enumerate([80.0, 85.0, 90.0, 95.0]):
            store.store_metric(
                run_id=f"run-{i}",
                agent_type="qa",
                metric_type="coverage",
                metric_name="line_coverage",
                metric_value=value
            )

        # Get stats
        stats = store.get_metric_stats(
            agent_type="qa",
            metric_name="line_coverage",
            limit=10
        )

        assert stats['avg'] == 87.5  # (80 + 85 + 90 + 95) / 4
        assert stats['min'] == 80.0
        assert stats['max'] == 95.0
        assert stats['count'] == 4
        assert stats['trend'] == 'increasing'

        store.close()


class TestHybridRAG:
    """Test HybridRAG functionality"""

    def test_hybrid_rag_initialization(self):
        """Test HybridRAG can be initialized"""
        rag = HybridRAG(
            vector_store=None,  # No vector store for testing
            relational_store=RelationalStore(db_path=":memory:")
        )

        assert rag.relational_store is not None
        assert rag.vector_store is None
        assert rag.vector_available is False

        rag.close()

    def test_store_document_extracts_metrics(self):
        """Test store_document extracts structured metrics"""
        rag = HybridRAG(
            vector_store=None,
            relational_store=RelationalStore(db_path=":memory:")
        )

        # Store test result
        rag.store_document(
            content="Test suite passed",
            doc_type="test_result",
            metadata={
                "run_id": "test-1",
                "agent_type": "qa",
                "tests_passed": 10,
                "tests_failed": 2,
                "timestamp": "2025-01-01T00:00:00"
            }
        )

        # Query metrics
        metrics = rag.relational_store.query_metrics(
            agent_type="qa",
            metric_type="test_result"
        )

        assert len(metrics) > 0
        # Pass rate should be 10/12 = 0.833...
        assert 0.83 <= metrics[0].metric_value <= 0.84

        rag.close()

    def test_structured_query_detection(self):
        """Test structured query detection"""
        rag = HybridRAG(
            vector_store=None,
            relational_store=RelationalStore(db_path=":memory:")
        )

        # Structured queries
        assert rag._is_structured_query("What's the latest coverage?")
        assert rag._is_structured_query("Get the pass rate")
        assert rag._is_structured_query("How many tests failed?")
        assert rag._is_structured_query("Show me the average metric")

        # Semantic queries
        assert not rag._is_structured_query("Find similar timeout errors")
        assert not rag._is_structured_query("Show accessibility patterns")
        assert not rag._is_structured_query("What caused this failure?")

        rag.close()

    def test_search_relational_coverage(self):
        """Test searching for coverage metrics"""
        rag = HybridRAG(
            vector_store=None,
            relational_store=RelationalStore(db_path=":memory:")
        )

        # Store coverage metric
        rag.relational_store.store_metric(
            run_id="test-1",
            agent_type="qa",
            metric_type="coverage",
            metric_name="line_coverage",
            metric_value=87.5,
            timestamp="2025-01-01T00:00:00"
        )

        # Search for coverage
        results = rag.search("what's the coverage", "qa", prefer_relational=True)

        assert len(results) > 0
        assert results[0].source == 'relational'
        assert '87.5%' in results[0].content

        rag.close()

    def test_augment_agent_context(self):
        """Test augmenting agent context with metrics"""
        rag = HybridRAG(
            vector_store=None,
            relational_store=RelationalStore(db_path=":memory:")
        )

        # Store some metrics
        rag.relational_store.store_metric(
            run_id="test-1",
            agent_type="qa",
            metric_type="coverage",
            metric_name="line_coverage",
            metric_value=87.5
        )

        rag.relational_store.store_execution(
            run_id="test-1",
            agent_type="qa",
            action="run_tests",
            outcome="success",
            success=True
        )

        # Augment context
        context = {"query": "test execution"}
        augmented = rag.augment_agent_context("qa", context)

        assert 'structured_metrics' in augmented
        assert 'recent_coverage' in augmented['structured_metrics']
        assert 'success_rate' in augmented['structured_metrics']

        rag.close()

    def test_log_agent_execution(self):
        """Test logging agent execution (MultiAgentRAG compatibility)"""
        rag = HybridRAG(
            vector_store=None,
            relational_store=RelationalStore(db_path=":memory:")
        )

        # Log execution (same interface as MultiAgentRAG)
        rag.log_agent_execution("qa", {
            "doc_type": "test_result",
            "content": "Tests passed",
            "run_id": "test-1",
            "tests_passed": 10,
            "tests_failed": 0,
            "timestamp": "2025-01-01T00:00:00"
        })

        # Verify metric was stored
        metrics = rag.relational_store.query_metrics(
            agent_type="qa",
            metric_type="test_result"
        )

        assert len(metrics) > 0
        assert metrics[0].metric_value == 1.0  # 100% pass rate

        rag.close()

    def test_fallback_resilience(self):
        """Test system continues when vector DB unavailable"""
        # Simulate vector DB unavailable
        rag = HybridRAG(
            vector_store=None,  # Vector DB unavailable
            relational_store=RelationalStore(db_path=":memory:")
        )

        # Should still work with relational only
        rag.store_document("Test", "test_result", {
            "run_id": "test-1",
            "agent_type": "qa",
            "tests_passed": 10,
            "tests_failed": 0
        })

        # Search should work (falls back to relational)
        results = rag.search("test results", "qa")
        assert isinstance(results, list)  # Graceful degradation

        rag.close()


class TestConfigIntegration:
    """Test config integration with hybrid RAG"""

    def test_hybrid_rag_enabled_detection(self):
        """Test detection of hybrid RAG mode from environment"""
        from agenticqa.rag.config import RAGConfig

        # Test with enabled
        os.environ['AGENTICQA_HYBRID_RAG'] = 'true'
        assert RAGConfig.is_hybrid_rag_enabled() is True

        # Test with disabled
        os.environ['AGENTICQA_HYBRID_RAG'] = 'false'
        assert RAGConfig.is_hybrid_rag_enabled() is False

        # Clean up
        if 'AGENTICQA_HYBRID_RAG' in os.environ:
            del os.environ['AGENTICQA_HYBRID_RAG']

    def test_use_postgresql_detection(self):
        """Test detection of PostgreSQL mode from environment"""
        from agenticqa.rag.config import RAGConfig

        # Test with enabled
        os.environ['AGENTICQA_USE_POSTGRESQL'] = 'true'
        assert RAGConfig.use_postgresql() is True

        # Test with disabled
        os.environ['AGENTICQA_USE_POSTGRESQL'] = 'false'
        assert RAGConfig.use_postgresql() is False

        # Clean up
        if 'AGENTICQA_USE_POSTGRESQL' in os.environ:
            del os.environ['AGENTICQA_USE_POSTGRESQL']


if __name__ == "__main__":
    # Run tests
    pytest.main([__file__, "-v"])
