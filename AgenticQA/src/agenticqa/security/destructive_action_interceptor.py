"""
DestructiveActionInterceptor — intercepts agent tool calls BEFORE execution.

The Gap
-------
ConstitutionalGate reviews agent *output text* after the fact.
This module intercepts *tool calls* before they execute — the only
way to prevent irreversible actions like the OpenClaw email-deletion incident,
where the agent ignored STOP commands because it was already mid-loop.

Classification
--------------
SAFE         — read-only, no side effects (list, get, read, search, fetch)
REVERSIBLE   — writes that can be undone (create draft, move to trash, write file)
IRREVERSIBLE — permanent single-item changes (send email, delete file, overwrite)
DESTRUCTIVE  — mass/bulk operations on real data (bulk delete, drop table, purge)

Usage
-----
    from agenticqa.security.destructive_action_interceptor import (
        DestructiveActionInterceptor, ActionCall
    )

    interceptor = DestructiveActionInterceptor()
    call = ActionCall(tool_name="delete_email", parameters={"all": True}, agent_id="myagent")
    verdict = interceptor.intercept(call)

    if not verdict.allowed:
        # block execution, optionally request human approval
        token = verdict.approval_token
        # ... present to human, get approval ...
        if interceptor.approve(token):
            proceed()
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import secrets
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Tuple

# ── Pattern tables ─────────────────────────────────────────────────────────────

# Tool names that are definitively read-only
_SAFE_TOOLS = re.compile(
    r"\b(get|list|read|fetch|search|find|query|view|show|describe|"
    r"explain|preview|check|inspect|status|ping|health|count|summarize)\b",
    re.IGNORECASE,
)

# Tool name patterns that imply irreversible single-item mutation
_IRREVERSIBLE_TOOLS = re.compile(
    r"\b(delete|remove|drop|send|publish|deploy|execute|run_command|"
    r"overwrite|replace|truncate|format|wipe|erase|kill|terminate|"
    r"shutdown|revoke|expire|cancel|close|archive_permanently)\b",
    re.IGNORECASE,
)

# Tool name patterns that imply bulk / mass operations (always DESTRUCTIVE)
_DESTRUCTIVE_TOOLS = re.compile(
    r"\b(bulk|batch|mass|purge|sweep|nuke|flush|clear_all|delete_all|"
    r"drop_table|drop_database|rm_rf|reset_all|factory_reset)\b",
    re.IGNORECASE,
)

# Parameter keys/values that escalate classification
_BULK_PARAM_KEYS = frozenset(
    {"all", "recursive", "force", "bulk", "batch", "entire", "purge",
     "delete_all", "wipe", "overwrite_all", "ignore_errors"}
)
_WILDCARD_VALUES = re.compile(r"(\*|\.all|/all|all_items|delete_all|true)", re.IGNORECASE)

# Target domains and their default risk tier
_HIGH_RISK_DOMAINS = frozenset(
    {"email", "mail", "inbox", "calendar", "database", "db", "table",
     "filesystem", "file", "s3", "bucket", "repo", "git", "process",
     "container", "pod", "deployment", "credential", "secret", "key"}
)

# Classification constants
SAFE = "safe"
REVERSIBLE = "reversible"
IRREVERSIBLE = "irreversible"
DESTRUCTIVE = "destructive"

_CLASSIFICATION_ORDER = {SAFE: 0, REVERSIBLE: 1, IRREVERSIBLE: 2, DESTRUCTIVE: 3}

# How long approval tokens stay valid (seconds)
_APPROVAL_TTL = int(os.getenv("AGENTICQA_APPROVAL_TTL", "300"))  # 5 min default

# Path for audit JSONL
_AUDIT_DIR = Path(os.getenv("AGENTICQA_SAFETY_DIR", ".agenticqa/safety"))


# ── Dataclasses ────────────────────────────────────────────────────────────────

@dataclass
class ActionCall:
    """Represents a tool call an agent wants to make."""
    tool_name: str
    parameters: dict = field(default_factory=dict)
    agent_id: str = "unknown"
    session_id: str = ""
    context_snippet: str = ""    # last ~200 chars of agent reasoning
    call_id: str = field(default_factory=lambda: secrets.token_hex(8))


@dataclass
class ActionVerdict:
    """Result of intercepting an ActionCall."""
    call: ActionCall
    classification: str          # safe | reversible | irreversible | destructive
    risk_level: str              # low | medium | high | critical
    allowed: bool                # False → blocked pending human approval
    requires_approval: bool
    approval_token: Optional[str]
    block_reason: str
    evidence: List[str]
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> dict:
        return {
            "call_id": self.call.call_id,
            "tool_name": self.call.tool_name,
            "agent_id": self.call.agent_id,
            "session_id": self.call.session_id,
            "classification": self.classification,
            "risk_level": self.risk_level,
            "allowed": self.allowed,
            "requires_approval": self.requires_approval,
            "approval_token": self.approval_token,
            "block_reason": self.block_reason,
            "evidence": self.evidence,
            "timestamp": self.timestamp,
        }


# ── Core classifier ────────────────────────────────────────────────────────────

class ActionClassifier:
    """Pure classifier — no state, no side-effects."""

    def classify(self, tool_name: str, parameters: dict) -> Tuple[str, List[str]]:
        """
        Returns (classification, evidence_list).
        Classification: safe | reversible | irreversible | destructive

        Tool names are split on underscores/hyphens so that compound names like
        'get_email', 'bulk_delete', 'list_files' match their verb component correctly.
        """
        evidence: List[str] = []
        classification = SAFE

        name_lower = tool_name.lower()
        # Extract individual words from compound tool names (get_email → ["get", "email"])
        parts = re.split(r"[_\-\.\s]+", name_lower)
        first_verb = parts[0] if parts else name_lower

        # Check destructive pattern against all parts (bulk_delete → "bulk" matches)
        if any(_DESTRUCTIVE_TOOLS.search(p) for p in parts):
            classification = DESTRUCTIVE
            evidence.append(f"Tool name '{tool_name}' matches destructive pattern (bulk/purge/wipe)")

        # Check irreversible against all parts (delete_file → "delete" matches)
        elif any(_IRREVERSIBLE_TOOLS.search(p) for p in parts):
            classification = IRREVERSIBLE
            evidence.append(f"Tool name '{tool_name}' matches irreversible pattern (delete/send/deploy)")

        # Safe read-only: match against first verb (get_email → "get" is safe)
        elif _SAFE_TOOLS.search(first_verb):
            classification = SAFE

        else:
            # Unknown tool — treat as reversible by default (cautious but not blocking)
            classification = REVERSIBLE
            evidence.append(f"Tool name '{tool_name}' is unrecognised — defaulting to reversible")

        # Parameter escalation: bulk keys → upgrade to DESTRUCTIVE
        param_keys_lower = {str(k).lower() for k in parameters}
        bulk_keys_found = param_keys_lower & _BULK_PARAM_KEYS
        if bulk_keys_found:
            new_cls = DESTRUCTIVE
            evidence.append(f"Bulk parameter key(s) found: {bulk_keys_found}")
            classification = _upgrade(classification, new_cls)

        # Parameter escalation: wildcard values → upgrade to DESTRUCTIVE
        for k, v in parameters.items():
            if _WILDCARD_VALUES.search(str(v)):
                evidence.append(f"Parameter '{k}={v}' contains wildcard/all-items value")
                classification = _upgrade(classification, DESTRUCTIVE)
                break

        # High-risk domain detection in tool name → upgrade reversible→irreversible
        for domain in _HIGH_RISK_DOMAINS:
            if domain in name_lower:
                evidence.append(f"High-risk domain '{domain}' in tool name")
                if classification == REVERSIBLE:
                    classification = IRREVERSIBLE
                break

        return classification, evidence

    @staticmethod
    def classification_to_risk(classification: str) -> str:
        return {
            SAFE: "low",
            REVERSIBLE: "medium",
            IRREVERSIBLE: "high",
            DESTRUCTIVE: "critical",
        }.get(classification, "high")


def _upgrade(current: str, candidate: str) -> str:
    """Return whichever classification is more severe."""
    if _CLASSIFICATION_ORDER.get(candidate, 0) > _CLASSIFICATION_ORDER.get(current, 0):
        return candidate
    return current


# ── Interceptor ────────────────────────────────────────────────────────────────

class DestructiveActionInterceptor:
    """
    Intercepts agent tool calls, classifies them, and blocks destructive/irreversible
    actions pending human approval.

    Thread-safe for single-process use (in-memory pending queue protected by dict ops).
    """

    def __init__(
        self,
        block_on: Tuple[str, ...] = (IRREVERSIBLE, DESTRUCTIVE),
        auto_approve_reversible: bool = True,
        audit_path: Optional[Path] = None,
    ) -> None:
        """
        Args:
            block_on: Classification levels that require human approval.
            auto_approve_reversible: If True, REVERSIBLE actions are allowed without approval.
            audit_path: Directory for JSONL audit log. Defaults to .agenticqa/safety/.
        """
        self._block_on = frozenset(block_on)
        self._auto_approve_reversible = auto_approve_reversible
        self._classifier = ActionClassifier()
        self._pending: Dict[str, dict] = {}   # token → verdict dict + expiry
        self._audit_path = audit_path or _AUDIT_DIR
        self._counters: Dict[str, int] = {}   # agent_id → destructive action count

    # ── Public API ─────────────────────────────────────────────────────────────

    def intercept(self, call: ActionCall) -> ActionVerdict:
        """Classify and gate an action call. Returns a verdict."""
        classification, evidence = self._classifier.classify(
            call.tool_name, call.parameters
        )
        risk_level = ActionClassifier.classification_to_risk(classification)

        needs_approval = classification in self._block_on
        if classification == REVERSIBLE and self._auto_approve_reversible:
            needs_approval = False

        approval_token: Optional[str] = None
        allowed = True
        block_reason = ""

        if needs_approval:
            allowed = False
            approval_token = self._create_approval_token(call, classification)
            block_reason = (
                f"Action classified as {classification.upper()} — "
                f"requires human approval before execution. "
                f"Approval token: {approval_token}"
            )
            # Track destructive action count per agent
            self._counters[call.agent_id] = self._counters.get(call.agent_id, 0) + 1

        verdict = ActionVerdict(
            call=call,
            classification=classification,
            risk_level=risk_level,
            allowed=allowed,
            requires_approval=needs_approval,
            approval_token=approval_token,
            block_reason=block_reason,
            evidence=evidence,
        )
        self._audit(verdict)
        return verdict

    def approve(self, token: str, approved_by: str = "human") -> bool:
        """
        Approve a pending action by token.
        Returns True if the token was valid and not expired.
        """
        entry = self._pending.get(token)
        if not entry:
            return False  # unknown token
        if time.time() > entry["expires_at"]:
            del self._pending[token]
            return False  # expired
        entry["approved"] = True
        entry["approved_by"] = approved_by
        entry["approved_at"] = time.time()
        self._audit_approval(token, entry, approved_by)
        return True

    def deny(self, token: str, denied_by: str = "human") -> bool:
        """Explicitly deny a pending action."""
        entry = self._pending.get(token)
        if not entry:
            return False
        del self._pending[token]
        return True

    def is_approved(self, token: str) -> bool:
        """Check if a token has been approved (and not expired)."""
        entry = self._pending.get(token)
        if not entry:
            return False
        if time.time() > entry["expires_at"]:
            del self._pending[token]
            return False
        return entry.get("approved", False)

    def get_pending_approvals(self) -> List[dict]:
        """Return all pending (unapproved, unexpired) approval requests."""
        now = time.time()
        expired = [t for t, e in self._pending.items() if now > e["expires_at"]]
        for t in expired:
            del self._pending[t]
        return [
            {**e, "token": t}
            for t, e in self._pending.items()
            if not e.get("approved", False)
        ]

    def agent_destructive_count(self, agent_id: str) -> int:
        """How many destructive/irreversible actions this agent has attempted."""
        return self._counters.get(agent_id, 0)

    # ── Internals ──────────────────────────────────────────────────────────────

    def _create_approval_token(self, call: ActionCall, classification: str) -> str:
        token = secrets.token_urlsafe(24)
        self._pending[token] = {
            "call_id": call.call_id,
            "tool_name": call.tool_name,
            "agent_id": call.agent_id,
            "session_id": call.session_id,
            "parameters": call.parameters,
            "classification": classification,
            "created_at": time.time(),
            "expires_at": time.time() + _APPROVAL_TTL,
            "approved": False,
        }
        return token

    def _audit(self, verdict: ActionVerdict) -> None:
        try:
            self._audit_path.mkdir(parents=True, exist_ok=True)
            log_path = self._audit_path / "action_intercept_audit.jsonl"
            with log_path.open("a", encoding="utf-8") as f:
                f.write(json.dumps(verdict.to_dict()) + "\n")
        except Exception:
            pass  # non-blocking audit

    def _audit_approval(self, token: str, entry: dict, approved_by: str) -> None:
        try:
            self._audit_path.mkdir(parents=True, exist_ok=True)
            log_path = self._audit_path / "action_intercept_audit.jsonl"
            with log_path.open("a", encoding="utf-8") as f:
                f.write(json.dumps({
                    "event": "approval_granted",
                    "token": token,
                    "tool_name": entry.get("tool_name"),
                    "agent_id": entry.get("agent_id"),
                    "approved_by": approved_by,
                    "timestamp": time.time(),
                }) + "\n")
        except Exception:
            pass
