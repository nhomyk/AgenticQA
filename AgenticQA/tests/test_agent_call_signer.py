"""Unit tests for AgentCallSigner."""
import time
import pytest
from agenticqa.security.agent_call_signer import AgentCallSigner, SignedCall


@pytest.fixture
def signer():
    return AgentCallSigner()


@pytest.mark.unit
def test_sign_returns_signed_call(signer):
    signed = signer.sign_call("QA_Agent", "SRE_Agent", "fix_linting", {"errors": 5})
    assert isinstance(signed, SignedCall)
    assert signed.from_agent == "QA_Agent"
    assert signed.to_agent == "SRE_Agent"
    assert signed.task_type == "fix_linting"
    assert len(signed.signature) == 64  # SHA-256 hex


@pytest.mark.unit
def test_verify_valid_call(signer):
    signed = signer.sign_call("QA_Agent", "SRE_Agent", "fix_linting", {"errors": 5})
    ok, err = signer.verify_call(signed)
    assert ok is True
    assert err is None


@pytest.mark.unit
def test_verify_tampered_payload(signer):
    signed = signer.sign_call("QA_Agent", "SRE_Agent", "fix_linting", {"errors": 5})
    # Tamper with payload
    tampered = SignedCall(**{**signed.__dict__, "payload": {"errors": 999}})
    ok, err = signer.verify_call(tampered)
    assert ok is False
    assert "tampered" in err.lower() or "hash" in err.lower()


@pytest.mark.unit
def test_verify_forged_signature(signer):
    signed = signer.sign_call("QA_Agent", "SRE_Agent", "fix_linting", {"errors": 5})
    forged = SignedCall(**{**signed.__dict__, "signature": "a" * 64})
    ok, err = signer.verify_call(forged)
    assert ok is False
    assert "invalid" in err.lower() or "signature" in err.lower()


@pytest.mark.unit
def test_verify_expired_call(signer):
    signed = signer.sign_call("QA_Agent", "SRE_Agent", "fix_linting", {})
    # Backdating timestamp beyond max age
    old = SignedCall(**{**signed.__dict__, "timestamp": time.time() - 400})
    ok, err = signer.verify_call(old)
    assert ok is False
    assert "expir" in err.lower()


@pytest.mark.unit
def test_verify_future_timestamp(signer):
    signed = signer.sign_call("QA_Agent", "SRE_Agent", "fix_linting", {})
    future = SignedCall(**{**signed.__dict__, "timestamp": time.time() + 60})
    ok, err = signer.verify_call(future)
    assert ok is False


@pytest.mark.unit
def test_different_nonce_different_signature(signer):
    p = {"data": "test"}
    s1 = signer.sign_call("A", "B", "task", p)
    s2 = signer.sign_call("A", "B", "task", p)
    assert s1.nonce != s2.nonce
    assert s1.signature != s2.signature


@pytest.mark.unit
def test_to_dict_from_dict_round_trip(signer):
    signed = signer.sign_call("QA_Agent", "SRE_Agent", "task", {"x": 1})
    d = AgentCallSigner.to_dict(signed)
    restored = AgentCallSigner.from_dict(d)
    ok, err = signer.verify_call(restored)
    assert ok is True


@pytest.mark.unit
def test_empty_payload_signed(signer):
    signed = signer.sign_call("A", "B", "t", {})
    ok, err = signer.verify_call(signed)
    assert ok is True


@pytest.mark.unit
def test_agent_impersonation_blocked(signer):
    """Compromised agent claims to be QA_Agent but uses different key."""
    signed = signer.sign_call("Malicious_Agent", "SRE_Agent", "deploy", {"env": "prod"})
    # Attacker changes from_agent to QA_Agent
    spoofed = SignedCall(**{**signed.__dict__, "from_agent": "QA_Agent"})
    ok, err = signer.verify_call(spoofed)
    assert ok is False  # signature covers from_agent, so spoof is detected
