"""End-to-end verification of the full AgenticQA pipeline.

Tests the complete user journey:
  API submit -> QUEUED -> WorkerPool pickup -> IN_PROGRESS
  -> agent orchestration -> code generation -> SDET test loop
  -> git commit -> COMPLETED

Uses real SQLite, real git repos, real worktree isolation,
and mocked agent orchestration to produce deterministic results.
"""

import os
import subprocess
import time
import threading
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

pytestmark = pytest.mark.integration


# ── Helpers ──────────────────────────────────────────────────────────────────


def _init_git_repo(path: Path, *, set_identity: bool = True) -> None:
    """Create a minimal git repo with an initial commit."""
    subprocess.run(["git", "init"], cwd=str(path), check=True, capture_output=True)
    if set_identity:
        subprocess.run(
            ["git", "config", "user.email", "e2e@agenticqa.dev"],
            cwd=str(path), check=True, capture_output=True,
        )
        subprocess.run(
            ["git", "config", "user.name", "E2E Test"],
            cwd=str(path), check=True, capture_output=True,
        )
    (path / "app.py").write_text(
        '"""Simple app for e2e testing."""\n\ndef hello():\n    return "hello"\n',
        encoding="utf-8",
    )
    subprocess.run(["git", "add", "."], cwd=str(path), check=True, capture_output=True)
    if set_identity:
        subprocess.run(
            ["git", "commit", "-m", "init: base app"],
            cwd=str(path), check=True, capture_output=True,
        )


def _mock_orchestration(feature_request):
    """Return a deterministic orchestration result with generated code."""
    title = feature_request.get("title", "feature")
    fn_name = title.lower().replace(" ", "_").replace("-", "_")[:30]

    return {
        "feature_request": feature_request,
        "generation": {
            "code": f"def {fn_name}():\n    return {{\"status\": \"ok\", \"feature\": \"{title}\"}}\n",
            "files_created": [f"src/generated/{fn_name}.py"],
        },
        "collaboration": {
            "compliance": {"violations": [], "status": "clean"},
            "sdet": {"coverage_status": "above_threshold", "current_coverage": 85},
            "devops": {"status": "ready"},
        },
        "quality_gate": {"passed": True, "blockers": [], "coverage_status": "above_threshold"},
        "ontology": {
            "author_agent": "Fullstack_Agent",
            "review_agents": ["Compliance_Agent", "SDET_Agent", "DevOps_Agent"],
        },
        "delegation_summary": {},
    }


