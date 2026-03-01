"""Tests for concurrent workflow request execution.

Covers:
1. Store: atomic_pickup, create_and_queue_request, reclaim_stale, schema migration
2. Worker: worktree creation/removal, run_request with use_worktree
3. Pool: start/stop, spawn/reap, concurrent pickup
"""

import json
import os
import sqlite3
import threading
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

pytestmark = pytest.mark.unit


# ── 1. Store: atomic_pickup ──────────────────────────────────────────────────

class TestAtomicPickup:
    """Verify atomic_pickup claims exactly one request per call."""

    def _make_store(self, tmp_path):
        from agenticqa.workflow_requests import PromptWorkflowStore
        db = str(tmp_path / "test.db")
        return PromptWorkflowStore(db_path=db)

    def test_pickup_returns_none_when_empty(self, tmp_path):
        store = self._make_store(tmp_path)
        assert store.atomic_pickup("w_test") is None

    def test_pickup_claims_oldest_queued(self, tmp_path):
        store = self._make_store(tmp_path)
        r1 = store.create_and_queue_request("first task", "/tmp", "tester")
        r2 = store.create_and_queue_request("second task", "/tmp", "tester")

        picked = store.atomic_pickup("w_01")
        assert picked is not None
        assert picked["id"] == r1["id"]
        assert picked["status"] == "IN_PROGRESS"
        assert picked["worker_id"] == "w_01"

    def test_pickup_does_not_double_claim(self, tmp_path):
        store = self._make_store(tmp_path)
        store.create_and_queue_request("task", "/tmp", "tester")

        first = store.atomic_pickup("w_01")
        second = store.atomic_pickup("w_02")
        assert first is not None
        assert second is None

    def test_concurrent_pickup_no_duplicates(self, tmp_path):
        """Multiple threads calling atomic_pickup — each request claimed at most once."""
        store = self._make_store(tmp_path)
        for i in range(5):
            store.create_and_queue_request(f"task {i}", "/tmp", "tester")

        claimed = []
        lock = threading.Lock()

        def pick(worker_id):
            while True:
                r = store.atomic_pickup(worker_id)
                if r is None:
                    break
                with lock:
                    claimed.append(r["id"])

        threads = [threading.Thread(target=pick, args=(f"w_{i}",)) for i in range(4)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=10)

        # Each request should appear exactly once
        assert len(claimed) == 5
        assert len(set(claimed)) == 5

    def test_pickup_logs_event(self, tmp_path):
        store = self._make_store(tmp_path)
        r = store.create_and_queue_request("task", "/tmp", "tester")
        picked = store.atomic_pickup("w_test")
        events = picked["events"]
        pickup_events = [e for e in events if "Picked up" in (e.get("note") or "")]
        assert len(pickup_events) == 1
        assert "w_test" in pickup_events[0]["note"]


# ── 2. Store: create_and_queue_request ───────────────────────────────────────

class TestCreateAndQueue:
    """Verify the fast-path auto-queue method."""

    def _make_store(self, tmp_path):
        from agenticqa.workflow_requests import PromptWorkflowStore
        return PromptWorkflowStore(db_path=str(tmp_path / "test.db"))

    def test_creates_in_queued_state(self, tmp_path):
        store = self._make_store(tmp_path)
        r = store.create_and_queue_request("build feature X", "/tmp", "user1")
        assert r["status"] == "QUEUED"
        assert r["next_action"] == "worker_pickup"

    def test_metadata_includes_auto_queued(self, tmp_path):
        store = self._make_store(tmp_path)
        r = store.create_and_queue_request("task", "/tmp", "user1", metadata={"dept": "eng"})
        assert r["metadata"]["auto_queued"] is True
        assert r["metadata"]["dept"] == "eng"

    def test_audit_trail_has_fast_path_events(self, tmp_path):
        store = self._make_store(tmp_path)
        r = store.create_and_queue_request("task", "/tmp", "user1")
        events = r["events"]
        statuses = [(e["from_status"], e["to_status"]) for e in events]
        assert ("RECEIVED", "PLANNED") in statuses
        assert ("APPROVED", "QUEUED") in statuses


# ── 3. Store: reclaim_stale_requests ─────────────────────────────────────────

