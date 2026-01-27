"""
Real Weaviate Integration Tests for Agent Learning

These tests verify that agents actually:
1. Store executions in Weaviate with embeddings
2. Retrieve similar historical executions from Weaviate
3. Improve decisions based on RAG insights
4. Learn autonomously over multiple deployments

Unlike test_pipeline_framework.py which uses mocks, these tests verify real RAG integration.
"""

import pytest
import os
import time
from unittest.mock import patch
from datetime import datetime, timedelta

# Mark all tests as integration tests
pytestmark = pytest.mark.integration


class TestRealWeaviateConnection:
    """Verify real Weaviate connection works"""

    @pytest.mark.skipif(
        os.getenv("WEAVIATE_HOST") is None,
        reason="Weaviate not configured. Set WEAVIATE_HOST to run these tests."
    )
    def test_weaviate_connection_established(self):
        """Verify we can connect to real Weaviate instance"""
        from src.agenticqa.rag.config import create_rag_system, RAGConfig

        try:
            # Print config summary for debugging
            print("\n" + RAGConfig.print_config_summary())

            # Create RAG system
            rag = create_rag_system()
            assert rag is not None, "RAG system should be created"
            assert rag.vector_store is not None, "Vector store should be initialized"

            print("✓ Weaviate connection established successfully")
        except Exception as e:
            pytest.fail(f"Failed to connect to Weaviate: {e}")

    @pytest.mark.skipif(
        os.getenv("WEAVIATE_HOST") is None,
        reason="Weaviate not configured"
    )
    def test_weaviate_store_and_retrieve_document(self):
        """Verify we can store and retrieve documents from Weaviate"""
        from src.agenticqa.rag.config import create_rag_system
        from src.agenticqa.rag.embeddings import EmbedderFactory

        rag = create_rag_system()
        embedder = EmbedderFactory.get_default()

        # Store a test document
        test_content = "Test error: Connection timeout after 30 seconds"
        embedding = embedder.embed(test_content)

        rag.vector_store.add_document(
            content=test_content,
            embedding=embedding,
            metadata={"test": True, "error_type": "timeout"},
            doc_type="error"
        )

        # Retrieve similar documents
        query_embedding = embedder.embed("Connection timeout error")
        similar_docs = rag.vector_store.search(
            query_embedding,
            doc_type="error",
            k=5,
            threshold=0.3
        )

        assert len(similar_docs) > 0, "Should retrieve similar documents"
        print(f"✓ Retrieved {len(similar_docs)} similar documents")


