"""
AgentScopeLeaseManager — hard operation caps for agent sessions.

The Gap
-------
"Stop" commands fail when agents are mid-loop (the OpenClaw incident).
Soft advisory limits fail. This module enforces hard operation caps
at the infrastructure level — the lease manager, not the agent, decides
whether an action proceeds. When the lease is exhausted or expired, the
agent is refused at the gate regardless of what it wants to do.

Lease Types
-----------
readonly   — reads only; any write/delete blocked
standard   — reads + limited writes; deletes blocked
elevated   — reads + writes + deletes (each capped)
custom     — caller specifies all caps explicitly

Usage
-----
    from agenticqa.security.scope_lease_manager import AgentScopeLeaseManager, LeaseConfig

    mgr = AgentScopeLeaseManager()

    # Grant a lease: agent may delete at most 5 emails, write at most 20,
    # session expires in 5 minutes
    lease_id = mgr.create_lease("openclaw-agent", "session-42",
        LeaseConfig(max_deletes=5, max_writes=20, lease_ttl_seconds=300))

    # Before each tool call:
    allowed, reason = mgr.check_and_consume(lease_id, "delete")
    if not allowed:
        raise PermissionError(reason)   # hard stop — agent cannot proceed
"""
from __future__ import annotations

import json
import os
import secrets
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Tuple

# Audit log path
_AUDIT_DIR = Path(os.getenv("AGENTICQA_SAFETY_DIR", ".agenticqa/safety"))

# Action type normalisation
_ACTION_ALIASES: Dict[str, str] = {
    # reads
    "get": "read", "list": "read", "fetch": "read", "search": "read",
    "query": "read", "view": "read", "find": "read", "describe": "read",
    # writes
    "create": "write", "update": "write", "set": "write", "put": "write",
    "post": "write", "patch": "write", "upload": "write", "save": "write",
    "move": "write", "rename": "write", "copy": "write", "send": "write",
    # deletes
    "delete": "delete", "remove": "delete", "drop": "delete", "purge": "delete",
    "wipe": "delete", "erase": "delete", "clear": "delete", "bulk_delete": "delete",
    # executes
    "execute": "execute", "run": "execute", "spawn": "execute", "exec": "execute",
    "deploy": "execute", "trigger": "execute",
}

_UNLIMITED = 2 ** 31  # sentinel for "no cap"


# ── Dataclasses ────────────────────────────────────────────────────────────────

@dataclass
class LeaseConfig:
    """Defines the operation caps for a lease."""
    max_reads: int = _UNLIMITED
    max_writes: int = 50
    max_deletes: int = 0          # default: deletes blocked
    max_executes: int = 0         # default: shell exec blocked
    lease_ttl_seconds: int = 600  # 10 min default
    require_confirm_above: int = 3  # warn (not block) when N ops of any type exceeded
    label: str = "standard"

    @classmethod
    def readonly(cls) -> "LeaseConfig":
        return cls(max_reads=_UNLIMITED, max_writes=0, max_deletes=0, max_executes=0, label="readonly")

    @classmethod
    def standard(cls) -> "LeaseConfig":
        return cls(max_reads=_UNLIMITED, max_writes=50, max_deletes=0, max_executes=0, label="standard")

    @classmethod
    def elevated(cls, max_deletes: int = 10, max_executes: int = 5) -> "LeaseConfig":
        return cls(max_reads=_UNLIMITED, max_writes=200, max_deletes=max_deletes,
                   max_executes=max_executes, label="elevated")


@dataclass
class ScopeLease:
    """Active lease record with runtime counters."""
    lease_id: str
    agent_id: str
    session_id: str
    config: LeaseConfig
    created_at: float = field(default_factory=time.time)
    # Runtime counters
    reads_used: int = 0
    writes_used: int = 0
    deletes_used: int = 0
    executes_used: int = 0
    total_ops: int = 0
    is_active: bool = True
    revoked_reason: str = ""

    @property
    def expires_at(self) -> float:
        return self.created_at + self.config.lease_ttl_seconds

    @property
    def is_expired(self) -> bool:
        return time.time() > self.expires_at

    @property
    def seconds_remaining(self) -> float:
        return max(0.0, self.expires_at - time.time())

    def _cap_for(self, action: str) -> int:
        return {
            "read": self.config.max_reads,
            "write": self.config.max_writes,
            "delete": self.config.max_deletes,
            "execute": self.config.max_executes,
        }.get(action, 0)

    def _used_for(self, action: str) -> int:
        return {
            "read": self.reads_used,
            "write": self.writes_used,
            "delete": self.deletes_used,
            "execute": self.executes_used,
        }.get(action, 0)

    def to_dict(self) -> dict:
        return {
            "lease_id": self.lease_id,
            "agent_id": self.agent_id,
            "session_id": self.session_id,
            "label": self.config.label,
            "is_active": self.is_active,
            "is_expired": self.is_expired,
            "seconds_remaining": round(self.seconds_remaining, 1),
            "revoked_reason": self.revoked_reason,
            "caps": {
                "reads": self.config.max_reads if self.config.max_reads < _UNLIMITED else "unlimited",
                "writes": self.config.max_writes,
                "deletes": self.config.max_deletes,
                "executes": self.config.max_executes,
            },
            "used": {
                "reads": self.reads_used,
                "writes": self.writes_used,
                "deletes": self.deletes_used,
                "executes": self.executes_used,
                "total": self.total_ops,
            },
            "created_at": self.created_at,
            "expires_at": self.expires_at,
        }


# ── Manager ────────────────────────────────────────────────────────────────────

