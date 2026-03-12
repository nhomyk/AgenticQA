"""
Pipeline Snapshot Testing

Tests that capture snapshots of agent outputs, data store artifacts, and pipeline results
to ensure consistency and detect unintended changes in data quality.
"""

import pytest
from datetime import datetime, timezone
from agenticqa import AgentOrchestrator
from agenticqa.data_store import TestArtifactStore, SecureDataPipeline
from agenticqa.data_store.snapshot_manager import SnapshotManager


@pytest.fixture
def snapshot_manager(tmp_path):
    """Create snapshot manager for tests."""
    return SnapshotManager(str(tmp_path / ".snapshots" / "tests"))


@pytest.fixture
def test_data():
    """Standard test data for snapshot testing."""
    return {
        "code": """
def add(a, b):
    return a + b

def subtract(a, b):
    return a - b
        """,
        "tests": """
import pytest
def test_add():
    assert add(2, 3) == 5
    assert add(-1, 1) == 0

def test_subtract():
    assert subtract(5, 3) == 2
    assert subtract(0, 5) == -5
        """,
        "performance_baseline": {"execution_time_ms": 5.2},
    }


class TestAgentOutputSnapshots:
    """Test that agent outputs remain consistent across executions."""

    def test_qa_agent_output_snapshot(self, snapshot_manager, test_data):
        """Snapshot test for QA Agent output."""
        orchestrator = AgentOrchestrator()
        results = orchestrator.execute_all_agents(test_data)

        qa_output = results.get("qa", {})

        # Create or compare snapshot
        comparison = snapshot_manager.compare_snapshot("qa_agent_output", qa_output)

        if comparison["status"] == "new":
            snapshot_manager.create_snapshot("qa_agent_output", qa_output)
            assert True, "Snapshot created"
        else:
            assert comparison["matches"], f"QA Agent output changed: {comparison['differences']}"

    def test_performance_agent_snapshot(self, snapshot_manager, test_data):
        """Snapshot test for Performance Agent output."""
        orchestrator = AgentOrchestrator()
        results = orchestrator.execute_all_agents(test_data)

        perf_output = results.get("performance", {})

        comparison = snapshot_manager.compare_snapshot("performance_agent_output", perf_output)

        if comparison["status"] == "new":
            snapshot_manager.create_snapshot("performance_agent_output", perf_output)
        else:
            assert comparison[
                "matches"
            ], f"Performance Agent output changed: {comparison['differences']}"

    def test_compliance_agent_snapshot(self, snapshot_manager, test_data):
        """Snapshot test for Compliance Agent output."""
        orchestrator = AgentOrchestrator()
        results = orchestrator.execute_all_agents(test_data)

        compliance_output = results.get("compliance", {})

        comparison = snapshot_manager.compare_snapshot("compliance_agent_output", compliance_output)

        if comparison["status"] == "new":
            snapshot_manager.create_snapshot("compliance_agent_output", compliance_output)
        else:
            assert comparison[
                "matches"
            ], f"Compliance Agent output changed: {comparison['differences']}"

    def test_devops_agent_snapshot(self, snapshot_manager, test_data):
        """Snapshot test for DevOps Agent output."""
        orchestrator = AgentOrchestrator()
        results = orchestrator.execute_all_agents(test_data)

        devops_output = results.get("devops", {})

        comparison = snapshot_manager.compare_snapshot("devops_agent_output", devops_output)

        if comparison["status"] == "new":
            snapshot_manager.create_snapshot("devops_agent_output", devops_output)
        else:
            assert comparison[
                "matches"
            ], f"DevOps Agent output changed: {comparison['differences']}"


