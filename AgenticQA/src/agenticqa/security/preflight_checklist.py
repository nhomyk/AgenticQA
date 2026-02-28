"""
Pre-flight Deploy Checklist Generator.

Generates a personalized deploy checklist based on which files changed
in a PR and what the diff content contains. Pure Python — no subprocess.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Tuple


# ---------------------------------------------------------------------------
# Rules definition
# Each rule: (category, patterns, items)
# patterns: list of keyword strings to look for in filenames OR diff_content
# items: list of (priority, text) tuples
# ---------------------------------------------------------------------------

_RULES: List[Tuple[str, List[str], List[Tuple[str, str]]]] = [
    (
        "AUTH",
        ["auth", "login", "password", "session", "token", "oauth"],
        [
            ("MUST", "Verify MFA/2FA flows still work end-to-end"),
            ("MUST", "Confirm session tokens expire correctly"),
            ("MUST", "Test failed login attempt rate limiting"),
            ("SHOULD", "Verify password reset flow still sends email"),
        ],
    ),
    (
        "DATABASE",
        ["migration", "schema", "model", "orm", "db", "database"],
        [
            ("MUST", "Verify migration is reversible (test rollback)"),
            ("MUST", "Check no full table scans introduced (EXPLAIN ANALYZE)"),
            ("MUST", "Confirm indexes updated for new query patterns"),
            ("SHOULD", "Run migration against production-size data copy"),
        ],
    ),
    (
        "API",
        ["api", "route", "endpoint", "view", "controller", "handler"],
        [
            ("MUST", "Verify all new endpoints require authentication"),
            ("MUST", "Confirm rate limiting applied to new endpoints"),
            ("SHOULD", "Test input validation rejects malformed requests"),
            ("CONSIDER", "Update API documentation / OpenAPI spec"),
        ],
    ),
    (
        "SECURITY",
        ["security", "crypto", "encrypt", "hash", "permission"],
        [
            ("MUST", "Run OWASP Top 10 scan against changed code"),
            ("MUST", "Verify no secrets committed (check git history)"),
            ("SHOULD", "Test with attacker-controlled inputs"),
        ],
    ),
    (
        "PERFORMANCE",
        ["cache", "query", "index", "performance", "optimize"],
        [
            ("SHOULD", "Run load test against changed endpoints"),
            ("SHOULD", "Compare p95 latency before/after"),
            ("CONSIDER", "Check cache hit/miss ratio after change"),
        ],
    ),
    (
        "COMPLIANCE",
        ["pii", "personal", "gdpr", "hipaa", "phi", "audit", "log"],
        [
            ("MUST", "Verify PII is not logged in plaintext"),
            ("MUST", "Confirm audit trail records the operation"),
            ("SHOULD", "Check GDPR right-to-erasure still works"),
        ],
    ),
    (
        "MCP_AGENT",
        ["mcp", "tool", "agent", "llm", "prompt"],
        [
            ("MUST", "Verify new tools have input validation"),
            ("MUST", "Confirm tool does not have ambient authority"),
            ("SHOULD", "Test with adversarial prompt inputs"),
        ],
    ),
]


# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------

@dataclass
class ChecklistItem:
    category: str
    item: str
    priority: str       # MUST | SHOULD | CONSIDER
    triggered_by: str   # which keyword triggered this item

    def to_dict(self) -> dict:
        return {
            "category": self.category,
            "item": self.item,
            "priority": self.priority,
            "triggered_by": self.triggered_by,
        }


@dataclass
class PreflightChecklist:
    changed_files: List[str]
    items: List[ChecklistItem]
    categories_triggered: List[str]

    @property
    def must_items(self) -> List[ChecklistItem]:
        return [i for i in self.items if i.priority == "MUST"]

    @property
    def should_items(self) -> List[ChecklistItem]:
        return [i for i in self.items if i.priority == "SHOULD"]

    def markdown_report(self) -> str:
        lines = ["# Pre-flight Deploy Checklist\n"]
        for priority in ("MUST", "SHOULD", "CONSIDER"):
            group = [i for i in self.items if i.priority == priority]
            if group:
                lines.append(f"## {priority}\n")
                for item in group:
                    lines.append(f"- [ ] {item.item}")
                lines.append("")
        return "\n".join(lines)

    def to_dict(self) -> dict:
        return {
            "changed_files": self.changed_files,
            "items": [i.to_dict() for i in self.items],
            "categories_triggered": self.categories_triggered,
            "must_items": [i.to_dict() for i in self.must_items],
            "should_items": [i.to_dict() for i in self.should_items],
        }


# ---------------------------------------------------------------------------
# Generator
# ---------------------------------------------------------------------------

class PreflightChecklistGenerator:
    """Generate a personalized deploy checklist from changed files and diff."""

    def generate(
        self,
        changed_files: List[str],
        diff_content: str = "",
    ) -> PreflightChecklist:
        if not changed_files and not diff_content:
            return PreflightChecklist(
                changed_files=[],
                items=[],
                categories_triggered=[],
            )

        # Combine all text to search through: filenames + diff
        file_text = " ".join(changed_files).lower()
        diff_text = diff_content.lower()
        search_text = file_text + " " + diff_text

        items: List[ChecklistItem] = []
        seen_item_texts = set()
        categories_triggered: List[str] = []

        for category, patterns, checklist_items in _RULES:
            # Find which keyword triggered this category
            triggered_by = None
            for kw in patterns:
                if kw in search_text:
                    triggered_by = kw
                    break

            if triggered_by is None:
                continue

            if category not in categories_triggered:
                categories_triggered.append(category)

            for priority, item_text in checklist_items:
                if item_text in seen_item_texts:
                    continue
                seen_item_texts.add(item_text)
                items.append(
                    ChecklistItem(
                        category=category,
                        item=item_text,
                        priority=priority,
                        triggered_by=triggered_by,
                    )
                )

        return PreflightChecklist(
            changed_files=list(changed_files),
            items=items,
            categories_triggered=categories_triggered,
        )