class AgentScopeLeaseManager:
    """
    Issues, tracks, and enforces operation-cap leases for agent sessions.

    A lease is refused (not just warned) when:
    - The lease does not exist
    - The lease has expired
    - The lease has been explicitly revoked
    - The requested action exceeds the configured cap
    """

    def __init__(self, audit_path: Optional[Path] = None) -> None:
        self._leases: Dict[str, ScopeLease] = {}
        self._audit_path = audit_path or _AUDIT_DIR

    # ── Lease lifecycle ────────────────────────────────────────────────────────

    def create_lease(
        self,
        agent_id: str,
        session_id: str,
        config: Optional[LeaseConfig] = None,
    ) -> str:
        """Create a new lease, return lease_id."""
        if config is None:
            config = LeaseConfig.standard()
        lease_id = secrets.token_hex(12)
        lease = ScopeLease(
            lease_id=lease_id,
            agent_id=agent_id,
            session_id=session_id,
            config=config,
        )
        self._leases[lease_id] = lease
        self._audit({"event": "lease_created", **lease.to_dict()})
        return lease_id

    def revoke_lease(self, lease_id: str, reason: str = "manual revocation") -> bool:
        """Immediately revoke a lease — all subsequent checks will fail."""
        lease = self._leases.get(lease_id)
        if not lease:
            return False
        lease.is_active = False
        lease.revoked_reason = reason
        self._audit({"event": "lease_revoked", "lease_id": lease_id, "reason": reason,
                     "timestamp": time.time()})
        return True

    def get_lease(self, lease_id: str) -> Optional[ScopeLease]:
        return self._leases.get(lease_id)

    def get_lease_status(self, lease_id: str) -> Optional[dict]:
        lease = self._leases.get(lease_id)
        return lease.to_dict() if lease else None

    def list_active_leases(self) -> List[dict]:
        return [l.to_dict() for l in self._leases.values()
                if l.is_active and not l.is_expired]

    # ── Enforcement ───────────────────────────────────────────────────────────

    def check_and_consume(
        self, lease_id: str, raw_action: str
    ) -> Tuple[bool, str]:
        """
        Check if an action is allowed, and consume one operation unit if so.

        Returns (allowed: bool, reason: str).
        If allowed=False, the agent MUST NOT proceed — this is a hard block.
        """
        action = _normalise_action(raw_action)

        lease = self._leases.get(lease_id)
        if not lease:
            return False, f"No lease found for id '{lease_id}'"

        if not lease.is_active:
            return False, f"Lease '{lease_id}' has been revoked: {lease.revoked_reason}"

        if lease.is_expired:
            lease.is_active = False
            lease.revoked_reason = "TTL expired"
            self._audit({"event": "lease_expired", "lease_id": lease_id, "timestamp": time.time()})
            return False, f"Lease '{lease_id}' expired {abs(lease.seconds_remaining):.0f}s ago"

        cap = lease._cap_for(action)
        used = lease._used_for(action)

        if cap == 0:
            return False, (
                f"Lease '{lease_id}' (label={lease.config.label}) prohibits {action} operations entirely. "
                f"Request a new lease with elevated permissions."
            )

        if used >= cap:
            reason = (
                f"Lease '{lease_id}' {action} cap exhausted: "
                f"{used}/{cap} used. Agent halted for safety."
            )
            self._audit({"event": "cap_exhausted", "lease_id": lease_id, "action": action,
                         "used": used, "cap": cap, "timestamp": time.time()})
            return False, reason

        # Consume
        self._consume(lease, action)

        remaining = cap - lease._used_for(action)
        warn = ""
        if remaining <= max(1, cap // 5):   # warn when ≤20% remaining
            warn = f" ⚠ Only {remaining} {action} op(s) remaining on this lease."

        return True, f"Allowed. {action.capitalize()} {used + 1}/{cap}.{warn}"

    # ── Bulk check (no consume) ───────────────────────────────────────────────

    def peek(self, lease_id: str, raw_action: str) -> Tuple[bool, str]:
        """Check without consuming. Use for pre-flight checks."""
        action = _normalise_action(raw_action)
        lease = self._leases.get(lease_id)
        if not lease:
            return False, "No lease found"
        if not lease.is_active or lease.is_expired:
            return False, "Lease inactive or expired"
        cap = lease._cap_for(action)
        used = lease._used_for(action)
        if cap == 0:
            return False, f"{action} prohibited by lease"
        if used >= cap:
            return False, f"{action} cap exhausted ({used}/{cap})"
        return True, f"{action} allowed ({used}/{cap} used)"

    # ── Internals ─────────────────────────────────────────────────────────────

    def _consume(self, lease: ScopeLease, action: str) -> None:
        if action == "read":
            lease.reads_used += 1
        elif action == "write":
            lease.writes_used += 1
        elif action == "delete":
            lease.deletes_used += 1
        elif action == "execute":
            lease.executes_used += 1
        lease.total_ops += 1
        self._audit({
            "event": "op_consumed",
            "lease_id": lease.lease_id,
            "agent_id": lease.agent_id,
            "action": action,
            "total_ops": lease.total_ops,
            "timestamp": time.time(),
        })

    def _audit(self, record: dict) -> None:
        try:
            self._audit_path.mkdir(parents=True, exist_ok=True)
            with (self._audit_path / "scope_lease_audit.jsonl").open("a", encoding="utf-8") as f:
                f.write(json.dumps(record) + "\n")
        except Exception:
            pass


def _normalise_action(raw: str) -> str:
    """Map a tool name to a canonical action type."""
    low = raw.lower().strip()
    return _ACTION_ALIASES.get(low, low if low in {"read", "write", "delete", "execute"} else "write")
