"""Unit tests for ImmutableAuditChain."""
import pytest
from agenticqa.security.immutable_audit import ImmutableAuditChain, AuditEvent


@pytest.fixture
def chain(tmp_path):
    return ImmutableAuditChain(path=tmp_path / "audit.jsonl")


@pytest.mark.unit
def test_append_returns_entry(chain):
    entry = chain.append(AuditEvent("AGENT_EXEC", "QA_Agent", "execute", {"status": "ok"}))
    assert entry.seq == 0
    assert entry.event_type == "AGENT_EXEC"
    assert len(entry.entry_hash) == 64


@pytest.mark.unit
def test_chain_starts_with_genesis(chain):
    from agenticqa.security.immutable_audit import _GENESIS_HASH
    e = chain.append(AuditEvent("AGENT_EXEC", "A", "run", {}))
    assert e.prev_hash == _GENESIS_HASH


@pytest.mark.unit
def test_second_entry_links_to_first(chain):
    e1 = chain.append(AuditEvent("AGENT_EXEC", "A", "run", {}))
    e2 = chain.append(AuditEvent("DELEGATION", "A", "delegate", {}))
    assert e2.prev_hash == e1.entry_hash


@pytest.mark.unit
def test_verify_chain_intact(chain):
    for i in range(5):
        chain.append(AuditEvent("AGENT_EXEC", f"Agent{i}", "run", {}))
    ok, violations = chain.verify_chain()
    assert ok is True
    assert violations == []


@pytest.mark.unit
def test_verify_chain_detects_tampering(tmp_path):
    path = tmp_path / "audit.jsonl"
    chain = ImmutableAuditChain(path=path)
    chain.append(AuditEvent("AGENT_EXEC", "A", "run", {}))
    chain.append(AuditEvent("DELEGATION", "A", "delegate", {}))
    # Tamper with first entry
    lines = path.read_text().splitlines()
    import json
    entry = json.loads(lines[0])
    entry["actor"] = "EVIL"
    lines[0] = json.dumps(entry)
    path.write_text("\n".join(lines) + "\n")
    # Now verify
    chain2 = ImmutableAuditChain(path=path)
    ok, violations = chain2.verify_chain()
    assert ok is False
    assert len(violations) >= 1


@pytest.mark.unit
def test_empty_chain_verifies_ok(chain):
    ok, violations = chain.verify_chain()
    assert ok is True
    assert violations == []


@pytest.mark.unit
def test_length(chain):
    assert chain.length() == 0
    chain.append(AuditEvent("AGENT_EXEC", "A", "run", {}))
    chain.append(AuditEvent("SECURITY_FINDING", "Scanner", "detect", {}))
    assert chain.length() == 2


@pytest.mark.unit
def test_compliance_log_filters_event_types(chain):
    chain.append(AuditEvent("AGENT_EXEC", "QA", "run", {}))
    chain.append(AuditEvent("GOVERNANCE_DECISION", "Gate", "allow", {}))
    log = chain.get_compliance_log(event_types={"GOVERNANCE_DECISION"})
    assert all(e["event_type"] == "GOVERNANCE_DECISION" for e in log)


@pytest.mark.unit
def test_compliance_log_filters_tenant(chain):
    chain.append(AuditEvent("AGENT_EXEC", "A", "run", {}, tenant_id="tenant-1"))
    chain.append(AuditEvent("AGENT_EXEC", "B", "run", {}, tenant_id="tenant-2"))
    log = chain.get_compliance_log(tenant_id="tenant-1")
    assert all(e["tenant_id"] == "tenant-1" for e in log)


@pytest.mark.unit
def test_compliance_log_chain_verified_flag(chain):
    chain.append(AuditEvent("SECURITY_FINDING", "Scanner", "detect", {}))
    log = chain.get_compliance_log()
    assert log[0]["chain_verified"] is True


@pytest.mark.unit
def test_seq_increments(chain):
    e0 = chain.append(AuditEvent("AGENT_EXEC", "A", "run", {}))
    e1 = chain.append(AuditEvent("AGENT_EXEC", "B", "run", {}))
    assert e0.seq == 0
    assert e1.seq == 1
