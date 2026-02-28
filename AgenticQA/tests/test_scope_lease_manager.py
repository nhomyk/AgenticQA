"""Unit tests for AgentScopeLeaseManager."""
import pytest
import time
from agenticqa.security.scope_lease_manager import (
    AgentScopeLeaseManager,
    LeaseConfig,
)


@pytest.fixture
def mgr(tmp_path):
    return AgentScopeLeaseManager(audit_path=tmp_path)


# ── Lease creation ────────────────────────────────────────────────────────────

@pytest.mark.unit
def test_create_lease_returns_id(mgr):
    lease_id = mgr.create_lease("agent-1", "sess-1")
    assert isinstance(lease_id, str) and len(lease_id) > 0

@pytest.mark.unit
def test_get_lease_status_has_fields(mgr):
    lid = mgr.create_lease("agent-1", "sess-1")
    status = mgr.get_lease_status(lid)
    assert status is not None
    for key in ("lease_id", "agent_id", "caps", "used", "is_active", "seconds_remaining"):
        assert key in status

@pytest.mark.unit
def test_standard_lease_no_deletes(mgr):
    lid = mgr.create_lease("agent", "sess", LeaseConfig.standard())
    allowed, reason = mgr.check_and_consume(lid, "delete")
    assert allowed is False
    assert "prohibits" in reason

@pytest.mark.unit
def test_readonly_lease_blocks_writes(mgr):
    lid = mgr.create_lease("agent", "sess", LeaseConfig.readonly())
    allowed, reason = mgr.check_and_consume(lid, "write")
    assert allowed is False

@pytest.mark.unit
def test_readonly_lease_allows_reads(mgr):
    lid = mgr.create_lease("agent", "sess", LeaseConfig.readonly())
    allowed, _ = mgr.check_and_consume(lid, "read")
    assert allowed is True

@pytest.mark.unit
def test_elevated_lease_allows_limited_deletes(mgr):
    lid = mgr.create_lease("agent", "sess", LeaseConfig.elevated(max_deletes=3))
    for _ in range(3):
        allowed, _ = mgr.check_and_consume(lid, "delete")
        assert allowed is True
    # 4th delete must be blocked
    allowed, reason = mgr.check_and_consume(lid, "delete")
    assert allowed is False
    assert "exhausted" in reason


# ── Cap enforcement ───────────────────────────────────────────────────────────

@pytest.mark.unit
def test_write_cap_exhausted(mgr):
    lid = mgr.create_lease("agent", "sess", LeaseConfig(max_writes=2))
    mgr.check_and_consume(lid, "write")
    mgr.check_and_consume(lid, "write")
    allowed, reason = mgr.check_and_consume(lid, "write")
    assert allowed is False
    assert "exhausted" in reason

@pytest.mark.unit
def test_counter_increments(mgr):
    lid = mgr.create_lease("agent", "sess", LeaseConfig(max_writes=10))
    for _ in range(5):
        mgr.check_and_consume(lid, "write")
    status = mgr.get_lease_status(lid)
    assert status["used"]["writes"] == 5

@pytest.mark.unit
def test_nonexistent_lease_blocked(mgr):
    allowed, reason = mgr.check_and_consume("fake-id", "read")
    assert allowed is False
    assert "No lease found" in reason


# ── TTL / expiry ──────────────────────────────────────────────────────────────

@pytest.mark.unit
def test_expired_lease_blocked(mgr):
    lid = mgr.create_lease("agent", "sess", LeaseConfig(lease_ttl_seconds=0))
    time.sleep(0.01)  # ensure expired
    allowed, reason = mgr.check_and_consume(lid, "read")
    assert allowed is False
    assert "expired" in reason.lower()


# ── Manual revocation ─────────────────────────────────────────────────────────

@pytest.mark.unit
def test_revoke_blocks_further_ops(mgr):
    lid = mgr.create_lease("agent", "sess", LeaseConfig.elevated())
    mgr.revoke_lease(lid, reason="emergency stop")
    allowed, reason = mgr.check_and_consume(lid, "read")
    assert allowed is False
    assert "revoked" in reason.lower()

@pytest.mark.unit
def test_revoke_unknown_lease_returns_false(mgr):
    assert mgr.revoke_lease("ghost-id") is False


# ── Peek (no consume) ─────────────────────────────────────────────────────────

@pytest.mark.unit
def test_peek_does_not_consume(mgr):
    lid = mgr.create_lease("agent", "sess", LeaseConfig(max_writes=3))
    for _ in range(5):
        mgr.peek(lid, "write")
    status = mgr.get_lease_status(lid)
    assert status["used"]["writes"] == 0

@pytest.mark.unit
def test_peek_reflects_cap_breach(mgr):
    lid = mgr.create_lease("agent", "sess", LeaseConfig(max_writes=1))
    mgr.check_and_consume(lid, "write")  # consume the only write
    allowed, _ = mgr.peek(lid, "write")
    assert allowed is False


# ── List active leases ────────────────────────────────────────────────────────

@pytest.mark.unit
def test_list_active_leases(mgr):
    mgr.create_lease("a1", "s1")
    mgr.create_lease("a2", "s2")
    active = mgr.list_active_leases()
    assert len(active) >= 2

@pytest.mark.unit
def test_action_aliases_normalised(mgr):
    lid = mgr.create_lease("agent", "sess", LeaseConfig(max_writes=5))
    # "update" should map to "write"
    allowed, msg = mgr.check_and_consume(lid, "update")
    assert allowed is True
    assert "write" in msg.lower() or "allowed" in msg.lower()
