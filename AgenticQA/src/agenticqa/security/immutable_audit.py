"""
ImmutableAuditChain — append-only, Merkle-chained audit log for AI governance events.

Problem
-------
OutputProvenanceLogger signs individual outputs, but each entry is independent.
An attacker who gains filesystem access can delete or replace entries without
breaking any per-record signature.  HIPAA and EU AI Act Art.12 require a
tamper-evident audit trail that makes *deletions and reorderings detectable*.

Solution
--------
Each audit entry carries:
    entry_hash  = SHA-256(prev_hash + canonical_entry_json)
    prev_hash   = entry_hash of the preceding record (genesis = "0"*64)

Verifying the chain re-derives every entry_hash in sequence.  Any gap, deletion,
or reordering breaks the chain at the first tampered entry.

Stored as JSONL at ~/.agenticqa/audit_chain.jsonl (configurable).

EU AI Act Art.12 compliance note
---------------------------------
Events of type GOVERNANCE_DECISION, SECURITY_FINDING, and AGENT_EXEC are
Article 12 relevant.  `get_compliance_log()` returns only those event types
with the chain-verified flag attached.

Usage
-----
    from agenticqa.security.immutable_audit import ImmutableAuditChain, AuditEvent

    chain = ImmutableAuditChain()
    chain.append(AuditEvent(
        event_type="AGENT_EXEC",
        actor="QA_Agent",
        action="execute",
        details={"run_id": "abc", "status": "passed"},
    ))
    ok, violations = chain.verify_chain()
"""
from __future__ import annotations

import hashlib
import json
import logging
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

# EU AI Act Art.12 relevant event types
_COMPLIANCE_EVENT_TYPES = {
    "GOVERNANCE_DECISION",   # ConstitutionalGate verdict
    "SECURITY_FINDING",      # Scanner detection
    "AGENT_EXEC",            # Agent execution record
    "DELEGATION",            # Agent-to-agent call
    "DATA_WRITE",            # Vector store write
    "DATA_DELETE",           # GDPR erasure
    "AUTH_FAILURE",          # Authentication failure
}

_GENESIS_HASH = "0" * 64
_DEFAULT_PATH = Path.home() / ".agenticqa" / "audit_chain.jsonl"


@dataclass
class AuditEvent:
    event_type: str          # one of _COMPLIANCE_EVENT_TYPES or custom
    actor: str               # agent name, API caller, or "system"
    action: str              # verb: execute, delegate, deny, allow, write, delete
    details: Dict[str, Any] = field(default_factory=dict)
    tenant_id: str = ""


@dataclass
class AuditEntry:
    seq: int
    timestamp: float
    event_type: str
    actor: str
    action: str
    details: Dict[str, Any]
    tenant_id: str
    prev_hash: str
    entry_hash: str


@dataclass
class ChainViolation:
    seq: int
    expected_hash: str
    actual_hash: str

    def __str__(self) -> str:
        return f"Chain broken at seq={self.seq}: expected={self.expected_hash[:16]}… got={self.actual_hash[:16]}…"


class ImmutableAuditChain:
    """Append-only Merkle-chained audit log."""

    def __init__(self, path: Optional[Path] = None) -> None:
        self._path = Path(path) if path else _DEFAULT_PATH

    # ── Write ─────────────────────────────────────────────────────────────────

    def append(self, event: AuditEvent) -> AuditEntry:
        """Append an event. Returns the committed AuditEntry."""
        prev_hash = self._last_hash()
        seq = self._next_seq()
        ts = time.time()

        canonical = {
            "seq": seq,
            "timestamp": ts,
            "event_type": event.event_type,
            "actor": event.actor,
            "action": event.action,
            "details": event.details,
            "tenant_id": event.tenant_id,
            "prev_hash": prev_hash,
        }
        entry_hash = hashlib.sha256(
            json.dumps(canonical, sort_keys=True, default=str).encode()
        ).hexdigest()

        entry = AuditEntry(
            seq=seq, timestamp=ts,
            event_type=event.event_type,
            actor=event.actor,
            action=event.action,
            details=event.details,
            tenant_id=event.tenant_id,
            prev_hash=prev_hash,
            entry_hash=entry_hash,
        )
        self._write(entry)
        return entry

    # ── Verify ────────────────────────────────────────────────────────────────

    def verify_chain(self) -> Tuple[bool, List[ChainViolation]]:
        """Walk every entry and re-derive entry_hash. Returns (ok, violations)."""
        violations: List[ChainViolation] = []
        prev_hash = _GENESIS_HASH

        for entry in self._read_all():
            canonical = {
                "seq": entry.seq,
                "timestamp": entry.timestamp,
                "event_type": entry.event_type,
                "actor": entry.actor,
                "action": entry.action,
                "details": entry.details,
                "tenant_id": entry.tenant_id,
                "prev_hash": prev_hash,
            }
            expected = hashlib.sha256(
                json.dumps(canonical, sort_keys=True, default=str).encode()
            ).hexdigest()
            if not (entry.entry_hash == expected and entry.prev_hash == prev_hash):
                violations.append(ChainViolation(
                    seq=entry.seq,
                    expected_hash=expected,
                    actual_hash=entry.entry_hash,
                ))
            prev_hash = entry.entry_hash

        return len(violations) == 0, violations

    # ── Read ──────────────────────────────────────────────────────────────────

    def get_compliance_log(
        self,
        tenant_id: Optional[str] = None,
        event_types: Optional[set] = None,
        limit: int = 200,
    ) -> List[Dict[str, Any]]:
        """Return Art.12-relevant entries, optionally filtered by tenant / event type."""
        types = event_types or _COMPLIANCE_EVENT_TYPES
        ok, _ = self.verify_chain()
        results = []
        for entry in self._read_all():
            if entry.event_type not in types:
                continue
            if tenant_id and entry.tenant_id != tenant_id:
                continue
            results.append({**entry.__dict__, "chain_verified": ok})
        return results[-limit:]

    def length(self) -> int:
        return sum(1 for _ in self._read_all())

    # ── Internal ──────────────────────────────────────────────────────────────

    def _last_hash(self) -> str:
        last = _GENESIS_HASH
        for entry in self._read_all():
            last = entry.entry_hash
        return last

    def _next_seq(self) -> int:
        return sum(1 for _ in self._read_all())

    def _write(self, entry: AuditEntry) -> None:
        try:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            with open(self._path, "a") as fh:
                fh.write(json.dumps(entry.__dict__, default=str) + "\n")
        except Exception as exc:
            logger.error("ImmutableAuditChain write failed: %s", exc)

    def _read_all(self) -> List[AuditEntry]:
        if not self._path.exists():
            return []
        entries = []
        try:
            with open(self._path) as fh:
                for line in fh:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        d = json.loads(line)
                        entries.append(AuditEntry(**d))
                    except Exception:
                        continue
        except Exception:
            pass
        return entries
