"""
Tests for Neo4j Delegation Tracking

Tests the graph-based delegation storage and GraphRAG capabilities.
"""

import pytest
import os
import uuid
from datetime import datetime

pytestmark = pytest.mark.integration


@pytest.fixture
def neo4j_store():
    """
    Fixture for Neo4j store with test database.

    Requires Neo4j to be running. Skip tests if not available.
    """
    try:
        from agenticqa.graph import DelegationGraphStore

        # Use test database or main database
        store = DelegationGraphStore(
            uri=os.getenv("NEO4J_URI", "bolt://localhost:7687"),
            user=os.getenv("NEO4J_USER", "neo4j"),
            password=os.getenv("NEO4J_PASSWORD", "agenticqa123")
        )

        store.connect()

        # Initialize schema
        store.initialize_schema()

        yield store

        # Cleanup: Clear test data
        store.clear_all_data()
        store.close()

    except Exception as e:
        pytest.skip(f"Neo4j not available: {e}")


class TestNeo4jBasicOperations:
    """Test basic Neo4j operations"""

    def test_connection(self, neo4j_store):
        """Test Neo4j connection"""
        assert neo4j_store._connected is True
        print("✓ Neo4j connection successful")

    def test_create_agent(self, neo4j_store):
        """Test creating agent nodes"""
        agent = neo4j_store.create_or_update_agent("SDET_Agent", "qa")

        assert agent["name"] == "SDET_Agent"
        assert agent["type"] == "qa"
        print("✓ Agent node created")

    def test_record_delegation(self, neo4j_store):
        """Test recording a delegation"""
        # Create agents first
        neo4j_store.create_or_update_agent("SDET_Agent", "qa")
        neo4j_store.create_or_update_agent("SRE_Agent", "devops")

        # Record delegation
        delegation_id = str(uuid.uuid4())
        task = {
            "task_type": "generate_tests",
            "file": "src/api.py"
        }

        result_id = neo4j_store.record_delegation(
            from_agent="SDET_Agent",
            to_agent="SRE_Agent",
            task=task,
            delegation_id=delegation_id,
            depth=1
        )

        assert result_id == delegation_id
        print("✓ Delegation recorded")

    def test_update_delegation_result(self, neo4j_store):
        """Test updating delegation with result"""
        # Setup
        neo4j_store.create_or_update_agent("SDET_Agent", "qa")
        neo4j_store.create_or_update_agent("SRE_Agent", "devops")

        delegation_id = str(uuid.uuid4())
        neo4j_store.record_delegation(
            from_agent="SDET_Agent",
            to_agent="SRE_Agent",
            task={"task_type": "test"},
            delegation_id=delegation_id,
            depth=1
        )

        # Update with result
        neo4j_store.update_delegation_result(
            delegation_id=delegation_id,
            status="success",
            duration_ms=123.5,
            result={"tests_generated": 5}
        )

        print("✓ Delegation result updated")


class TestNeo4jAnalytics:
    """Test Neo4j analytics queries"""

    def test_most_delegated_agents(self, neo4j_store):
        """Test finding most delegated-to agents"""
        # Setup: Create multiple delegations
        neo4j_store.create_or_update_agent("SDET_Agent", "qa")
        neo4j_store.create_or_update_agent("SRE_Agent", "devops")
        neo4j_store.create_or_update_agent("Fullstack_Agent", "devops")

        # Create delegations: SDET -> SRE (3 times)
        for i in range(3):
            delegation_id = str(uuid.uuid4())
            neo4j_store.record_delegation(
                from_agent="SDET_Agent",
                to_agent="SRE_Agent",
                task={"task_type": f"test_{i}"},
                delegation_id=delegation_id,
                depth=1
            )
            neo4j_store.update_delegation_result(
                delegation_id=delegation_id,
                status="success",
                duration_ms=100.0 + i * 10
            )

        # Query
        results = neo4j_store.get_most_delegated_agents(limit=5)

        assert len(results) > 0
        assert results[0]["agent"] == "SRE_Agent"
        assert results[0]["delegation_count"] == 3
        print(f"✓ Most delegated agent: {results[0]['agent']} ({results[0]['delegation_count']} delegations)")

    def test_delegation_chains(self, neo4j_store):
        """Test finding delegation chains"""
        # Setup: Create chain SDET -> SRE -> QA
        agents = ["SDET_Agent", "SRE_Agent", "QA_Agent"]
        for agent in agents:
            neo4j_store.create_or_update_agent(agent, "qa")

        # Create chain
        delegations = [
            ("SDET_Agent", "SRE_Agent"),
            ("SRE_Agent", "QA_Agent")
        ]

        for i, (from_agent, to_agent) in enumerate(delegations):
            delegation_id = str(uuid.uuid4())
            neo4j_store.record_delegation(
                from_agent=from_agent,
                to_agent=to_agent,
                task={"task_type": "chain_test"},
                delegation_id=delegation_id,
                depth=i + 1
            )
            neo4j_store.update_delegation_result(
                delegation_id=delegation_id,
                status="success",
                duration_ms=100.0
            )

        # Query chains
        results = neo4j_store.find_delegation_chains(min_length=2, limit=10)

        assert len(results) > 0
        assert results[0]["chain_length"] >= 2
        print(f"✓ Found delegation chain of length {results[0]['chain_length']}")

    def test_circular_delegations(self, neo4j_store):
        """Test circular delegation detection"""
        results = neo4j_store.find_circular_delegations()

        # Should be empty (guardrails prevent this)
        assert len(results) == 0
        print("✓ No circular delegations detected (as expected)")

    def test_success_rates(self, neo4j_store):
        """Test delegation success rate calculations"""
        # Setup
        neo4j_store.create_or_update_agent("SDET_Agent", "qa")
        neo4j_store.create_or_update_agent("SRE_Agent", "devops")

        # Create 5 delegations: 4 success, 1 failure
        for i in range(5):
            delegation_id = str(uuid.uuid4())
            neo4j_store.record_delegation(
                from_agent="SDET_Agent",
                to_agent="SRE_Agent",
                task={"task_type": f"test_{i}"},
                delegation_id=delegation_id,
                depth=1
            )
            status = "success" if i < 4 else "failed"
            neo4j_store.update_delegation_result(
                delegation_id=delegation_id,
                status=status,
                duration_ms=100.0
            )

        # Query success rates
        results = neo4j_store.get_delegation_success_rate_by_pair(limit=10)

        assert len(results) > 0
        pair = results[0]
        assert pair["from_agent"] == "SDET_Agent"
        assert pair["to_agent"] == "SRE_Agent"
        assert pair["total"] == 5
        assert pair["successes"] == 4
        assert abs(pair["success_rate"] - 0.8) < 0.01  # 80% success rate
        print(f"✓ Success rate calculated: {pair['success_rate'] * 100:.0f}%")


