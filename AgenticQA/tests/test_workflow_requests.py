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
