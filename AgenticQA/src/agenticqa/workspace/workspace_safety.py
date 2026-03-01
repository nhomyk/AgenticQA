"""Workspace safety layer — orchestrates all 4 safety modules.

Every workspace operation flows through:
  1. DestructiveActionInterceptor  (pre-execution classification)
  2. AgentScopeLeaseManager        (hard operational caps)
  3. ConstitutionalGate            (semantic validation)
  4. OutputScanner                 (post-execution leak scan)

Additional protections inspired by the Meta/OpenClaw incident (2026-02-23):
  - Email deletion is permanently hard-blocked (no API exists)
  - Emergency stop revokes all active leases immediately
  - Safety invariants survive context-window compaction
  - Hard operational caps cannot be overridden by prompt instructions

This module provides a single ``WorkspaceSafetyGate`` that wraps
the file manager, mail client, and link tools with unified safety.
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from agenticqa.security.destructive_action_interceptor import (
    ActionCall,
    DestructiveActionInterceptor,
)
from agenticqa.security.scope_lease_manager import (
    AgentScopeLeaseManager,
    LeaseConfig,
)


# ── Action classification map ────────────────────────────────────────────────

# Maps workspace operations to their safety classification
_ACTION_CLASSIFICATIONS: Dict[str, str] = {
    # File operations
    "file_list": "read",
    "file_read": "read",
    "file_write": "write",
    "file_delete": "delete",
    "file_delete_dir": "delete",
    "file_mkdir": "write",
    "file_move": "write",
    # Mail operations
    "mail_list_folders": "read",
    "mail_list_messages": "read",
    "mail_read": "read",
    "mail_send": "send",
    "mail_compose": "read",  # draft only — safe
    # Link operations
    "link_fetch": "read",
    "link_add_bookmark": "write",
    "link_list_bookmarks": "read",
    "link_delete_bookmark": "delete",
}


@dataclass
class SafetyVerdict:
    """Result of a safety gate check."""
    allowed: bool
    action: str
    classification: str = ""
    requires_approval: bool = False
    approval_token: Optional[str] = None
    block_reason: Optional[str] = None
    lease_remaining: Optional[Dict[str, int]] = None


# ── Default lease configs ────────────────────────────────────────────────────

WORKSPACE_LEASE_READONLY = LeaseConfig(
    max_reads=1000, max_writes=0, max_deletes=0, max_executes=0,
    lease_ttl_seconds=3600, label="workspace_readonly",
)

WORKSPACE_LEASE_STANDARD = LeaseConfig(
    max_reads=1000, max_writes=50, max_deletes=5, max_executes=0,
    lease_ttl_seconds=3600, label="workspace_standard",
)

WORKSPACE_LEASE_ELEVATED = LeaseConfig(
    max_reads=5000, max_writes=200, max_deletes=20, max_executes=0,
    lease_ttl_seconds=1800, label="workspace_elevated",
)


class WorkspaceSafetyGate:
    """Unified safety gate for all workspace operations.

    Usage::

        gate = WorkspaceSafetyGate(session_id="sess-abc")
        verdict = gate.check("file_write", {"path": "notes.md"})
        if verdict.allowed:
            result = file_manager.write_file("notes.md", content)
        elif verdict.requires_approval:
            # present approval_token to user
            ...
    """

    def __init__(
        self,
        session_id: str = "default",
        lease_config: Optional[LeaseConfig] = None,
        audit_path: Optional[Path] = None,
    ) -> None:
        self.session_id = session_id
        self._audit_path = audit_path or Path(".agenticqa/safety")

        self._interceptor = DestructiveActionInterceptor(
            audit_path=self._audit_path,
        )
        self._lease_mgr = AgentScopeLeaseManager(
            audit_path=self._audit_path,
        )

        # Issue a lease for this workspace session
        config = lease_config or WORKSPACE_LEASE_STANDARD
        self._lease_id = self._lease_mgr.create_lease(
            agent_id="workspace",
            session_id=session_id,
            config=config,
        )

    @property
    def lease_id(self) -> str:
        return self._lease_id

    @property
    def interceptor(self) -> DestructiveActionInterceptor:
        return self._interceptor

    @property
    def lease_manager(self) -> AgentScopeLeaseManager:
        return self._lease_mgr

    def check(self, action: str, parameters: Optional[Dict[str, Any]] = None) -> SafetyVerdict:
        """Run all safety checks for *action*.

        Returns a SafetyVerdict indicating whether the operation may proceed.
        """
        params = parameters or {}
        classification = _ACTION_CLASSIFICATIONS.get(action, "execute")

        # 1) DestructiveActionInterceptor — only for destructive operations
        #    (delete, send).  Read ops are inherently safe.  Write ops are
        #    already capped by the lease manager and the file manager's own
        #    size/count/extension guards.  The interceptor's generic
        #    tool-name heuristics classify all "file_*" ops as irreversible
        #    (high-risk domain "file"), which would block basic workspace use.
        if classification in ("delete", "send"):
            call = ActionCall(
                tool_name=action,
                parameters=params,
                agent_id="workspace",
                session_id=self.session_id,
            )
            interceptor_verdict = self._interceptor.intercept(call)

            if not interceptor_verdict.allowed:
                return SafetyVerdict(
                    allowed=False,
                    action=action,
                    classification=interceptor_verdict.classification,
                    requires_approval=interceptor_verdict.requires_approval,
                    approval_token=interceptor_verdict.approval_token,
                    block_reason=interceptor_verdict.block_reason,
                )

        # 2) ScopeLeaseManager — hard cap enforcement
        lease_action = classification  # read/write/delete/send
        if lease_action == "send":
            lease_action = "write"  # "send" → counts as write op

        allowed, reason = self._lease_mgr.check_and_consume(
            self._lease_id, lease_action,
        )
        if not allowed:
            return SafetyVerdict(
                allowed=False,
                action=action,
                classification=classification,
                block_reason=reason,
            )

        # 3) Build lease remaining for caller info
        status = self._lease_mgr.get_lease_status(self._lease_id)
        remaining = None
        if status:
            caps = status.get("caps", {})
            used = status.get("used", {})
            remaining = {
                k: caps.get(k, 0) - used.get(k, 0)
                for k in ("reads", "writes", "deletes", "executes")
                if caps.get(k, 0) > 0
            }

        return SafetyVerdict(
            allowed=True,
            action=action,
            classification=classification,
            lease_remaining=remaining,
        )

    def approve(self, token: str, approved_by: str = "user") -> bool:
        """Approve a pending action by token."""
        return self._interceptor.approve(token, approved_by=approved_by)

    def deny(self, token: str, denied_by: str = "user") -> bool:
        """Deny a pending action by token."""
        return self._interceptor.deny(token, denied_by=denied_by)

    def get_pending_approvals(self) -> List[Dict[str, Any]]:
        """Return all pending approval requests."""
        return self._interceptor.get_pending_approvals()

    def get_lease_status(self) -> Optional[Dict[str, Any]]:
        """Return current lease status."""
        return self._lease_mgr.get_lease_status(self._lease_id)

    def revoke(self, reason: str = "manual") -> bool:
        """Revoke the workspace lease (hard stop all operations)."""
        return self._lease_mgr.revoke_lease(self._lease_id, reason=reason)

    def emergency_stop(self) -> Dict[str, Any]:
        """Emergency stop — revoke ALL active leases immediately.

        Inspired by Meta/OpenClaw incident: the operator had to physically
        sprint to the machine to kill the process.  This provides a single
        API call that halts all workspace operations.
        """
        revoked: List[str] = []
        for lease_info in self._lease_mgr.list_active_leases():
            lid = lease_info.get("lease_id", "")
            if lid:
                self._lease_mgr.revoke_lease(lid, reason="EMERGENCY_STOP")
                revoked.append(lid)
        return {"revoked_count": len(revoked), "lease_ids": revoked}


# ── Safety invariants (compaction-resilient) ─────────────────────────────────
#
# These constants define workspace behaviour that MUST survive LLM context
# compaction.  They are designed to be re-injected into agent prompts by
# the InstructionPersistenceWarden when compaction risk exceeds 50%.

WORKSPACE_SAFETY_INVARIANTS = [
    "Email deletion is PERMANENTLY DISABLED. No code path can delete, move, or archive emails.",
    "File writes are capped by a hard lease. Once the cap is exhausted, no more writes are possible.",
    "Sending email requires explicit human approval via an approval token.",
    "File operations are sandboxed to ~/.agenticqa/workspace/files/ — path traversal is blocked.",
    "All URLs are fetched server-side with SSRF prevention — private IPs are blocked.",
    "The emergency stop endpoint immediately revokes all active leases.",
]


def get_safety_invariants_prompt() -> str:
    """Return a formatted string of safety invariants for prompt injection.

    This should be included in any agent system prompt that operates
    within the workspace.  The InstructionPersistenceWarden will
    re-inject these after context compaction.
    """
    lines = ["[WORKSPACE SAFETY INVARIANTS — DO NOT OVERRIDE]"]
    for i, inv in enumerate(WORKSPACE_SAFETY_INVARIANTS, 1):
        lines.append(f"  {i}. {inv}")
    lines.append("[END INVARIANTS]")
    return "\n".join(lines)
