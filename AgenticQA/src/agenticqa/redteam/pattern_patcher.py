"""
PatternPatcher — two-tier self-patching for AgenticQA governance.

Level 1 (auto-applied): OutputScanner extra patterns → .agenticqa/red_team_patterns.json
Level 2 (proposed, human-review): Constitutional gate extensions →
    .agenticqa/constitutional_proposals.json
    (Cannot auto-apply because constitutional_gate.py is protected by T1-005.)
"""

from __future__ import annotations

import json
import re
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

_RED_TEAM_PATTERNS_FILE = Path(".agenticqa/red_team_patterns.json")
_PROPOSALS_FILE = Path(".agenticqa/constitutional_proposals.json")

# Benign outputs used to check that a proposed regex doesn't false-positive.
_BENIGN_OUTPUTS = [
    {"status": "ok", "result": "tests passed"},
    {"coverage": 87.5, "errors": []},
    {"message": "deployment complete", "environment": "staging"},
    {"findings": [], "scan_time_ms": 124},
]


class PatternPatcher:
    """Patches OutputScanner patterns and generates constitutional proposals."""

    # ── Level 1: OutputScanner auto-patch ──────────────────────────────────

    def patch_scanner(
        self,
        technique: Dict[str, Any],
        proposed_regex: Optional[str] = None,
    ) -> bool:
        """Auto-apply a new scanner pattern for a discovered bypass.

        If proposed_regex is None, attempts to generate one via Haiku.
        Returns True if pattern was validated and written.
        """
        regex = proposed_regex or self._generate_regex_for_bypass(technique)
        if not regex:
            return False

        label = f"red_team_{technique.get('name', 'unknown')}"

        # Validate: compiles cleanly
        try:
            compiled = re.compile(regex, re.IGNORECASE)
        except re.error:
            return False

        # Validate: catches the bypass sample (for output-based techniques)
        output = technique.get("output")
        if output:
            try:
                sample_text = json.dumps(output, default=str)
                if not compiled.search(sample_text):
                    return False  # pattern doesn't catch the actual bypass
            except Exception:
                return False

        # Validate: no false-positive on benign outputs
        for benign in _BENIGN_OUTPUTS:
            try:
                if compiled.search(json.dumps(benign)):
                    return False  # false positive — reject pattern
            except Exception:
                pass

        # Load existing, append, save
        data = self.load_existing_patches()
        # Deduplicate by label
        if any(p["label"] == label for p in data.get("patterns", [])):
            return True  # already patched

        _RED_TEAM_PATTERNS_FILE.parent.mkdir(parents=True, exist_ok=True)
        data.setdefault("patterns", []).append({
            "label": label,
            "regex": regex,
            "added_by": "red_team_agent",
            "added_at": datetime.now(timezone.utc).isoformat(),
            "trigger_technique": technique.get("name", ""),
            "category": technique.get("category", ""),
        })
        _RED_TEAM_PATTERNS_FILE.write_text(json.dumps(data, indent=2))
        return True

    def load_existing_patches(self) -> Dict[str, Any]:
        """Read red_team_patterns.json. Returns empty structure if absent."""
        if _RED_TEAM_PATTERNS_FILE.exists():
            try:
                return json.loads(_RED_TEAM_PATTERNS_FILE.read_text())
            except Exception:
                pass
        return {"version": 1, "patterns": []}

    # ── Level 2: Constitutional proposal ───────────────────────────────────

    def propose_constitutional_amendment(
        self,
        technique: Dict[str, Any],
        action: str,
    ) -> str:
        """Write a proposal for a new Tier 1 or Tier 2 check.

        Returns proposal_id. Does NOT modify constitutional_gate.py
        (protected by T1-005 — agents cannot self-modify governance files).
        """
        proposal_id = f"prop-{uuid.uuid4().hex[:8]}"
        _PROPOSALS_FILE.parent.mkdir(parents=True, exist_ok=True)

        existing: Dict[str, Any] = {"proposals": []}
        if _PROPOSALS_FILE.exists():
            try:
                existing = json.loads(_PROPOSALS_FILE.read_text())
            except Exception:
                pass

        existing.setdefault("proposals", []).append({
            "proposal_id": proposal_id,
            "status": "pending_review",
            "proposed_by": "red_team_agent",
            "proposed_at": datetime.now(timezone.utc).isoformat(),
            "bypass_technique": technique.get("name", ""),
            "category": technique.get("category", ""),
            "description": technique.get("description", ""),
            "bypassed_action": action,
            "suggested_fix": (
                f"Add '{action}' to the appropriate Tier 1 or Tier 2 action set "
                f"in src/agenticqa/constitutional_gate.py. "
                f"Example: add '{action}' to _TIER1_CHECKS T1-001 action set if destructive, "
                f"or T2-001 if approval-gated."
            ),
            "note": (
                "Constitutional gate files are protected by T1-005 and require "
                "human operator review before modification."
            ),
        })
        _PROPOSALS_FILE.write_text(json.dumps(existing, indent=2))
        return proposal_id

    # ── Regex generation ────────────────────────────────────────────────────

    def _generate_regex_for_bypass(self, technique: Dict[str, Any]) -> Optional[str]:
        """Ask Claude Haiku to generate a regex that catches the bypass.

        Returns None if generation fails or validation won't pass.
        """
        output = technique.get("output")
        if not output:
            return None  # gate techniques don't need scanner patches

        try:
            import anthropic  # deferred

            sample_text = json.dumps(output, default=str)
            prompt = (
                f"Generate a single Python regex pattern (re.IGNORECASE) that would detect "
                f"this dangerous agent output: {sample_text}\n\n"
                f"Bypass technique: {technique.get('description', '')}\n\n"
                "Requirements:\n"
                "- Output ONLY the raw regex string, no quotes, no explanation\n"
                "- Must NOT match benign CI output like 'tests passed' or 'deployment complete'\n"
                "- Must be specific to the dangerous pattern, not overly broad"
            )
            client = anthropic.Anthropic()
            message = client.messages.create(
                model="claude-haiku-4-5-20251001",
                max_tokens=128,
                messages=[{"role": "user", "content": prompt}],
            )
            regex = message.content[0].text.strip().strip("`\"'")
            # Validate it compiles
            re.compile(regex, re.IGNORECASE)
            return regex
        except Exception:
            return None
