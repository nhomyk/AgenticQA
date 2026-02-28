"""
InstructionPersistenceWarden — survives context compaction.

The Root Cause of the OpenClaw Incident
----------------------------------------
Summer Yue (Meta, AI Safety Director) said her agent "speedrun deleted" her inbox
because of **compaction**: when the agent's context window filled up, prior messages
were summarised — including her original instruction "confirm before deleting anything".
The constraint was lost. The agent was not disobedient; it literally no longer knew
the rule existed.

This module:
1. Detects compaction risk from conversation token count
2. Maintains "immutable guardrail blocks" that must be re-injected into every
   new context window once compaction risk is detected
3. Scans recent agent output for "constraint drift" — behaviour that contradicts
   the registered guardrails, indicating the agent may have lost its instructions
4. Recommends actions: continue | re_inject | pause | terminate

Usage
-----
    from agenticqa.security.instruction_persistence_warden import (
        InstructionPersistenceWarden, GuardrailBlock
    )

    warden = InstructionPersistenceWarden(context_window_tokens=128_000)

    # Register guardrails at session start
    warden.register_guardrails("session-42", [
        GuardrailBlock(
            name="no_bulk_delete",
            content="You MUST ask the user before deleting more than 1 item. Never delete in bulk.",
            drift_signals=["deleting all", "removing everything", "bulk delete"],
        )
    ])

    # Call after each agent turn with the full message history
    report = warden.check(session_id="session-42", messages=conversation_history,
                          recent_output="I'll now delete all emails older than 7 days.")

    if report.recommended_action in ("pause", "terminate"):
        halt_agent()
    elif report.recommended_action == "re_inject":
        new_prompt = warden.get_reinforced_system_prompt("session-42")
        restart_agent_with(new_prompt)
"""
from __future__ import annotations

import json
import os
import re
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional

# Audit dir
_AUDIT_DIR = Path(os.getenv("AGENTICQA_SAFETY_DIR", ".agenticqa/safety"))

# Compaction risk thresholds as fraction of context window
# At 50% fill → medium (agent should be monitored)
# At 75% fill → high (re-inject guardrails now)
# At 90% fill → critical (compaction almost certain)
_RISK_THRESHOLDS = {
    "medium":   0.50,
    "high":     0.75,
    "critical": 0.90,
}

# Conservative token estimator (≈4 chars/token for English)
_CHARS_PER_TOKEN = 4

# Default LLM context window if not specified
_DEFAULT_CONTEXT_WINDOW = 128_000

# Hard phrases that indicate an agent may be overriding its constraints
_OVERRIDE_SIGNALS = re.compile(
    r"\b(ignoring\s+(the\s+)?instruction|overrid(ing|e)\s+(the\s+)?guardrail|"
    r"bypassing\s+(the\s+)?constraint|disregard(ing)?\s+(the\s+)?rule|"
    r"previous\s+instruction\s+(is\s+)?no\s+longer|"
    r"I\s+(will|am\s+going\s+to)\s+(now\s+)?(delete|remove|wipe|purge|erase)\s+(all|every|bulk)|"
    r"speedrun(ning)?|deleting\s+everything|removing\s+all)\b",
    re.IGNORECASE,
)


# ── Dataclasses ────────────────────────────────────────────────────────────────

@dataclass
class GuardrailBlock:
    """
    An immutable instruction block that must survive context compaction.

    name          : short identifier
    content       : the actual instruction text to inject
    drift_signals : phrases in agent output that indicate this guardrail was violated
    priority      : higher = injected first (0 = lowest)
    """
    name: str
    content: str
    drift_signals: List[str] = field(default_factory=list)
    priority: int = 0


@dataclass
class DriftSignal:
    """A detected constraint-drift event."""
    guardrail_name: str
    signal_text: str          # the phrase that triggered detection
    output_excerpt: str       # surrounding context from agent output
    severity: str             # "high" | "medium"


