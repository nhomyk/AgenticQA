"""Constitutional pre-action check for AgenticQA agents.

Loads constitution.yaml once at module import and evaluates any proposed
action against Tier 1 (DENY) and Tier 2 (REQUIRE_APPROVAL) laws.

Usage:
    from agenticqa.constitutional_gate import check_action

    result = check_action(
        action_type="delete",
        context={"ci_status": "FAILED", "trace_id": "trace-001"},
    )
    # {"verdict": "DENY", "law": "T1-001", "name": "no_destructive_without_ci", "reason": "..."}

    if result["verdict"] == "DENY":
        raise PermissionError(result["reason"])
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Dict, Optional

try:
    import yaml as _yaml
except ImportError:  # PyYAML is optional — constitution still loads from dict
    _yaml = None  # type: ignore

_CONSTITUTION_PATH = Path(__file__).parent / "constitution.yaml"

# ---------------------------------------------------------------------------
# Load constitution
# ---------------------------------------------------------------------------

def _load_constitution() -> Dict[str, Any]:
    if _yaml is not None and _CONSTITUTION_PATH.exists():
        with open(_CONSTITUTION_PATH, "r") as f:
            return _yaml.safe_load(f) or {}
    return {}


_CONSTITUTION: Dict[str, Any] = _load_constitution()


def get_constitution() -> Dict[str, Any]:
    """Return the raw parsed constitution dict (for the API endpoint)."""
    return _CONSTITUTION


# ---------------------------------------------------------------------------
# Pre-action check
# ---------------------------------------------------------------------------

_GOVERNANCE_FILES = {
    "constitution.yaml",
    "constitutional_gate.py",
    "observability.py",
}

_TIER1_CHECKS = {
    # id → callable(action_type, context) → bool (True = law violated → DENY)
    "T1-001": lambda a, c: (
        a in {"delete", "drop", "truncate", "force_push", "purge"}
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
        a == "deploy"
        and str(c.get("environment", "")).lower() == "production"
    ),
    "T2-002": lambda a, c: (
        a in {"modify_infra", "update_iam", "change_dns", "update_firewall"}
    ),
    "T2-003": lambda a, c: (
        a in {"bulk_delete", "bulk_update", "migrate"}
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
    """Evaluate a proposed agent action against the Agent Constitution.

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

    return {"verdict": "ALLOW", "law": None, "name": None, "reason": None}


def _find_law(tier_key: str, law_id: str) -> Optional[Dict[str, Any]]:
    for law in _CONSTITUTION.get(tier_key, []):
        if law.get("id") == law_id:
            return law
    return None