class TestGraphRAG:
    """Test GraphRAG capabilities"""

    def test_recommend_delegation_target(self, neo4j_store):
        """Test GraphRAG delegation recommendation"""
        # Setup: Create historical successful delegations
        neo4j_store.create_or_update_agent("SDET_Agent", "qa")
        neo4j_store.create_or_update_agent("SRE_Agent", "devops")

        # Create 5 successful delegations for "generate_tests" task
        for i in range(5):
            delegation_id = str(uuid.uuid4())
            neo4j_store.record_delegation(
                from_agent="SDET_Agent",
                to_agent="SRE_Agent",
                task={"task_type": "generate_tests"},
                delegation_id=delegation_id,
                depth=1
            )
            neo4j_store.update_delegation_result(
                delegation_id=delegation_id,
                status="success",
                duration_ms=200.0 + i * 10
            )

        # Get recommendation
        recommendation = neo4j_store.recommend_delegation_target(
            from_agent="SDET_Agent",
            task_type="generate_tests",
            acceptable_duration_ms=5000.0,
            min_success_count=3
        )

        assert recommendation is not None
        assert recommendation["recommended_agent"] == "SRE_Agent"
        assert recommendation["success_count"] >= 3
        print(f"✓ GraphRAG recommendation: {recommendation['recommended_agent']} (confidence based on {recommendation['success_count']} successes)")

    def test_get_delegation_history(self, neo4j_store):
        """Test retrieving delegation history for task type"""
        # Setup
        neo4j_store.create_or_update_agent("Fullstack_Agent", "devops")
        neo4j_store.create_or_update_agent("Compliance_Agent", "compliance")

        # Create delegations
        for i in range(3):
            delegation_id = str(uuid.uuid4())
            neo4j_store.record_delegation(
                from_agent="Fullstack_Agent",
                to_agent="Compliance_Agent",
                task={"task_type": "code_validation"},
                delegation_id=delegation_id,
                depth=1
            )
            neo4j_store.update_delegation_result(
                delegation_id=delegation_id,
                status="success",
                duration_ms=150.0
            )

        # Get history
        history = neo4j_store.get_delegation_history_for_task(
            task_type="code_validation",
            status="success",
            limit=5
        )

        assert len(history) == 3
        assert history[0]["from_agent"] == "Fullstack_Agent"
        assert history[0]["to_agent"] == "Compliance_Agent"
        print(f"✓ Retrieved {len(history)} historical delegations")


class TestDatabaseStats:
    """Test database statistics and utilities"""

    def test_get_database_stats(self, neo4j_store):
        """Test retrieving database statistics"""
        # Create some test data
        neo4j_store.create_or_update_agent("Test_Agent_1", "qa")
        neo4j_store.create_or_update_agent("Test_Agent_2", "devops")

        delegation_id = str(uuid.uuid4())
        neo4j_store.record_delegation(
            from_agent="Test_Agent_1",
            to_agent="Test_Agent_2",
            task={"task_type": "test"},
            delegation_id=delegation_id,
            depth=1
        )

        # Get stats
        stats = neo4j_store.get_database_stats()

        assert stats["total_agents"] >= 2
        assert stats["total_delegations"] >= 1
        print(f"✓ Database stats: {stats['total_agents']} agents, {stats['total_delegations']} delegations")

    def test_get_agent_stats(self, neo4j_store):
        """Test retrieving stats for specific agent"""
        # Create agent and delegation
        neo4j_store.create_or_update_agent("SDET_Agent", "qa")
        neo4j_store.create_or_update_agent("SRE_Agent", "devops")

        delegation_id = str(uuid.uuid4())
        neo4j_store.record_delegation(
            from_agent="SDET_Agent",
            to_agent="SRE_Agent",
            task={"task_type": "test"},
            delegation_id=delegation_id,
            depth=1
        )

        # Get agent stats
        stats = neo4j_store.get_agent_stats("SDET_Agent")

        assert stats is not None
        assert stats["name"] == "SDET_Agent"
        assert stats["delegations_made"] >= 1
        print(f"✓ Agent stats retrieved for {stats['name']}")


def test_hybrid_rag_integration():
    """Test Hybrid GraphRAG integration (requires both Weaviate and Neo4j)"""
    try:
        from agenticqa.graph import create_hybrid_rag

        # This will try to connect to both systems
        hybrid_rag = create_hybrid_rag()

        assert hybrid_rag is not None
        print(f"✓ Hybrid RAG initialized (Weaviate: {hybrid_rag.weaviate_enabled}, Neo4j: {hybrid_rag.neo4j_enabled})")

    except Exception as e:
        pytest.skip(f"Hybrid RAG not available: {e}")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