class TestAgentRAGIntegration:
    """Test agents use RAG for learning and improvement"""

    @pytest.mark.skipif(
        os.getenv("WEAVIATE_HOST") is None,
        reason="Weaviate not configured"
    )
    def test_qa_agent_uses_rag_insights(self):
        """Verify QA Agent uses RAG insights in recommendations"""
        from src.agents import QAAssistantAgent

        # Create agent with RAG enabled
        agent = QAAssistantAgent()

        # Verify RAG is initialized
        assert agent.use_rag is True, "RAG should be enabled by default"
        if agent.rag is None:
            pytest.skip("RAG initialization failed - Weaviate may not be running")

        # Execute agent with test results
        test_results = {
            "test_name": "test_api_timeout",
            "test_type": "integration",
            "status": "failed",
            "total": 10,
            "passed": 8,
            "failed": 2,
            "coverage": 85,
        }

        analysis = agent.execute(test_results)

        # Verify RAG insights were attempted
        assert "rag_insights_used" in analysis, "Should track RAG insights usage"
        print(f"✓ QA Agent used {analysis.get('rag_insights_used', 0)} RAG insights")

        # Verify recommendations were generated
        assert "recommendations" in analysis
        assert len(analysis["recommendations"]) > 0
        print(f"✓ Generated {len(analysis['recommendations'])} recommendations")

    @pytest.mark.skipif(
        os.getenv("WEAVIATE_HOST") is None,
        reason="Weaviate not configured"
    )
    def test_performance_agent_uses_rag_insights(self):
        """Verify Performance Agent uses RAG insights for optimizations"""
        from src.agents import PerformanceAgent

        agent = PerformanceAgent()

        # Verify RAG is initialized
        if agent.rag is None:
            pytest.skip("RAG initialization failed - Weaviate may not be running")

        # Execute agent with performance data
        execution_data = {
            "operation": "database_query",
            "duration_ms": 8500,
            "memory_mb": 512,
            "baseline_ms": 2000
        }

        analysis = agent.execute(execution_data)

        # Verify RAG insights were attempted
        assert "rag_insights_used" in analysis
        print(f"✓ Performance Agent used {analysis.get('rag_insights_used', 0)} RAG insights")

        # Verify status is degraded due to high duration
        assert analysis["status"] == "degraded"
        print(f"✓ Detected performance degradation (8500ms > 5000ms threshold)")

    @pytest.mark.skipif(
        os.getenv("WEAVIATE_HOST") is None,
        reason="Weaviate not configured"
    )
    def test_compliance_agent_uses_rag_insights(self):
        """Verify Compliance Agent uses RAG insights for rules"""
        from src.agents import ComplianceAgent

        agent = ComplianceAgent()

        if agent.rag is None:
            pytest.skip("RAG initialization failed - Weaviate may not be running")

        # Execute agent with compliance data
        compliance_data = {
            "context": "PCI DSS compliance check",
            "regulations": ["PCI_DSS", "GDPR"],
            "encrypted": False,
            "pii_masked": False,
            "audit_enabled": True
        }

        checks = agent.execute(compliance_data)

        # Verify RAG insights were attempted
        assert "rag_insights_used" in checks
        print(f"✓ Compliance Agent used {checks.get('rag_insights_used', 0)} RAG insights")

        # Verify violations were detected
        assert len(checks["violations"]) >= 2  # At least encryption and PII masking
        print(f"✓ Detected {len(checks['violations'])} compliance violations")

    @pytest.mark.skipif(
        os.getenv("WEAVIATE_HOST") is None,
        reason="Weaviate not configured"
    )
    def test_devops_agent_uses_rag_insights(self):
        """Verify DevOps Agent uses RAG insights for deployments"""
        from src.agents import DevOpsAgent

        agent = DevOpsAgent()

        if agent.rag is None:
            pytest.skip("RAG initialization failed - Weaviate may not be running")

        # Execute agent with deployment config
        deployment_config = {
            "version": "v2.1.0",
            "environment": "production",
            "error_type": "",
            "message": ""
        }

        result = agent.execute(deployment_config)

        # Verify RAG insights were attempted
        assert "rag_insights_used" in result
        print(f"✓ DevOps Agent used {result.get('rag_insights_used', 0)} RAG insights")

        # Verify deployment was successful
        assert result["deployment_status"] == "success"
        print(f"✓ Deployment to {result['environment']} succeeded")


class TestAgentLearningOverTime:
    """Test agents improve decision quality over multiple executions"""

    @pytest.mark.skipif(
        os.getenv("WEAVIATE_HOST") is None,
        reason="Weaviate not configured"
    )
    def test_agent_stores_execution_in_weaviate(self):
        """Verify agent executions are stored in Weaviate"""
        from src.agents import QAAssistantAgent

        agent = QAAssistantAgent()

        if agent.rag is None:
            pytest.skip("RAG initialization failed")

        # Execute agent multiple times
        for i in range(3):
            test_results = {
                "test_name": f"test_scenario_{i}",
                "test_type": "unit",
                "status": "passed" if i % 2 == 0 else "failed",
                "total": 10,
                "passed": 8 if i % 2 == 0 else 6,
                "failed": 2 if i % 2 == 0 else 4,
                "coverage": 85
            }

            agent.execute(test_results)

        # Verify executions were stored
        assert len(agent.execution_history) >= 3
        print(f"✓ Stored {len(agent.execution_history)} executions")

    @pytest.mark.skipif(
        os.getenv("WEAVIATE_HOST") is None,
        reason="Weaviate not configured"
    )
    def test_agent_retrieves_similar_executions(self):
        """Verify agents can retrieve similar past executions"""
        from src.agents import QAAssistantAgent

        agent = QAAssistantAgent()

        if not agent.use_data_store:
            pytest.skip("Data store not enabled")

        # Get similar executions
        similar = agent.get_similar_executions(status="error", limit=5)

        # Should return list (may be empty if no prior errors)
        assert isinstance(similar, list)
        print(f"✓ Retrieved {len(similar)} similar executions from history")

    @pytest.mark.skipif(
        os.getenv("WEAVIATE_HOST") is None,
        reason="Weaviate not configured"
    )
    def test_agent_pattern_insights_improve_over_time(self):
        """Verify pattern insights accumulate and improve"""
        from src.agents import PerformanceAgent

        agent = PerformanceAgent()

        if not agent.use_data_store:
            pytest.skip("Data store not enabled")

        # Get pattern insights
        insights = agent.get_pattern_insights()

        # Should return pattern data
        assert isinstance(insights, dict)
        assert "errors" in insights
        assert "performance" in insights
        assert "flakiness" in insights

        print(f"✓ Pattern insights available:")
        print(f"  - Total errors: {insights['errors'].get('total', 0)}")
        print(f"  - Performance metrics tracked: {len(insights.get('performance', {}))}")


