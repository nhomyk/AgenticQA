"""Tests for observability event store and worker trace logging."""

import os
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from agenticqa.observability import ObservabilityStore
from agenticqa.workflow_requests import PromptWorkflowStore
from agenticqa.workflow_worker import WorkflowExecutionWorker


def _init_git_repo(path: Path) -> None:
    subprocess.run(["git", "init"], cwd=str(path), check=True, capture_output=True, text=True)
    subprocess.run(["git", "config", "user.email", "agenticqa@example.com"], cwd=str(path), check=True)
    subprocess.run(["git", "config", "user.name", "AgenticQA Bot"], cwd=str(path), check=True)
    (path / "README.md").write_text("# temp repo\n", encoding="utf-8")
    subprocess.run(["git", "add", "README.md"], cwd=str(path), check=True)
    subprocess.run(["git", "commit", "-m", "init"], cwd=str(path), check=True)


def test_observability_store_lists_traces_and_events(tmp_path):
    store = ObservabilityStore(db_path=str(tmp_path / "obs.db"))
    store.log_event(
        trace_id="tr_1",
        request_id="wr_1",
        span_id="sp_1",
        agent="WorkflowWorker",
        action="run_request",
        status="STARTED",
        metadata={"dry_run": True},
    )
    store.log_event(
        trace_id="tr_1",
        request_id="wr_1",
        span_id="sp_1",
        agent="SDET_Agent",
        action="sdet_test_loop",
        status="COMPLETED",
        metadata={"iterations": 1},
    )

    traces = store.list_traces(limit=10)
    assert len(traces) == 1
    assert traces[0]["trace_id"] == "tr_1"
    assert traces[0]["event_count"] == 2

    events = store.list_events(limit=10, trace_id="tr_1")
    assert len(events) == 2
    assert events[0]["metadata"] is not None

    trace = store.get_trace("tr_1")
    analysis = trace.get("analysis") or {}
    assert analysis.get("trace_id") == "tr_1"
    assert analysis.get("completeness_ratio") == 1.0

    quality = store.get_quality_summary(limit=10, min_completeness=0.95)
    assert quality["trace_count"] == 1
    assert quality["below_threshold_count"] == 0

    store.close()


def test_worker_emits_observability_events(tmp_path):
    repo_path = tmp_path / "repo"
    repo_path.mkdir(parents=True, exist_ok=True)
    _init_git_repo(repo_path)

    wf_store = PromptWorkflowStore(db_path=str(tmp_path / "workflow.db"))
    obs_store = ObservabilityStore(db_path=str(tmp_path / "obs.db"))

    item = wf_store.create_request(
        prompt="Add simple endpoint helper",
        repo=str(repo_path),
        requester="tests",
        metadata={
            "target_file": "src/generated/obs_test.py",
            "require_sdet_loop": True,
            "max_sdet_iterations": 1,
            "enable_sdet_autofix": True,
            "inject_python_syntax_error": True,
        },
    )
    wf_store.approve_request(item["id"])
    wf_store.queue_request(item["id"])

    worker = WorkflowExecutionWorker(wf_store, observability_store=obs_store)
    result = worker.run_request(item["id"], dry_run=True, open_pr=False)

    assert result["status"] == "COMPLETED"

    events = obs_store.list_events(limit=100, request_id=item["id"])
    actions = {(e["agent"], e["action"], e["status"]) for e in events}

    assert ("WorkflowWorker", "run_request", "STARTED") in actions
    assert ("PromptOpsOrchestrator", "orchestrate", "STARTED") in actions
    assert ("SDET_Agent", "sdet_test_loop", "STARTED") in actions

    trace_id = events[0]["trace_id"]
    analysis = obs_store.analyze_trace(trace_id)
    assert analysis["span_count"] >= 2
    assert analysis["critical_path_ms"] >= 0

    obs_store.close()
    wf_store.close()