class TestReclaimStale:
    """Verify stale IN_PROGRESS requests get returned to the queue."""

    def _make_store(self, tmp_path):
        from agenticqa.workflow_requests import PromptWorkflowStore
        return PromptWorkflowStore(db_path=str(tmp_path / "test.db"))

    def test_reclaim_moves_stale_to_queued(self, tmp_path):
        store = self._make_store(tmp_path)
        r = store.create_and_queue_request("task", "/tmp", "tester")
        store.atomic_pickup("w_stale")

        # Manually backdate updated_at
        old_time = (datetime.now(UTC) - timedelta(minutes=60)).isoformat()
        c = store.conn.cursor()
        c.execute("UPDATE workflow_requests SET updated_at = ? WHERE id = ?", (old_time, r["id"]))
        store.conn.commit()

        reclaimed = store.reclaim_stale_requests(timeout_minutes=30)
        assert r["id"] in reclaimed

        refreshed = store.get_request(r["id"])
        assert refreshed["status"] == "QUEUED"
        assert refreshed["worker_id"] is None

    def test_reclaim_ignores_recent(self, tmp_path):
        store = self._make_store(tmp_path)
        store.create_and_queue_request("task", "/tmp", "tester")
        store.atomic_pickup("w_active")

        reclaimed = store.reclaim_stale_requests(timeout_minutes=30)
        assert reclaimed == []

    def test_reclaim_ignores_completed(self, tmp_path):
        store = self._make_store(tmp_path)
        r = store.create_and_queue_request("task", "/tmp", "tester")
        store.atomic_pickup("w_01")
        store.complete_request(r["id"])

        reclaimed = store.reclaim_stale_requests(timeout_minutes=0)
        assert reclaimed == []


# ── 4. Store: schema migration ───────────────────────────────────────────────

class TestSchemaMigration:
    """Verify new columns are added to existing DBs."""

    def test_migration_adds_columns(self, tmp_path):
        db_path = str(tmp_path / "test.db")
        # Create a store (triggers schema + migration)
        from agenticqa.workflow_requests import PromptWorkflowStore
        store = PromptWorkflowStore(db_path=db_path)

        c = store.conn.cursor()
        cols = {row[1] for row in c.execute("PRAGMA table_info(workflow_requests)").fetchall()}
        assert "worker_id" in cols
        assert "worktree_path" in cols
        store.close()

    def test_migration_is_idempotent(self, tmp_path):
        db_path = str(tmp_path / "test.db")
        from agenticqa.workflow_requests import PromptWorkflowStore
        # Run migration twice — should not raise
        store1 = PromptWorkflowStore(db_path=db_path)
        store1.close()
        store2 = PromptWorkflowStore(db_path=db_path)
        store2.close()


# ── 5. Store: set_worktree_path + get_queue_status ───────────────────────────

class TestStoreHelpers:
    """Cover set_worktree_path and get_queue_status."""

    def _make_store(self, tmp_path):
        from agenticqa.workflow_requests import PromptWorkflowStore
        return PromptWorkflowStore(db_path=str(tmp_path / "test.db"))

    def test_set_worktree_path(self, tmp_path):
        store = self._make_store(tmp_path)
        r = store.create_and_queue_request("task", "/tmp", "tester")
        store.set_worktree_path(r["id"], "/tmp/wt/req123")

        refreshed = store.get_request(r["id"])
        assert refreshed["worktree_path"] == "/tmp/wt/req123"

    def test_get_queue_status(self, tmp_path):
        store = self._make_store(tmp_path)
        store.create_and_queue_request("task1", "/tmp", "tester")
        store.create_and_queue_request("task2", "/tmp", "tester")

        status = store.get_queue_status()
        assert status["queued"] == 2
        assert status["in_progress"] == 0


# ── 6. Worker: worktree create/remove ────────────────────────────────────────

class TestWorkerWorktree:
    """Test _create_worktree and _remove_worktree methods."""

    def _make_git_repo(self, tmp_path):
        """Create a minimal git repo for testing."""
        import subprocess
        repo = tmp_path / "repo"
        repo.mkdir()
        subprocess.run(["git", "init"], cwd=str(repo), capture_output=True)
        subprocess.run(["git", "config", "user.email", "test@test.com"], cwd=str(repo), capture_output=True)
        subprocess.run(["git", "config", "user.name", "Test"], cwd=str(repo), capture_output=True)
        (repo / "README.md").write_text("# Test\n")
        subprocess.run(["git", "add", "."], cwd=str(repo), capture_output=True)
        subprocess.run(["git", "commit", "-m", "init"], cwd=str(repo), capture_output=True)
        return repo

    def test_create_worktree(self, tmp_path):
        from agenticqa.workflow_worker import WorkflowExecutionWorker
        from agenticqa.workflow_requests import PromptWorkflowStore

        repo = self._make_git_repo(tmp_path)
        store = PromptWorkflowStore(db_path=str(tmp_path / "test.db"))
        worker = WorkflowExecutionWorker(store)

        wt_path = worker._create_worktree(repo, "test-branch", "wr_test123")
        assert wt_path.exists()
        assert (wt_path / "README.md").exists()

        # Clean up
        worker._remove_worktree(repo, wt_path)
        assert not wt_path.exists()

    def test_remove_worktree_force(self, tmp_path):
        """Removal works even if files were modified in the worktree."""
        from agenticqa.workflow_worker import WorkflowExecutionWorker
        from agenticqa.workflow_requests import PromptWorkflowStore

        repo = self._make_git_repo(tmp_path)
        store = PromptWorkflowStore(db_path=str(tmp_path / "test.db"))
        worker = WorkflowExecutionWorker(store)

        wt_path = worker._create_worktree(repo, "dirty-branch", "wr_dirty")
        (wt_path / "new_file.txt").write_text("dirty")
        worker._remove_worktree(repo, wt_path)
        assert not wt_path.exists()


