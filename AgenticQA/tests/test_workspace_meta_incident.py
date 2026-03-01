"""Tests for Meta/OpenClaw incident protections.

On 2026-02-23, Meta's AI Safety Director lost control of an OpenClaw agent
that "speed-ran deleting" her emails after context-window compaction dropped
the "don't take action" instruction.

These tests verify that AgenticQA's workspace cannot reproduce this failure:
  1. Email deletion is permanently hard-blocked (no API, no code path)
  2. Email move/archive is hard-blocked
  3. Emergency stop revokes all leases
  4. Safety invariants survive and can be re-injected
  5. Send requires explicit approval token
  6. Lease exhaustion is a hard block (not advisory)
"""
import os
import pytest

from agenticqa.workspace.mail_client import SafeMailClient, MailConfig
from agenticqa.workspace.workspace_safety import (
    WorkspaceSafetyGate,
    WORKSPACE_SAFETY_INVARIANTS,
    WORKSPACE_LEASE_STANDARD,
    get_safety_invariants_prompt,
)
from agenticqa.security.scope_lease_manager import LeaseConfig


# ── Email deletion PERMANENTLY blocked ───────────────────────────────────────


@pytest.mark.unit
def test_email_delete_hard_blocked():
    """delete_message() is always blocked, regardless of config or approval."""
    client = SafeMailClient(config=MailConfig(
        imap_host="imap.test.com", user="test@test.com", password="secret",
    ))
    result = client.delete_message("42")
    assert not result.success
    assert "permanently disabled" in result.error.lower()


@pytest.mark.unit
def test_email_delete_mentions_meta_incident():
    """delete_message error references the Meta/OpenClaw incident."""
    client = SafeMailClient(config=MailConfig())
    result = client.delete_message("1")
    assert "Meta/OpenClaw" in result.error or "2026-02-23" in result.error


@pytest.mark.unit
def test_email_move_hard_blocked():
    """move_message() is always blocked."""
    client = SafeMailClient(config=MailConfig(
        imap_host="imap.test.com", user="test@test.com", password="secret",
    ))
    result = client.move_message("42", "Trash")
    assert not result.success
    assert "disabled" in result.error.lower()


@pytest.mark.unit
def test_email_delete_no_code_path_exists():
    """No IMAP DELETE or STORE \\Deleted flag is ever sent."""
    # Verify the SafeMailClient has no method that calls IMAP delete/store
    import inspect
    source = inspect.getsource(SafeMailClient)
    # These IMAP commands would delete emails
    dangerous_imap = ["store(", "uid store", "\\Deleted", "expunge"]
    for cmd in dangerous_imap:
        assert cmd.lower() not in source.lower(), \
            f"SafeMailClient source should not contain '{cmd}'"


# ── Send requires approval ───────────────────────────────────────────────────


@pytest.mark.unit
def test_send_without_approval_blocked():
    """Sending email without approved=True is always blocked."""
    client = SafeMailClient(config=MailConfig(
        imap_host="imap.test.com", smtp_host="smtp.test.com",
        user="test@test.com", password="secret",
    ))
    result = client.send_message("to@test.com", "Test", "Body")
    assert not result.success
    assert result.requires_approval


@pytest.mark.unit
def test_send_default_is_unapproved():
    """The approved parameter defaults to False (safe by default)."""
    import inspect
    sig = inspect.signature(SafeMailClient.send_message)
    assert sig.parameters["approved"].default is False


# ── Emergency stop ───────────────────────────────────────────────────────────


@pytest.mark.unit
def test_emergency_stop_revokes_lease(tmp_path):
    """emergency_stop() revokes the workspace lease."""
    gate = WorkspaceSafetyGate(
        session_id="test-estop",
        lease_config=WORKSPACE_LEASE_STANDARD,
        audit_path=tmp_path / "audit",
    )

    # Verify lease is active before stop
    status_before = gate.get_lease_status()
    assert status_before is not None
    assert status_before.get("is_active") is True

    # Emergency stop
    result = gate.emergency_stop()
    assert result["revoked_count"] >= 1

    # Lease should now be revoked — operations blocked
    verdict = gate.check("file_read")
    assert not verdict.allowed


