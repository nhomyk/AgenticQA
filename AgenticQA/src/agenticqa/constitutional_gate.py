"""Constitutional pre-action check for AgenticQA agents.

Loads constitution.yaml and agent_scopes.yaml once at module import and
evaluates any proposed action against:
  - Tier 1 laws (DENY)
  - Tier 2 laws (REQUIRE_APPROVAL)
  - Agent file-scope declarations (T1-006 — DENY if out of scope)

Usage:
    from agenticqa.constitutional_gate import check_action, check_file_scope

    # Full constitutional check (includes scope if agent + target_path present)
    result = check_action(
        action_type="write",
        context={"agent": "SDET_Agent", "target_path": ".github/workflows/ci.yml",
                 "trace_id": "tr-001"},
    )
    # {"verdict": "DENY", "law": "T1-006", "name": "agent_file_scope_violation", ...}

    # Direct scope check
    result = check_file_scope("SRE_Agent", "write", ".github/workflows/deploy.yml")
    # {"verdict": "ALLOW", ...}
"""

from __future__ import annotations

import fnmatch
import os
from pathlib import Path
from typing import Any, Dict, List, Optional

try:
    import yaml as _yaml
except ImportError:  # PyYAML is optional — constitution still loads from dict
    _yaml = None  # type: ignore

_CONSTITUTION_PATH = Path(__file__).parent / "constitution.yaml"
_SCOPES_PATH = Path(__file__).parent / "agent_scopes.yaml"

# ---------------------------------------------------------------------------
# Load constitution + agent scopes
# ---------------------------------------------------------------------------

def _load_constitution() -> Dict[str, Any]:
    if _yaml is not None and _CONSTITUTION_PATH.exists():
        with open(_CONSTITUTION_PATH, "r") as f:
            return _yaml.safe_load(f) or {}
    return {}


def _resolve_scopes_path() -> Path:
    """Resolve agent scopes path with per-repo and env-var override support.

    Resolution order (first found wins):
    1. AGENTICQA_SCOPES_PATH environment variable
    2. .agenticqa/agent_scopes.yaml in the current working directory
    3. Package default (agent_scopes.yaml next to this file)
    """
    env_path = os.environ.get("AGENTICQA_SCOPES_PATH")
    if env_path:
        p = Path(env_path)
        if p.exists():
            return p

    repo_override = Path.cwd() / ".agenticqa" / "agent_scopes.yaml"
    if repo_override.exists():
        return repo_override

    return _SCOPES_PATH


def _load_scopes() -> Dict[str, Any]:
    path = _resolve_scopes_path()
    if _yaml is not None and path.exists():
        with open(path, "r") as f:
            data = _yaml.safe_load(f) or {}
            # Strip top-level metadata keys (version, etc.)
            return {k: v for k, v in data.items() if isinstance(v, dict) and "read" in v or "write" in v or "deny" in v}
    return {}


_CONSTITUTION: Dict[str, Any] = _load_constitution()
_AGENT_SCOPES: Dict[str, Any] = _load_scopes()


def get_constitution() -> Dict[str, Any]:
    """Return the raw parsed constitution dict (for the API endpoint)."""
    return _CONSTITUTION


def get_agent_scopes() -> Dict[str, Any]:
    """Return all agent scope declarations (for the API endpoint)."""
    return _AGENT_SCOPES


# ---------------------------------------------------------------------------
# File scope enforcement (T1-006)
# ---------------------------------------------------------------------------

_WRITE_ACTIONS = {"write", "delete", "modify", "insert", "update", "create", "overwrite", "truncate", "drop", "purge"}
_READ_ACTIONS = {"read", "scan", "analyze", "inspect", "list"}


def _path_matches(file_path: str, pattern: str) -> bool:
    """Match a file path against a glob pattern with ** support."""
    fp = file_path.replace("\\", "/").lstrip("./").lstrip("/")
    pat = pattern.replace("\\", "/").lstrip("./").lstrip("/").rstrip("/")

    if pat == "**":
        return True

    # Pattern like "tests/**" — match directory and all contents
    if pat.endswith("/**"):
        prefix = pat[:-3]
        return fp == prefix or fp.startswith(prefix + "/")

    # Pattern like "**/*.yml" — match at any depth
    if pat.startswith("**/"):
        suffix = pat[3:]
        basename = fp.split("/")[-1]
        return fnmatch.fnmatch(basename, suffix) or fnmatch.fnmatch(fp, suffix)

    # Pattern with ** in the middle — split and check prefix + suffix
    if "**" in pat:
        parts = pat.split("**", 1)
        return fp.startswith(parts[0]) and (not parts[1] or fnmatch.fnmatch(fp, pat.replace("**", "*")))

    # No **, use fnmatch: match full path OR just the basename
    return fnmatch.fnmatch(fp, pat) or fnmatch.fnmatch(fp.split("/")[-1], pat)