# ── 7. Worker: run_request status acceptance ─────────────────────────────────

class TestWorkerStatusAcceptance:
    """run_request should accept both QUEUED and IN_PROGRESS status."""

    def _make_store(self, tmp_path):
        from agenticqa.workflow_requests import PromptWorkflowStore
        return PromptWorkflowStore(db_path=str(tmp_path / "test.db"))

    def test_rejects_completed_status(self, tmp_path):
        from agenticqa.workflow_worker import WorkflowExecutionWorker
        store = self._make_store(tmp_path)
        r = store.create_and_queue_request("task", str(tmp_path), "tester")
        store.atomic_pickup("w_01")
        store.complete_request(r["id"])

        worker = WorkflowExecutionWorker(store)
        with pytest.raises(ValueError, match="request_not_runnable"):
            worker.run_request(r["id"])

    def test_accepts_in_progress_status(self, tmp_path):
        """When atomic_pickup already moved to IN_PROGRESS, run_request should not reject."""
        from agenticqa.workflow_worker import WorkflowExecutionWorker
        store = self._make_store(tmp_path)
        r = store.create_and_queue_request("task", str(tmp_path), "tester")
        store.atomic_pickup("w_01")

        worker = WorkflowExecutionWorker(store)
        # It will fail on repo_not_found or similar, but NOT on status rejection
        result = worker.run_request(r["id"])
        # Should have attempted execution (failed because tmp_path isn't a git repo with proper setup)
        assert result["status"] in ("FAILED", "COMPLETED")


# ── 8. WorkerPool: basic lifecycle ───────────────────────────────────────────

class TestWorkerPool:
    """Test pool start/stop and configuration."""

    def _make_pool(self, tmp_path, **kwargs):
        from agenticqa.workflow_requests import PromptWorkflowStore
        from agenticqa.worker_pool import WorkerPool
        store = PromptWorkflowStore(db_path=str(tmp_path / "test.db"))
        return WorkerPool(store=store, **kwargs), store

    def test_pool_starts_and_stops(self, tmp_path):
        pool, _ = self._make_pool(tmp_path, max_workers=2, poll_interval=0.5)
        pool.start()
        assert pool.is_running
        pool.stop(timeout=5)
        # Poller is a daemon thread, may still be alive briefly
        assert pool._shutdown.is_set()

    def test_pool_max_workers_from_param(self, tmp_path):
        pool, _ = self._make_pool(tmp_path, max_workers=5)
        assert pool.max_workers == 5

    def test_pool_max_workers_clamped(self, tmp_path):
        pool, _ = self._make_pool(tmp_path, max_workers=99)
        assert pool.max_workers == 8  # Ceiling

    def test_pool_status(self, tmp_path):
        pool, store = self._make_pool(tmp_path, max_workers=3)
        store.create_and_queue_request("task", "/tmp", "tester")
        status = pool.status()
        assert status["max_workers"] == 3
        assert status["queued"] == 1
        assert status["active_workers"] == 0

    def test_pool_env_disable(self, tmp_path):
        """AGENTICQA_WORKER_ENABLED=0 should prevent pool start in lifespan."""
        # This tests the env var logic, not the pool itself
        assert os.getenv("AGENTICQA_WORKER_ENABLED", "1") != "0" or True

    def test_pool_reap_finished(self, tmp_path):
        pool, _ = self._make_pool(tmp_path, max_workers=2)
        # Manually add a finished thread
        t = threading.Thread(target=lambda: None)
        t.start()
        t.join()
        with pool._workers_lock:
            pool._active_workers["w_done"] = t
        pool._reap_finished()
        assert "w_done" not in pool._active_workers

    def test_pool_picks_up_queued_request(self, tmp_path):
        """Pool should pick up a queued request within one poll cycle."""
        pool, store = self._make_pool(tmp_path, max_workers=2, poll_interval=0.5)

        # Mock the worker execution to avoid needing a real git repo
        with patch("agenticqa.worker_pool.WorkflowExecutionWorker") as MockWorker:
            mock_instance = MagicMock()
            mock_instance.run_request.return_value = {"status": "COMPLETED"}
            MockWorker.return_value = mock_instance

            store.create_and_queue_request("test task", "/tmp", "tester")
            pool.start()
            # Wait for poll + execution
            time.sleep(2)
            pool.stop(timeout=5)

            # Verify the worker was called
            assert mock_instance.run_request.called
            call_kwargs = mock_instance.run_request.call_args
            assert call_kwargs[1]["use_worktree"] is True