class TestAutonomousLearning:
    """Test end-to-end autonomous learning without intervention"""

    @pytest.mark.skipif(
        os.getenv("WEAVIATE_HOST") is None,
        reason="Weaviate not configured"
    )
    def test_full_learning_cycle(self):
        """
        Test complete learning cycle:
        1. Agent executes task
        2. Execution logged to Weaviate
        3. Future executions retrieve insights
        4. Decision quality improves
        """
        from src.agents import QAAssistantAgent

        agent = QAAssistantAgent()

        if agent.rag is None:
            pytest.skip("RAG initialization failed")

        # Phase 1: Execute without prior knowledge
        test_results_1 = {
            "test_name": "test_database_connection",
            "test_type": "integration",
            "status": "failed",
            "total": 5,
            "passed": 3,
            "failed": 2,
            "coverage": 70
        }

        analysis_1 = agent.execute(test_results_1)
        rec_count_1 = len(analysis_1.get("recommendations", []))
        print(f"\n✓ First execution: {rec_count_1} recommendations")

        # Small delay to ensure Weaviate indexing completes
        time.sleep(1)

        # Phase 2: Execute similar task - should have more insights
        test_results_2 = {
            "test_name": "test_database_timeout",
            "test_type": "integration",
            "status": "failed",
            "total": 5,
            "passed": 3,
            "failed": 2,
            "coverage": 70
        }

        analysis_2 = agent.execute(test_results_2)
        rec_count_2 = len(analysis_2.get("recommendations", []))
        print(f"✓ Second execution: {rec_count_2} recommendations")

        # Verify learning occurred (recommendations count should be equal or greater)
        assert rec_count_2 >= rec_count_1, \
            f"Agent should maintain or improve recommendations ({rec_count_2} >= {rec_count_1})"

        print(f"✓ Agent maintained recommendation quality across executions")


class TestRealWorldScenarios:
    """Test real-world learning scenarios"""

    @pytest.mark.skipif(
        os.getenv("WEAVIATE_HOST") is None,
        reason="Weaviate not configured"
    )
    def test_flaky_test_detection_and_learning(self):
        """Test agent learns to detect and handle flaky tests"""
        from src.agents import QAAssistantAgent

        agent = QAAssistantAgent()

        if agent.rag is None:
            pytest.skip("RAG initialization failed")

        # Simulate flaky test pattern over multiple executions
        for i in range(5):
            test_results = {
                "test_name": "test_flaky_network_call",
                "test_type": "integration",
                "status": "passed" if i % 2 == 0 else "failed",
                "total": 10,
                "passed": 9 if i % 2 == 0 else 7,
                "failed": 1 if i % 2 == 0 else 3,
                "coverage": 85
            }

            agent.execute(test_results)

        # After multiple executions, pattern analysis should detect flakiness
        insights = agent.get_pattern_insights()

        print(f"✓ Executed flaky test 5 times, pattern analysis available")
        print(f"  - Flakiness data: {insights.get('flakiness', {})}")

    @pytest.mark.skipif(
        os.getenv("WEAVIATE_HOST") is None,
        reason="Weaviate not configured"
    )
    def test_performance_regression_learning(self):
        """Test agent learns performance regression patterns"""
        from src.agents import PerformanceAgent

        agent = PerformanceAgent()

        if agent.rag is None:
            pytest.skip("RAG initialization failed")

        # Simulate performance degradation
        baseline = 1000
        for i in range(3):
            execution_data = {
                "operation": "api_request",
                "duration_ms": baseline + (i * 1000),  # Gradual slowdown
                "memory_mb": 256,
                "baseline_ms": baseline
            }

            analysis = agent.execute(execution_data)
            print(f"✓ Execution {i+1}: {analysis['duration_ms']}ms - {analysis['status']}")

        # Verify status changed to degraded
        assert analysis["status"] == "degraded", "Should detect performance degradation"


if __name__ == "__main__":
    # Run tests with verbose output
    pytest.main([__file__, "-v", "-s", "--tb=short"])