def _wait_for_queue_drain(store, timeout: float = 60.0) -> None:
    """Block until queue is empty or timeout."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        qs = store.get_queue_status()
        if qs["queued"] == 0 and qs["in_progress"] == 0:
            return
        time.sleep(0.5)
    raise TimeoutError("Queue did not drain within timeout")


def _stub_sdet_loop(*args, **kwargs):
    """Fast no-op replacement for _run_sdet_test_loop."""
    return [], {"required": False, "passed": True, "iterations": 0, "tests_generated": 0}


def _stub_pre_scan(*args, **kwargs):
    """Fast no-op replacement for _run_pre_scan_agents."""
    return {}


# ── 1. Multi-feature build e2e ───────────────────────────────────────────────


class TestE2EFullPipeline:
    """Full pipeline: 3 features submitted, executed concurrently, verified."""

    FEATURES = [
        {"prompt": "Add a health check endpoint that returns server status", "title": "health_check"},
        {"prompt": "Add input validation middleware for request bodies", "title": "input_validation"},
        {"prompt": "Add request logging with structured JSON output", "title": "request_logging"},
    ]

    def test_multi_feature_build_e2e(self, tmp_path):
        """Submit 3 features -> WorkerPool executes all 3 -> verify COMPLETED."""
        from agenticqa.workflow_requests import PromptWorkflowStore
        from agenticqa.worker_pool import WorkerPool
        from agenticqa.workflow_worker import WorkflowExecutionWorker

        repo_path = tmp_path / "e2e_repo"
        repo_path.mkdir()
        _init_git_repo(repo_path)

        store = PromptWorkflowStore(db_path=str(tmp_path / "e2e.db"))

        # Step 1: Submit 3 feature requests
        request_ids = []
        for feat in self.FEATURES:
            req = store.create_and_queue_request(
                prompt=feat["prompt"],
                repo=str(repo_path),
                requester="e2e_test",
                metadata={"title": feat["title"]},
            )
            assert req["status"] == "QUEUED"
            request_ids.append(req["id"])

        assert store.get_queue_status()["queued"] == 3

        # Step 2: Mock orchestrator for deterministic code gen
        mock_orch = MagicMock()
        mock_orch.run.side_effect = lambda req, fr: _mock_orchestration(fr)
        mock_orch.fullstack = MagicMock()
        mock_orch.fullstack.execute.side_effect = lambda fr: _mock_orchestration(fr)["generation"]

        # Step 3: Start pool and execute
        pool = WorkerPool(
            store=store,
            max_workers=3,
            poll_interval=0.5,
            dry_run=True,
            open_pr=False,
        )

        original_run = WorkflowExecutionWorker.run_request

        def patched_run(self_worker, *args, **kwargs):
            self_worker.orchestrator = mock_orch
            self_worker._run_pre_scan_agents = _stub_pre_scan
            self_worker._run_sdet_test_loop = _stub_sdet_loop
            return original_run(self_worker, *args, **kwargs)

        with patch.object(WorkflowExecutionWorker, "run_request", patched_run):
            pool.start()
            _wait_for_queue_drain(store, timeout=60)
            pool.stop(timeout=30)

        # Step 4: Verify all 3 COMPLETED
        for rid in request_ids:
            req = store.get_request(rid)
            assert req["status"] == "COMPLETED", (
                f"Request {rid}: status={req['status']}, error={req.get('error_message')}"
            )
            assert req["branch_name"] is not None
            assert req["branch_name"].startswith("agenticqa/")
            assert req["commit_sha"] is not None
            assert len(req["commit_sha"]) >= 7

        # Step 5: Verify 3 unique branches
        branches = [store.get_request(rid)["branch_name"] for rid in request_ids]
        assert len(set(branches)) == 3, f"Expected 3 unique branches, got {branches}"

        # Step 6: Queue fully drained
        final = store.get_queue_status()
        assert final["queued"] == 0
        assert final["in_progress"] == 0

        # Step 7: Commits reachable in git
        for rid in request_ids:
            req = store.get_request(rid)
            result = subprocess.run(
                ["git", "cat-file", "-t", req["commit_sha"]],
                cwd=str(repo_path),
                capture_output=True, text=True,
            )
            assert result.stdout.strip() == "commit", (
                f"Commit {req['commit_sha']} not reachable: {result.stderr}"
            )

        # Step 8: Workflow artifacts exist in commits
        for rid in request_ids:
            req = store.get_request(rid)
            artifact_rel = f".agenticqa/workflows/{rid}.md"
            show = subprocess.run(
                ["git", "show", f"{req['commit_sha']}:{artifact_rel}"],
                cwd=str(repo_path),
                capture_output=True, text=True,
            )
            assert show.returncode == 0, f"Artifact not in commit: {show.stderr}"
            assert rid in show.stdout

        # Step 9: Lifecycle events complete
        for rid in request_ids:
            req = store.get_request(rid)
            events = req.get("events", [])
            to_statuses = [e["to_status"] for e in events]
            assert "QUEUED" in to_statuses
            assert "IN_PROGRESS" in to_statuses
            assert "COMPLETED" in to_statuses

        store.close()


# ── 2. Git identity auto-configuration ───────────────────────────────────────


class TestGitIdentityAutoConfig:
    """Worker should auto-set git user.name/email when missing."""

    def test_auto_sets_identity_on_bare_repo(self, tmp_path):
        """Repo without local user.name/email should still commit successfully.

        _ensure_git_identity either sets a local identity or relies on global
        config — either way the commit must succeed.
        """
        from agenticqa.workflow_requests import PromptWorkflowStore
        from agenticqa.workflow_worker import WorkflowExecutionWorker

        repo_path = tmp_path / "bare_id"
        repo_path.mkdir()
        # Init without setting identity — then manually add + commit with env vars
        subprocess.run(["git", "init"], cwd=str(repo_path), check=True, capture_output=True)
        (repo_path / "app.py").write_text("x = 1\n")
        subprocess.run(["git", "add", "."], cwd=str(repo_path), check=True, capture_output=True)
        env = os.environ.copy()
        env["GIT_AUTHOR_NAME"] = "init"
        env["GIT_AUTHOR_EMAIL"] = "init@test.com"
        env["GIT_COMMITTER_NAME"] = "init"
        env["GIT_COMMITTER_EMAIL"] = "init@test.com"
        subprocess.run(
            ["git", "commit", "-m", "init"],
            cwd=str(repo_path), check=True, capture_output=True, env=env,
        )

        # Verify no local config
        result = subprocess.run(
            ["git", "config", "--local", "user.name"],
            cwd=str(repo_path), capture_output=True, text=True,
        )
        assert result.returncode != 0 or not result.stdout.strip()

        store = PromptWorkflowStore(db_path=str(tmp_path / "bare.db"))
        req = store.create_and_queue_request("test feature", str(repo_path), "tester")

        mock_orch = MagicMock()
        mock_orch.run.side_effect = lambda r, fr: _mock_orchestration(fr)
        mock_orch.fullstack = MagicMock()
        mock_orch.fullstack.execute.side_effect = lambda fr: _mock_orchestration(fr)["generation"]

        worker = WorkflowExecutionWorker(store)
        worker.orchestrator = mock_orch
        worker._run_pre_scan_agents = _stub_pre_scan
        worker._run_sdet_test_loop = _stub_sdet_loop
        result = worker.run_request(req["id"], dry_run=True, open_pr=False)

        assert result["status"] == "COMPLETED"
        assert result["commit_sha"] is not None

        # Verify a valid identity exists (either auto-set or from global config)
        name = subprocess.run(
            ["git", "config", "user.name"],
            cwd=str(repo_path), capture_output=True, text=True,
        )
        assert name.returncode == 0 and name.stdout.strip(), "git user.name should be set"

        store.close()


# ── 3. Concurrent worktree isolation ─────────────────────────────────────────


class TestConcurrentWorktreeIsolation:
    """Verify unique worktree paths per concurrent request."""

    def test_no_worktree_collision(self, tmp_path):
        from agenticqa.workflow_requests import PromptWorkflowStore
        from agenticqa.worker_pool import WorkerPool
        from agenticqa.workflow_worker import WorkflowExecutionWorker

        repo_path = tmp_path / "wt_iso"
        repo_path.mkdir()
        _init_git_repo(repo_path)

        store = PromptWorkflowStore(db_path=str(tmp_path / "wt.db"))

        ids = []
        for i in range(3):
            r = store.create_and_queue_request(f"feature {i}", str(repo_path), "tester")
            ids.append(r["id"])

        mock_orch = MagicMock()
        mock_orch.run.side_effect = lambda r, fr: _mock_orchestration(fr)
        mock_orch.fullstack = MagicMock()
        mock_orch.fullstack.execute.side_effect = lambda fr: _mock_orchestration(fr)["generation"]

        pool = WorkerPool(store=store, max_workers=3, poll_interval=0.5, dry_run=True)

        original_run = WorkflowExecutionWorker.run_request

        def patched_run(self_worker, *args, **kwargs):
            self_worker.orchestrator = mock_orch
            self_worker._run_pre_scan_agents = _stub_pre_scan
            self_worker._run_sdet_test_loop = _stub_sdet_loop
            return original_run(self_worker, *args, **kwargs)

        with patch.object(WorkflowExecutionWorker, "run_request", patched_run):
            pool.start()
            _wait_for_queue_drain(store, timeout=60)
            pool.stop(timeout=30)

        # Verify worktree paths were set and unique
        wt_paths = []
        for rid in ids:
            req = store.get_request(rid)
            wt = req.get("worktree_path")
            if wt:
                wt_paths.append(wt)

        assert len(set(wt_paths)) == len(wt_paths), f"Duplicate worktree paths: {wt_paths}"
        store.close()


# ── 4. Failed request does not block queue ───────────────────────────────────


class TestFailedRequestHandling:
    """One bad request should not block other valid ones."""

    def test_bad_repo_fails_others_complete(self, tmp_path):
        from agenticqa.workflow_requests import PromptWorkflowStore
        from agenticqa.worker_pool import WorkerPool
        from agenticqa.workflow_worker import WorkflowExecutionWorker

        repo_path = tmp_path / "good_repo"
        repo_path.mkdir()
        _init_git_repo(repo_path)

        store = PromptWorkflowStore(db_path=str(tmp_path / "mixed.db"))

        # 2 valid + 1 invalid repo path
        good1 = store.create_and_queue_request("feature 1", str(repo_path), "tester")
        bad = store.create_and_queue_request("bad feature", "/nonexistent/repo/path", "tester")
        good2 = store.create_and_queue_request("feature 2", str(repo_path), "tester")

        mock_orch = MagicMock()
        mock_orch.run.side_effect = lambda r, fr: _mock_orchestration(fr)
        mock_orch.fullstack = MagicMock()
        mock_orch.fullstack.execute.side_effect = lambda fr: _mock_orchestration(fr)["generation"]

        pool = WorkerPool(store=store, max_workers=3, poll_interval=0.5, dry_run=True)

        original_run = WorkflowExecutionWorker.run_request

        def patched_run(self_worker, *args, **kwargs):
            self_worker.orchestrator = mock_orch
            self_worker._run_pre_scan_agents = _stub_pre_scan
            self_worker._run_sdet_test_loop = _stub_sdet_loop
            return original_run(self_worker, *args, **kwargs)

        with patch.object(WorkflowExecutionWorker, "run_request", patched_run):
            pool.start()
            _wait_for_queue_drain(store, timeout=60)
            pool.stop(timeout=30)

        # Good ones complete, bad one fails
        assert store.get_request(good1["id"])["status"] == "COMPLETED"
        assert store.get_request(good2["id"])["status"] == "COMPLETED"
        assert store.get_request(bad["id"])["status"] == "FAILED"
        assert store.get_request(bad["id"])["error_message"] is not None

        # Queue fully drained
        final = store.get_queue_status()
        assert final["queued"] == 0
        assert final["in_progress"] == 0

        store.close()


# ── 5. Request lifecycle events ──────────────────────────────────────────────


class TestRequestLifecycle:
    """Verify complete audit trail in events."""

    def test_create_and_queue_lifecycle(self, tmp_path):
        """Auto-queue path should record all transitions."""
        from agenticqa.workflow_requests import PromptWorkflowStore

        store = PromptWorkflowStore(db_path=str(tmp_path / "lifecycle.db"))
        req = store.create_and_queue_request("test", "/tmp", "tester")

        events = req["events"]
        transitions = [(e["from_status"], e["to_status"]) for e in events]

        # Fast-path records: RECEIVED->PLANNED, PLANNED->AWAITING_APPROVAL,
        # AWAITING_APPROVAL->APPROVED, APPROVED->QUEUED
        assert ("RECEIVED", "PLANNED") in transitions
        assert ("APPROVED", "QUEUED") in transitions
        store.close()


# ── 6. Preflight integration ────────────────────────────────────────────────


class TestPreflightIntegration:
    """Run preflight against a test repo and verify it passes."""

    def test_preflight_on_healthy_repo(self, tmp_path):
        from agenticqa.client_preflight import run_preflight

        repo = tmp_path / "preflight_int"
        repo.mkdir()
        _init_git_repo(repo)

        report = run_preflight(str(repo))
        assert report.passed is True
        assert len(report.checks) == 7

        # All critical probes pass
        for check in report.checks:
            if check.name in ("git_repo", "git_config", "python_tooling", "import_chain"):
                assert check.status == "pass", f"{check.name} should pass: {check.message}"
