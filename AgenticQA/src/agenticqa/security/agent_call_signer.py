"""
AgentCallSigner — cryptographic signing and verification of inter-agent delegation calls.

Problem
-------
DelegationGuardrails enforce *who* can call *what*, but do not prove *that the caller
is the agent it claims to be*. A compromised agent (or a prompt-injected agent) can
forge ExecutionRequest objects claiming to originate from any agent.

Solution
--------
Every outgoing delegation is signed with HMAC-SHA256 over a canonical payload:

    HMAC-SHA256(key, f"{from_agent}|{to_agent}|{task_type}|{payload_hash}|{timestamp}|{nonce}")

The signature, timestamp, and nonce are attached as metadata.  The receiver calls
verify_call() before executing — if the signature is missing, forged, or expired,
the call is rejected.

Key: AGENTICQA_AGENT_CALL_SECRET env var (auto-derived from AGENTICQA_PROVENANCE_SECRET
if absent; falls back to a dev default that prints a warning).

Usage
-----
    from agenticqa.security.agent_call_signer import AgentCallSigner

    signer = AgentCallSigner()
    signed = signer.sign_call("QA_Agent", "SRE_Agent", "fix_linting", payload)
    ok, err = signer.verify_call(signed)
"""
from __future__ import annotations

import hashlib
import hmac
import json
import logging
import os
import secrets
import time
from dataclasses import dataclass
from typing import Any, Dict, Optional, Tuple

logger = logging.getLogger(__name__)

_DEV_KEY = b"agenticqa-dev-agent-call-secret-change-in-prod"
_MAX_AGE_SECONDS = 300   # 5 minutes
_NONCE_LEN = 16


def _get_key() -> bytes:
    raw = (
        os.environ.get("AGENTICQA_AGENT_CALL_SECRET")
        or os.environ.get("AGENTICQA_PROVENANCE_SECRET")
    )
    if raw:
        return raw.encode()
    logger.warning(
        "AGENTICQA_AGENT_CALL_SECRET not set — using insecure dev key. "
        "Set this env var before deploying to production."
    )
    return _DEV_KEY


@dataclass
class SignedCall:
    from_agent: str
    to_agent: str
    task_type: str
    payload_hash: str          # SHA-256 hex of json.dumps(payload, sort_keys=True)
    timestamp: float           # unix epoch (float)
    nonce: str                 # random hex string, prevents replay
    signature: str             # HMAC-SHA256 hex
    payload: Dict[str, Any]    # original payload (not signed again; verify via payload_hash)


@dataclass
class VerificationResult:
    ok: bool
    error: Optional[str] = None


class AgentCallSigner:
    """Signs and verifies inter-agent delegation calls."""

    def __init__(self) -> None:
        self._key = _get_key()

    # ── Sign ─────────────────────────────────────────────────────────────────

    def sign_call(
        self,
        from_agent: str,
        to_agent: str,
        task_type: str,
        payload: Dict[str, Any],
    ) -> SignedCall:
        """Produce a SignedCall ready to send to the target agent."""
        payload_hash = self._hash_payload(payload)
        timestamp = time.time()
        nonce = secrets.token_hex(_NONCE_LEN)
        sig = self._compute_sig(from_agent, to_agent, task_type, payload_hash, timestamp, nonce)
        return SignedCall(
            from_agent=from_agent,
            to_agent=to_agent,
            task_type=task_type,
            payload_hash=payload_hash,
            timestamp=timestamp,
            nonce=nonce,
            signature=sig,
            payload=payload,
        )

    # ── Verify ───────────────────────────────────────────────────────────────

    def verify_call(self, call: SignedCall) -> Tuple[bool, Optional[str]]:
        """Return (True, None) if signature is valid and fresh; (False, reason) otherwise."""
        age = time.time() - call.timestamp
        if age > _MAX_AGE_SECONDS:
            return False, f"Call expired: age={age:.0f}s > {_MAX_AGE_SECONDS}s"
        if age < -10:
            return False, f"Call timestamp is in the future by {-age:.0f}s (clock skew?)"

        actual_hash = self._hash_payload(call.payload)
        if not hmac.compare_digest(actual_hash, call.payload_hash):
            return False, "Payload has been tampered (hash mismatch)"

        expected_sig = self._compute_sig(
            call.from_agent, call.to_agent, call.task_type,
            call.payload_hash, call.timestamp, call.nonce,
        )
        if not hmac.compare_digest(expected_sig, call.signature):
            return False, "Signature invalid — possible forgery or key mismatch"

        return True, None

    # ── Helpers ───────────────────────────────────────────────────────────────

    @staticmethod
    def _hash_payload(payload: Dict[str, Any]) -> str:
        return hashlib.sha256(
            json.dumps(payload, sort_keys=True, default=str).encode()
        ).hexdigest()

    def _compute_sig(
        self,
        from_agent: str,
        to_agent: str,
        task_type: str,
        payload_hash: str,
        timestamp: float,
        nonce: str,
    ) -> str:
        canonical = f"{from_agent}|{to_agent}|{task_type}|{payload_hash}|{timestamp:.6f}|{nonce}"
        return hmac.new(self._key, canonical.encode(), hashlib.sha256).hexdigest()

    # ── Dict serialisation (for JSON transport) ───────────────────────────────

    @staticmethod
    def to_dict(call: SignedCall) -> Dict[str, Any]:
        return {
            "from_agent": call.from_agent,
            "to_agent": call.to_agent,
            "task_type": call.task_type,
            "payload_hash": call.payload_hash,
            "timestamp": call.timestamp,
            "nonce": call.nonce,
            "signature": call.signature,
            "payload": call.payload,
        }

    @staticmethod
    def from_dict(d: Dict[str, Any]) -> SignedCall:
        return SignedCall(**d)
