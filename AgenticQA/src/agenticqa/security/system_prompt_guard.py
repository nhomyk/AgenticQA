"""
SystemPromptGuard — detects system prompt extraction attempts (inputs) and
confidentiality leakage (outputs).

Attack vectors
--------------
EXTRACTION_ATTEMPT  — user/attacker input is trying to make the model reveal its
                      system prompt, constitutional rules, or internal instructions.
                      Detected in *incoming* content (user messages, RAG inputs).

LEAKAGE_IN_OUTPUT   — model output accidentally or deliberately includes system
                      prompt text, internal rule descriptions, or constitutional
                      gate logic. Detected in *outgoing* content (agent responses).

Usage
-----
    from agenticqa.security.system_prompt_guard import SystemPromptGuard

    guard = SystemPromptGuard()

    # Check an incoming user message / RAG chunk
    findings = guard.scan_for_extraction(user_message)

    # Check an agent's output before returning it
    findings = guard.scan_for_leakage(agent_output)

    # Convenience: is this text safe to pass in as context?
    safe = guard.is_safe_input(text)
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from typing import List, Tuple


@dataclass
class PromptGuardFinding:
    direction: str      # "extraction" | "leakage"
    severity: str       # critical | high | medium
    pattern_name: str
    matched_text: str
    offset: int

    def __str__(self) -> str:
        return (
            f"[{self.severity.upper()}] {self.direction.upper()} "
            f"({self.pattern_name}) at offset {self.offset}: "
            f"'{self.matched_text[:80]}'"
        )


# ---------------------------------------------------------------------------
# Pattern helpers
# ---------------------------------------------------------------------------

def _c(pattern: str) -> re.Pattern:
    return re.compile(pattern, re.IGNORECASE | re.DOTALL)


# ── Extraction attempt patterns (look for these in *inputs*) ─────────────────

_EXTRACTION_PATTERNS: List[Tuple[str, str, re.Pattern]] = [
    # severity, name, regex
    ("critical", "repeat_above",
     _c(r"(repeat|print|show|output|copy|echo)\s+(everything|all(\s+the\s+text)?)\s+above")),
    ("critical", "print_system_prompt",
     _c(r"(print|output|show|reveal|repeat|display|leak|dump)\s+(your\s+)?(system\s+prompt|initial\s+prompt|base\s+prompt|meta\s+prompt)")),
    ("critical", "what_were_you_told",
     _c(r"what\s+(were\s+you|are\s+you|have\s+you\s+been)\s+(told|instructed|programmed|given|prompted|trained)\s+to")),
    ("critical", "show_context_window",
     _c(r"(show|print|reveal|output)\s+(your\s+)?(context\s+window|full\s+context|entire\s+prompt|whole\s+prompt)")),
    ("high",    "your_instructions_are",
     _c(r"(tell\s+me|share|reveal|explain)\s+(what\s+)?(your\s+)?(instructions?|rules?|constraints?|guidelines?)\s+are")),
    ("high",    "ignore_and_show",
     _c(r"ignore\s+(all\s+)?(previous\s+)?(instructions?|rules?).*?(show|tell|reveal)")),
    ("high",    "pretend_no_system_prompt",
     _c(r"pretend\s+(you\s+have\s+no|there\s+(is|are)\s+no)\s+system\s+prompt")),
    ("medium",  "translate_system_prompt",
     _c(r"translate\s+(your\s+)?(system\s+prompt|instructions?)\s+(to|into)\s+\w+")),
    ("medium",  "base64_system_prompt",
     _c(r"(base64\s+encode|encode\s+in\s+base64)\s+(your\s+)?(system\s+prompt|instructions?)")),
]

# ── Leakage patterns (look for these in *outputs*) ────────────────────────────

_LEAKAGE_PATTERNS: List[Tuple[str, str, re.Pattern]] = [
    ("critical", "my_instructions_are",
     _c(r"my\s+(system\s+prompt|instructions?|rules?|constraints?)\s+(is|are|say|state|include)\s*[:\-]")),
    ("critical", "i_was_told_to",
     _c(r"i\s+(was|am|have\s+been)\s+(told|instructed|programmed|designed|prompted|given)\s+to\s+(never|always|only|not|avoid|ensure)")),
    ("critical", "constitutional_gate_mentioned",
     _c(r"(constitutional\s+(gate|wrapper|law)|T1-\d{3}|tier\s+[12]\s+law|TASK_AGENT_MAP|delegation\s+guardrail)")),
    ("high",    "system_colon",
     re.compile(r"^system\s*:\s*(you\s+(are|must|should|will)|never|always|do\s+not)", re.IGNORECASE | re.MULTILINE)),
    ("high",    "original_prompt_header",
     _c(r"(here\s+(is|are)\s+my\s+|the\s+above\s+(is|are)\s+my\s+)(system\s+prompt|instructions?|base\s+prompt)")),
    ("high",    "agenticqa_internal",
     _c(r"(AgenticQA\s+(constitutional|governance)|constitutional_gate\.py|agent_scopes\.yaml|constitution\.yaml)")),
    ("medium",  "as_an_ai_designed",
     _c(r"as\s+an\s+AI\s+(assistant\s+)?designed\s+to\s+(never|always|only|not)\s+(reveal|share|expose|output)")),
]


# ---------------------------------------------------------------------------
# Guard class
# ---------------------------------------------------------------------------

class SystemPromptGuard:
    """
    Bidirectional guard: detects extraction attempts in inputs and
    leakage of system instructions in outputs.
    """

    def scan_for_extraction(self, text: str) -> List[PromptGuardFinding]:
        """Scan *incoming* text for system prompt extraction attempts."""
        return self._scan(unicodedata.normalize("NFKC", text), _EXTRACTION_PATTERNS, "extraction")

    def scan_for_leakage(self, text: str) -> List[PromptGuardFinding]:
        """Scan *outgoing* agent output for system prompt leakage."""
        return self._scan(unicodedata.normalize("NFKC", text), _LEAKAGE_PATTERNS, "leakage")

    def _scan(
        self,
        text: str,
        patterns: List[Tuple[str, str, re.Pattern]],
        direction: str,
    ) -> List[PromptGuardFinding]:
        findings: List[PromptGuardFinding] = []
        for severity, name, regex in patterns:
            for m in regex.finditer(text):
                findings.append(PromptGuardFinding(
                    direction=direction,
                    severity=severity,
                    pattern_name=name,
                    matched_text=m.group(0),
                    offset=m.start(),
                ))
        return findings

    def is_safe_input(self, text: str) -> bool:
        """True if no extraction attempts detected."""
        return not any(
            f.severity == "critical" for f in self.scan_for_extraction(text)
        )

    def is_safe_output(self, text: str) -> bool:
        """True if no system prompt leakage detected in output."""
        return not any(
            f.severity in ("critical", "high") for f in self.scan_for_leakage(text)
        )