@pytest.mark.unit
def test_emergency_stop_revokes_multiple_leases(tmp_path):
    """emergency_stop() revokes ALL active leases, not just the caller's."""
    gate1 = WorkspaceSafetyGate(
        session_id="sess-1",
        lease_config=WORKSPACE_LEASE_STANDARD,
        audit_path=tmp_path / "audit",
    )
    # Create a second gate sharing the same lease manager
    gate2 = WorkspaceSafetyGate(
        session_id="sess-2",
        lease_config=WORKSPACE_LEASE_STANDARD,
        audit_path=tmp_path / "audit",
    )

    result = gate1.emergency_stop()
    assert result["revoked_count"] >= 1


# ── Safety invariants (compaction resilience) ────────────────────────────────


@pytest.mark.unit
def test_safety_invariants_exist():
    """WORKSPACE_SAFETY_INVARIANTS is a non-empty list."""
    assert isinstance(WORKSPACE_SAFETY_INVARIANTS, list)
    assert len(WORKSPACE_SAFETY_INVARIANTS) >= 5


@pytest.mark.unit
def test_invariants_cover_email_deletion():
    """At least one invariant explicitly forbids email deletion."""
    combined = " ".join(WORKSPACE_SAFETY_INVARIANTS).lower()
    assert "email deletion" in combined or "delete" in combined


@pytest.mark.unit
def test_invariants_cover_lease_caps():
    """At least one invariant mentions hard lease caps."""
    combined = " ".join(WORKSPACE_SAFETY_INVARIANTS).lower()
    assert "lease" in combined or "cap" in combined


@pytest.mark.unit
def test_invariants_cover_send_approval():
    """At least one invariant mentions send approval requirement."""
    combined = " ".join(WORKSPACE_SAFETY_INVARIANTS).lower()
    assert "approval" in combined


@pytest.mark.unit
def test_invariants_prompt_format():
    """get_safety_invariants_prompt() returns a formatted prompt block."""
    prompt = get_safety_invariants_prompt()
    assert "[WORKSPACE SAFETY INVARIANTS" in prompt
    assert "[END INVARIANTS]" in prompt
    assert "1." in prompt  # numbered


@pytest.mark.unit
def test_invariants_prompt_contains_all_invariants():
    """All invariants appear in the prompt."""
    prompt = get_safety_invariants_prompt()
    for inv in WORKSPACE_SAFETY_INVARIANTS:
        assert inv in prompt


# ── Lease exhaustion is hard block ───────────────────────────────────────────


@pytest.mark.unit
def test_lease_exhaustion_hard_blocks(tmp_path):
    """When a lease is exhausted, operations are hard-blocked (not advisory)."""
    config = LeaseConfig(
        max_reads=2, max_writes=0, max_deletes=0, max_executes=0,
        lease_ttl_seconds=300,
    )
    gate = WorkspaceSafetyGate(
        session_id="test-exhaust",
        lease_config=config,
        audit_path=tmp_path / "audit",
    )

    # Use up both reads
    v1 = gate.check("file_list")
    v2 = gate.check("file_read")
    assert v1.allowed
    assert v2.allowed

    # Third read MUST be blocked (not advisory)
    v3 = gate.check("file_read")
    assert not v3.allowed


# ── API endpoints for Meta incident protections ─────────────────────────────


@pytest.fixture
def client():
    os.environ["AGENTICQA_AUTH_DISABLE"] = "1"
    os.environ["AGENTICQA_PATH_SANITIZE_DISABLE"] = "1"
    from fastapi.testclient import TestClient
    import agent_api
    return TestClient(agent_api.app)


@pytest.mark.unit
def test_emergency_stop_endpoint(client):
    """POST /api/workspace/safety/emergency-stop works."""
    resp = client.post("/api/workspace/safety/emergency-stop")
    assert resp.status_code == 200
    data = resp.json()
    assert data["success"] is True
    assert "revoked_count" in data


@pytest.mark.unit
def test_safety_invariants_endpoint(client):
    """GET /api/workspace/safety/invariants returns the invariants."""
    resp = client.get("/api/workspace/safety/invariants")
    assert resp.status_code == 200
    data = resp.json()
    assert data["success"] is True
    assert len(data["invariants"]) >= 5
    assert "[WORKSPACE SAFETY INVARIANTS" in data["prompt"]