class TestDataStoreSnapshots:
    """Test that data store artifacts remain consistent."""

    def test_artifact_store_structure_snapshot(self, snapshot_manager, tmp_path):
        """Snapshot test for artifact store structure."""
        store = TestArtifactStore(str(tmp_path / ".test-artifact-store"))

        store_info = {
            "total_artifacts": len(store.master_index),
            "storage_dir": str(store.storage_dir),
            "index_keys": sorted(store.master_index.keys()),
        }

        comparison = snapshot_manager.compare_snapshot("datastore_structure", store_info)

        if comparison["status"] == "new":
            snapshot_manager.create_snapshot("datastore_structure", store_info)
        else:
            # Allow growth, but flag if structure changes unexpectedly
            assert comparison[
                "matches"
            ], f"Data store structure changed: {comparison['differences']}"

    def test_artifact_metadata_snapshot(self, snapshot_manager, tmp_path):
        """Snapshot test for artifact metadata consistency."""
        store = TestArtifactStore(str(tmp_path / ".test-artifact-store"))
        first_artifact_id = store.store_artifact(
            artifact_data={"status": "ok", "created_at": datetime.now(timezone.utc).isoformat()},
            artifact_type="execution",
            source="snapshot_test",
            tags=["snapshot"],
        )
        artifact_meta = store.master_index[first_artifact_id]

        comparison = snapshot_manager.compare_snapshot("artifact_metadata_schema", artifact_meta)

        if comparison["status"] == "new":
            snapshot_manager.create_snapshot("artifact_metadata_schema", artifact_meta)
        else:
            # Verify schema consistency
            assert "artifact_id" in artifact_meta, "Artifact missing 'artifact_id'"
            assert "timestamp" in artifact_meta, "Artifact missing 'timestamp'"
            assert "checksum" in artifact_meta, "Artifact missing 'checksum'"


class TestPipelineSnapshots:
    """Test that complete pipeline outputs remain consistent."""

    def test_pipeline_execution_snapshot(self, snapshot_manager, test_data):
        """Snapshot test for complete pipeline execution."""
        pipeline = SecureDataPipeline()
        execution_payload = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "agent_name": "qa_agent",
            "status": "passed",
            "output": test_data,
        }
        success, results = pipeline.execute_with_validation("qa_agent", execution_payload)
        assert success is True

        # Remove timestamp-based fields for stable snapshots
        snapshot_results = {
            k: v for k, v in results.items() if k not in ["timestamp", "execution_id"]
        }

        comparison = snapshot_manager.compare_snapshot("pipeline_execution", snapshot_results)

        if comparison["status"] == "new":
            snapshot_manager.create_snapshot("pipeline_execution", snapshot_results)
        else:
            assert comparison["matches"], f"Pipeline output changed: {comparison['differences']}"


class TestSnapshotManager:
    """Test the snapshot manager itself."""

    def test_snapshot_creation(self, snapshot_manager):
        """Test creating a snapshot."""
        test_data = {"key": "value", "number": 42}

        hash_value = snapshot_manager.create_snapshot("test_snapshot", test_data)

        assert hash_value is not None
        assert len(hash_value) == 64  # SHA256 hash length

    def test_snapshot_comparison_match(self, snapshot_manager):
        """Test comparing matching snapshots."""
        data = {"status": "passed", "score": 100}

        # Create initial snapshot
        snapshot_manager.create_snapshot("match_test", data)

        # Compare same data
        comparison = snapshot_manager.compare_snapshot("match_test", data)

        assert comparison["matches"] is True
        assert comparison["status"] == "match"

    def test_snapshot_comparison_mismatch(self, snapshot_manager):
        """Test comparing mismatched snapshots."""
        data1 = {"status": "passed", "score": 100}
        data2 = {"status": "passed", "score": 95}

        # Create initial snapshot
        snapshot_manager.create_snapshot("mismatch_test", data1)

        # Compare different data
        comparison = snapshot_manager.compare_snapshot("mismatch_test", data2)

        assert comparison["matches"] is False
        assert comparison["status"] == "mismatch"
        assert comparison["differences"] is not None

    def test_snapshot_retrieval(self, snapshot_manager):
        """Test retrieving all snapshots."""
        snapshot_manager.create_snapshot("snap1", {"data": 1})
        snapshot_manager.create_snapshot("snap2", {"data": 2})

        all_snapshots = snapshot_manager.get_all_snapshots()

        assert "snap1" in all_snapshots
        assert "snap2" in all_snapshots
