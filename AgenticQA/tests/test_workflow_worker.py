"""Tests for workflow execution worker."""

import os
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from agenticqa.workflow_requests import PromptWorkflowStore
from agenticqa.workflow_worker import WorkflowExecutionWorker


def _init_git_repo(path: Path) -> None:
    subprocess.run(["git", "init"], cwd=str(path), check=True, capture_output=True, text=True)
    subprocess.run(["git", "config", "user.email", "agenticqa@example.com"], cwd=str(path), check=True)
    subprocess.run(["git", "config", "user.name", "AgenticQA Bot"], cwd=str(path), check=True)

    (path / "README.md").write_text("# temp repo\n", encoding="utf-8")
    subprocess.run(["git", "add", "README.md"], cwd=str(path), check=True)
    subprocess.run(["git", "commit", "-m", "init"], cwd=str(path), check=True)


def test_worker_processes_queued_request_dry_run(tmp_path):
    repo_path = tmp_path / "repo"
    repo_path.mkdir(parents=True, exist_ok=True)
    _init_git_repo(repo_path)

    store = PromptWorkflowStore(db_path=str(tmp_path / "workflow.db"))
    item = store.create_request(
        prompt="Add health endpoint tests",
        repo=str(repo_path),
        requester="dashboard",
    )
    approved = store.approve_request(item["id"])
    assert approved["status"] == "APPROVED"
    queued = store.queue_request(item["id"])
    assert queued["status"] == "QUEUED"

    worker = WorkflowExecutionWorker(store)
    result = worker.run_next(dry_run=True, open_pr=False)

    assert result is not None
    assert result["id"] == item["id"]
    assert result["status"] == "COMPLETED"
    assert result["branch_name"].startswith("agenticqa/")
    assert result["commit_sha"] is not None
    assert len(result["commit_sha"]) >= 7
    assert result["pr_url"] is None

    artifact_rel = f".agenticqa/workflows/{item['id']}.md"
    show = subprocess.run(
        ["git", "show", f"{result['commit_sha']}:{artifact_rel}"],
        cwd=str(repo_path),
        capture_output=True,
        text=True,
        check=True,
    )
    assert item["id"] in show.stdout
    assert "Collaborative Orchestration" in show.stdout
    assert "Fullstack_Agent" in show.stdout

    changed = subprocess.run(
        ["git", "show", "--name-only", "--pretty=format:", result["commit_sha"]],
        cwd=str(repo_path),
        capture_output=True,
        text=True,
        check=True,
    )
    changed_files = [line.strip() for line in changed.stdout.splitlines() if line.strip()]
    assert artifact_rel in changed_files
    generated_files = [
        p for p in changed_files
        if p != artifact_rel and (p.endswith(".js") or p.endswith(".py") or p.endswith(".ts"))
    ]
    assert len(generated_files) >= 1

    generated_show = subprocess.run(
        ["git", "show", f"{result['commit_sha']}:{generated_files[0]}"],
        cwd=str(repo_path),
        capture_output=True,
        text=True,
        check=True,
    )
    assert "Author Agent" in generated_show.stdout
    assert "Quality Gate Passed" in generated_show.stdout

    store.close()


def test_worker_marks_failed_for_missing_repo(tmp_path):
    missing_repo = tmp_path / "does_not_exist"

    store = PromptWorkflowStore(db_path=str(tmp_path / "workflow.db"))
    item = store.create_request(
        prompt="Implement endpoint",
        repo=str(missing_repo),
        requester="dashboard",
    )
    store.approve_request(item["id"])
    store.queue_request(item["id"])

    worker = WorkflowExecutionWorker(store)
    result = worker.run_request(item["id"], dry_run=True, open_pr=False)

    assert result["status"] == "FAILED"
    assert "repo_not_found" in (result.get("error_message") or "")

    store.close()


def test_worker_enforces_strict_push_policy_gate(tmp_path):
    repo_path = tmp_path / "repo"
    repo_path.mkdir(parents=True, exist_ok=True)
    _init_git_repo(repo_path)

    store = PromptWorkflowStore(db_path=str(tmp_path / "workflow.db"))
    item = store.create_request(
        prompt="Add safer retry handling",
        repo=str(repo_path),
        requester="dashboard",
        metadata={"source": "test"},
    )
    store.approve_request(item["id"])
    store.queue_request(item["id"])

    worker = WorkflowExecutionWorker(store)
    result = worker.run_request(item["id"], dry_run=False, open_pr=False)

    assert result["status"] == "FAILED"
    assert "approved_by_required_for_push" in (result.get("error_message") or "")

    store.close()