def _matches_any(file_path: str, patterns: List[str]) -> bool:
    return any(_path_matches(file_path, p) for p in patterns)


def check_file_scope(
    agent_name: str,
    action: str,
    file_path: str,
) -> Dict[str, Any]:
    """Check whether an agent is permitted to perform action on file_path.

    Args:
        agent_name: Agent identifier, e.g. "SDET_Agent".
        action:     Action type, e.g. "write", "read", "delete".
        file_path:  Target file or directory path.

    Returns:
        dict with verdict / law / name / reason keys (same shape as check_action).
    """
    scope = _AGENT_SCOPES.get(agent_name)
    if scope is None:
        # Unknown agent — open-world assumption: ALLOW (backward-compatible)
        return {"verdict": "ALLOW", "law": None, "name": None, "reason": None}

    act = str(action).strip().lower()
    deny_pats: List[str] = scope.get("deny", [])
    write_pats: List[str] = scope.get("write", [])
    read_pats: List[str] = scope.get("read", [])

    # Deny patterns take absolute precedence
    if _matches_any(file_path, deny_pats):
        return {
            "verdict": "DENY",
            "law": "T1-006",
            "name": "agent_file_scope_violation",
            "reason": (
                f"Agent '{agent_name}' is explicitly denied access to '{file_path}'. "
                f"Scope declaration: deny patterns matched."
            ),
        }

    # Write actions require explicit write permission
    if act in _WRITE_ACTIONS:
        if not write_pats or not _matches_any(file_path, write_pats):
            return {
                "verdict": "DENY",
                "law": "T1-006",
                "name": "agent_file_scope_violation",
                "reason": (
                    f"Agent '{agent_name}' does not have write permission for '{file_path}'. "
                    f"Declared write scope: {write_pats or '(none)'}."
                ),
            }

    # Read actions require explicit read permission
    if act in _READ_ACTIONS:
        if not read_pats or not _matches_any(file_path, read_pats):
            return {
                "verdict": "DENY",
                "law": "T1-006",
                "name": "agent_file_scope_violation",
                "reason": (
                    f"Agent '{agent_name}' does not have read permission for '{file_path}'. "
                    f"Declared read scope: {read_pats or '(none)'}."
                ),
            }

    return {"verdict": "ALLOW", "law": None, "name": None, "reason": None}


# ---------------------------------------------------------------------------
# Pre-action check
# ---------------------------------------------------------------------------

_GOVERNANCE_FILES = {
    "constitution.yaml",
    "constitutional_gate.py",
    "observability.py",
}

# Canonical action sets with semantic aliases and common typos included.
# This prevents bypass via alternate phrasing or single-character typos.
_DESTRUCTIVE_ACTIONS = {
    "delete", "delet",          # common typo
    "drop", "truncate", "force_push", "purge",
    "clean", "wipe", "erase",  # semantic aliases for destructive ops
}

_DEPLOY_ACTIONS = {
    "deploy",
    "release", "ship", "go_live",  # semantic deploy aliases
}

_BULK_ACTIONS = {
    "bulk_delete", "bulk_update", "migrate",
    "sync", "replicate", "mirror",  # bulk operation aliases
}

_TIER1_CHECKS = {
    # id → callable(action_type, context) → bool (True = law violated → DENY)
    "T1-001": lambda a, c: (
        a in _DESTRUCTIVE_ACTIONS
        and str(c.get("ci_status", "")).upper() != "PASSED"
    ),
    "T1-002": lambda a, c: (
        a == "delegate"
        and int(c.get("delegation_depth", 0)) >= 3
    ),
    "T1-003": lambda a, c: (
        a in {"log_event", "log_decision", "audit"}
        and bool(c.get("contains_pii"))
    ),
    "T1-004": lambda a, c: (
        a in {"write", "insert", "update", "publish", "push"}
        and not c.get("trace_id")
    ),
    "T1-005": lambda a, c: (
        a in {"write", "delete", "modify"}
        and _is_governance_file(c.get("target_path", ""))
    ),
}