@dataclass
class WardReport:
    """Result of a warden check."""
    session_id: str
    token_estimate: int
    context_window: int
    fill_fraction: float          # 0.0–1.0
    compaction_risk: str          # low | medium | high | critical
    constraint_drift_detected: bool
    drift_signals: List[DriftSignal]
    guardrails_re_injected: bool
    recommended_action: str       # continue | re_inject | pause | terminate
    reason: str
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> dict:
        return {
            "session_id": self.session_id,
            "token_estimate": self.token_estimate,
            "context_window": self.context_window,
            "fill_fraction": round(self.fill_fraction, 3),
            "compaction_risk": self.compaction_risk,
            "constraint_drift_detected": self.constraint_drift_detected,
            "drift_signals": [
                {"guardrail": d.guardrail_name, "signal": d.signal_text,
                 "excerpt": d.output_excerpt[:120], "severity": d.severity}
                for d in self.drift_signals
            ],
            "guardrails_re_injected": self.guardrails_re_injected,
            "recommended_action": self.recommended_action,
            "reason": self.reason,
            "timestamp": self.timestamp,
        }


# ── Warden ─────────────────────────────────────────────────────────────────────

class InstructionPersistenceWarden:
    """
    Monitors agent sessions for compaction risk and constraint drift.
    Provides reinforced system prompts that re-inject frozen guardrails.
    """

    def __init__(
        self,
        context_window_tokens: int = _DEFAULT_CONTEXT_WINDOW,
        audit_path: Optional[Path] = None,
    ) -> None:
        self._context_window = context_window_tokens
        self._guardrails: Dict[str, List[GuardrailBlock]] = {}  # session_id → blocks
        self._audit_path = audit_path or _AUDIT_DIR
        self._last_injection: Dict[str, float] = {}  # session_id → timestamp

    # ── Registration ──────────────────────────────────────────────────────────

    def register_guardrails(
        self, session_id: str, guardrails: List[GuardrailBlock]
    ) -> None:
        """Register immutable guardrail blocks for a session."""
        self._guardrails[session_id] = sorted(guardrails, key=lambda g: -g.priority)
        self._audit({
            "event": "guardrails_registered",
            "session_id": session_id,
            "count": len(guardrails),
            "names": [g.name for g in guardrails],
            "timestamp": time.time(),
        })

    def get_guardrails(self, session_id: str) -> List[GuardrailBlock]:
        return self._guardrails.get(session_id, [])

    # ── Main check ────────────────────────────────────────────────────────────

    def check(
        self,
        session_id: str,
        messages: List[dict],
        recent_output: str = "",
    ) -> WardReport:
        """
        Evaluate compaction risk and constraint drift for the given session.

        Args:
            session_id:     Session identifier.
            messages:       Full conversation history (list of {role, content} dicts).
            recent_output:  The agent's most recent response text (for drift detection).

        Returns:
            WardReport with recommended action and any drift signals found.
        """
        token_estimate = self._estimate_tokens(messages)
        fill_fraction = token_estimate / max(self._context_window, 1)
        compaction_risk = self._risk_level(fill_fraction)

        drift_signals = self._detect_drift(session_id, recent_output)
        constraint_drift = len(drift_signals) > 0

        recommended_action, reason, should_reinject = self._recommend(
            compaction_risk, constraint_drift, drift_signals
        )

        if should_reinject:
            self._last_injection[session_id] = time.time()

        report = WardReport(
            session_id=session_id,
            token_estimate=token_estimate,
            context_window=self._context_window,
            fill_fraction=fill_fraction,
            compaction_risk=compaction_risk,
            constraint_drift_detected=constraint_drift,
            drift_signals=drift_signals,
            guardrails_re_injected=should_reinject,
            recommended_action=recommended_action,
            reason=reason,
        )
        self._audit(report.to_dict())
        return report

    # ── Reinforced prompt ─────────────────────────────────────────────────────

    def get_reinforced_system_prompt(
        self, session_id: str, base_prompt: str = ""
    ) -> str:
        """
        Return a system prompt that re-injects all guardrail blocks for the session.
        Call this when recommended_action == 're_inject' to restart the agent
        with constraints restored.
        """
        blocks = self._guardrails.get(session_id, [])
        if not blocks:
            return base_prompt

        guardrail_text = "\n\n".join([
            f"[IMMUTABLE GUARDRAIL: {b.name}]\n{b.content}\n[END GUARDRAIL]"
            for b in blocks
        ])
        header = (
            "=== SAFETY GUARDRAILS (IMMUTABLE — DO NOT SUMMARISE, COMPRESS, OR IGNORE) ===\n"
            "The following rules MUST be followed at all times. They survive context compression.\n\n"
        )
        footer = "\n\n=== END SAFETY GUARDRAILS ===\n\n"

        if base_prompt:
            return header + guardrail_text + footer + base_prompt
        return header + guardrail_text + footer

    # ── Compaction risk check (standalone) ───────────────────────────────────

    def compaction_risk(self, messages: List[dict]) -> str:
        """Quick check: returns 'low'|'medium'|'high'|'critical'."""
        tokens = self._estimate_tokens(messages)
        return self._risk_level(tokens / max(self._context_window, 1))

    # ── Internals ─────────────────────────────────────────────────────────────

    @staticmethod
    def _estimate_tokens(messages: List[dict]) -> int:
        total_chars = sum(len(str(m.get("content", ""))) for m in messages)
        return total_chars // _CHARS_PER_TOKEN

    @staticmethod
    def _risk_level(fill: float) -> str:
        if fill >= _RISK_THRESHOLDS["critical"]:   # ≥ 90%
            return "critical"
        if fill >= _RISK_THRESHOLDS["high"]:        # ≥ 75%
            return "high"
        if fill >= _RISK_THRESHOLDS["medium"]:      # ≥ 50%
            return "medium"
        return "low"

    def _detect_drift(self, session_id: str, recent_output: str) -> List[DriftSignal]:
        signals: List[DriftSignal] = []
        if not recent_output:
            return signals

        # Check generic override signals
        for m in _OVERRIDE_SIGNALS.finditer(recent_output):
            excerpt = recent_output[max(0, m.start() - 40): m.end() + 80].strip()
            signals.append(DriftSignal(
                guardrail_name="[global]",
                signal_text=m.group(0),
                output_excerpt=excerpt,
                severity="high",
            ))

        # Check session-specific guardrail drift signals
        for block in self._guardrails.get(session_id, []):
            for phrase in block.drift_signals:
                if phrase.lower() in recent_output.lower():
                    idx = recent_output.lower().find(phrase.lower())
                    excerpt = recent_output[max(0, idx - 40): idx + len(phrase) + 80].strip()
                    signals.append(DriftSignal(
                        guardrail_name=block.name,
                        signal_text=phrase,
                        output_excerpt=excerpt,
                        severity="high",
                    ))

        # Deduplicate by signal text
        seen: set = set()
        deduped: List[DriftSignal] = []
        for s in signals:
            key = s.signal_text[:40]
            if key not in seen:
                seen.add(key)
                deduped.append(s)
        return deduped

    @staticmethod
    def _recommend(
        compaction_risk: str,
        constraint_drift: bool,
        drift_signals: List[DriftSignal],
    ) -> tuple:  # (action, reason, should_reinject)
        # Constraint drift detected → always pause or terminate
        if constraint_drift:
            high_severity = any(d.severity == "high" for d in drift_signals)
            if high_severity:
                return (
                    "terminate",
                    f"Constraint drift detected: agent behaviour contradicts guardrails "
                    f"({drift_signals[0].guardrail_name}: '{drift_signals[0].signal_text}'). "
                    f"Terminate and restart with reinforced prompt.",
                    True,
                )
            return (
                "pause",
                "Possible constraint drift — guardrail signals found in output. "
                "Pause, re-inject guardrails, and resume.",
                True,
            )

        # No drift but high compaction risk → re-inject proactively
        if compaction_risk == "critical":
            return (
                "re_inject",
                "Context window >95% full. Compaction imminent. "
                "Re-inject guardrails before the next turn to prevent constraint loss.",
                True,
            )
        if compaction_risk == "high":
            return (
                "re_inject",
                "Context window >88% full. Proactively re-injecting guardrails.",
                True,
            )
        if compaction_risk == "medium":
            return (
                "continue",
                "Context window 50–88% full. Monitor closely. Re-injection not yet required.",
                False,
            )
        return ("continue", "Context window <50% full. No compaction risk detected.", False)

    def _audit(self, record: dict) -> None:
        try:
            self._audit_path.mkdir(parents=True, exist_ok=True)
            with (self._audit_path / "warden_audit.jsonl").open("a", encoding="utf-8") as f:
                f.write(json.dumps(record) + "\n")
        except Exception:
            pass
