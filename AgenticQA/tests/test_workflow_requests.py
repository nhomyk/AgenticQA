"""Tests for prompt-driven workflow request store."""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from agenticqa.workflow_requests import PromptWorkflowStore


def test_create_request_generates_plan_and_waits_approval(tmp_path):
    store = PromptWorkflowStore(db_path=str(tmp_path / "workflow.db"))

    item = store.create_request(
        prompt="Add retry to webhook endpoint and tests",
        repo=".",
        requester="dashboard",
    )

    assert item["id"].startswith("wr_")
    assert item["status"] == "AWAITING_APPROVAL"
    assert item["next_action"] == "approve_to_queue"
    assert item["plan"] is not None
    assert "work_items" in item["plan"]
    assert len(item["plan"]["work_items"]) >= 3

    store.close()


def test_approve_then_queue_transition(tmp_path):
    store = PromptWorkflowStore(db_path=str(tmp_path / "workflow.db"))

    item = store.create_request(prompt="Build API endpoint", repo=".", requester="dashboard")
    request_id = item["id"]

    approved = store.approve_request(request_id)
    assert approved["status"] == "APPROVED"
    assert approved["next_action"] == "queue_for_execution"

    queued = store.queue_request(request_id)
    assert queued["status"] == "QUEUED"
    assert queued["next_action"] == "worker_pickup"

    store.close()


def test_cancel_request_sets_terminal_state(tmp_path):
    store = PromptWorkflowStore(db_path=str(tmp_path / "workflow.db"))

    item = store.create_request(prompt="Refactor pipeline", repo=".", requester="dashboard")
    cancelled = store.cancel_request(item["id"], reason="user_cancel")

    assert cancelled["status"] == "CANCELLED"
    assert cancelled["next_action"] == "none"

    # Terminal states should remain stable
    cancelled_again = store.cancel_request(item["id"], reason="second_try")
    assert cancelled_again["status"] == "CANCELLED"

    store.close()


def test_replay_request_creates_queued_clone(tmp_path):
    store = PromptWorkflowStore(db_path=str(tmp_path / "workflow.db"))

    item = store.create_request(prompt="Improve flaky test handling", repo=".", requester="dashboard")
    replay = store.replay_request(item["id"], requester="test_replay")

    assert replay["status"] == "QUEUED"
    assert replay["metadata"].get("replay_of") == item["id"]
    assert replay["metadata"].get("self_heal") is True

    store.close()


def test_metrics_returns_expected_keys(tmp_path):
    store = PromptWorkflowStore(db_path=str(tmp_path / "workflow.db"))
    first = store.create_request(prompt="Add endpoint", repo=".", requester="dashboard")
    store.approve_request(first["id"])
    store.queue_request(first["id"])
    store.start_request(first["id"])
    store.complete_request(first["id"], note="done")

    second = store.create_request(prompt="Break migration", repo=".", requester="dashboard")
    store.approve_request(second["id"])
    store.queue_request(second["id"])
    store.fail_request(second["id"], error_message="failed")

    metrics = store.get_metrics(lookback_limit=50)
    assert metrics["total_requests"] >= 2
    assert "mttr_minutes" in metrics
    assert "pass_rate_uplift_pct" in metrics
    assert "flaky_reduction_pct" in metrics

    store.close()


def test_chat_session_and_messages_roundtrip(tmp_path):
    store = PromptWorkflowStore(db_path=str(tmp_path / "workflow.db"))

    session = store.create_chat_session(repo=".", requester="dashboard_chat", metadata={"source": "test"})
    assert session["id"].startswith("cs_")

    user_msg = store.add_chat_message(
        session_id=session["id"],
        role="user",
        content="Add retries to webhook endpoint",
    )
    assistant_msg = store.add_chat_message(
        session_id=session["id"],
        role="assistant",
        content="Captured. I can create a workflow request next.",
        request_id="wr_123",
    )

    loaded = store.get_chat_session(session["id"], message_limit=20)
    assert loaded is not None
    assert len(loaded["messages"]) == 2
    assert loaded["messages"][0]["content"] == user_msg["content"]
    assert loaded["messages"][1]["request_id"] == assistant_msg["request_id"]

    store.close()