_TIER2_CHECKS = {
    "T2-001": lambda a, c: (
        a in _DEPLOY_ACTIONS
        and str(c.get("environment", "")).lower() == "production"
    ),
    "T2-002": lambda a, c: (
        a in {"modify_infra", "update_iam", "change_dns", "update_firewall"}
    ),
    "T2-003": lambda a, c: (
        a in _BULK_ACTIONS
        and int(c.get("record_count", 0)) > 1000
    ),
}

# Map law id → human-readable name (pulled from constitution once loaded)
def _build_law_names() -> Dict[str, str]:
    names: Dict[str, str] = {}
    for tier_key in ("tier_1", "tier_2"):
        for law in _CONSTITUTION.get(tier_key, []):
            names[law["id"]] = law["name"]
    return names


_LAW_NAMES: Dict[str, str] = _build_law_names()


def _is_governance_file(path: str) -> bool:
    return os.path.basename(str(path)) in _GOVERNANCE_FILES


def check_action(
    action_type: str,
    context: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Evaluate a proposed agent action against the Agent Constitution and file scopes.

    Args:
        action_type: The type of action the agent wants to perform.
                     Examples: "delete", "deploy", "delegate", "write", "log_event".
        context:     Runtime context for the action. Recognized keys:
                     - ci_status (str): "PASSED" | "FAILED" | "PENDING"
                     - delegation_depth (int): current delegation chain length
                     - contains_pii (bool): payload contains PII
                     - trace_id (str): current active trace
                     - target_path (str): file/resource path being written or deleted
                     - environment (str): "production" | "staging" | "dev"
                     - record_count (int): records affected by bulk operation
                     - agent (str): agent name — triggers file scope check when
                                    combined with target_path

    Returns:
        dict with keys:
            verdict (str): "ALLOW" | "REQUIRE_APPROVAL" | "DENY"
            law (str|None): law id that triggered the verdict, e.g. "T1-001"
            name (str|None): human-readable law name
            reason (str|None): explanation string for logs / error messages
    """
    ctx = context or {}
    action = str(action_type).strip().lower()

    # Tier 1 — evaluate in id order; first violation wins
    for law_id, check in _TIER1_CHECKS.items():
        if check(action, ctx):
            law_def = _find_law("tier_1", law_id)
            return {
                "verdict": "DENY",
                "law": law_id,
                "name": _LAW_NAMES.get(law_id, law_def.get("name") if law_def else None),
                "reason": (
                    (law_def or {}).get("description", "").strip()
                    or f"Action '{action}' denied by {law_id}."
                ),
            }

    # Tier 2 — evaluate; first match wins
    for law_id, check in _TIER2_CHECKS.items():
        if check(action, ctx):
            law_def = _find_law("tier_2", law_id)
            return {
                "verdict": "REQUIRE_APPROVAL",
                "law": law_id,
                "name": _LAW_NAMES.get(law_id, law_def.get("name") if law_def else None),
                "reason": (
                    (law_def or {}).get("description", "").strip()
                    or f"Action '{action}' requires human approval per {law_id}."
                ),
            }

    # T1-006 — Agent file scope check (fires when agent + target_path are present)
    agent = ctx.get("agent", "")
    target_path = ctx.get("target_path", "")
    if agent and target_path:
        scope_result = check_file_scope(str(agent), action, str(target_path))
        if scope_result["verdict"] != "ALLOW":
            return scope_result

    return {"verdict": "ALLOW", "law": None, "name": None, "reason": None}


def _find_law(tier_key: str, law_id: str) -> Optional[Dict[str, Any]]:
    for law in _CONSTITUTION.get(tier_key, []):
        if law.get("id") == law_id:
            return law
    return None


class ConstitutionalViolationError(Exception):
    """Raised when an agent action is denied by the Agent Constitution."""

    def __init__(self, reason: str, law: Optional[str] = None):
        self.reason = reason
        self.law = law
        super().__init__(reason)

    def __str__(self) -> str:
        if self.law:
            return f"[{self.law}] {self.reason}"
        return self.reason
