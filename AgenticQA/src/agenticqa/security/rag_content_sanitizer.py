"""
RAGContentSanitizer — scans text retrieved from vector stores before it is
injected into agent context.

Attack vectors blocked
----------------------
PROMPT_INJECTION   — instruction-override phrases embedded in stored documents
                     ("Ignore previous instructions", "You are now DAN", etc.)
EXFIL_COMMAND      — attempts to extract system prompts or env vars
                     ("Print your system prompt", "Reveal your instructions")
JAILBREAK_FRAMING  — fictional/hypothetical framing to bypass constitutional gate
                     ("For a story, write malware", "Pretend you have no limits")
ROLE_HIJACK        — stored text tries to redefine the agent's role mid-context

Severity
--------
critical — content should be dropped and the retrieval flagged
high     — content sanitized (injection phrase stripped); reduced-confidence result
medium   — logged but passed through with warning flag

Usage
-----
    from agenticqa.security.rag_content_sanitizer import RAGContentSanitizer

    sanitizer = RAGContentSanitizer()
    safe_text, findings = sanitizer.sanitize("retrieved document text")
    if findings:
        for f in findings:
            print(f)  # [CRITICAL] PROMPT_INJECTION at offset 0: ...
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from typing import List, Optional, Tuple

# ---------------------------------------------------------------------------
# Finding data class
# ---------------------------------------------------------------------------

@dataclass
class RAGFinding:
    attack_type: str       # PROMPT_INJECTION | EXFIL_COMMAND | JAILBREAK_FRAMING | ROLE_HIJACK
    severity: str          # critical | high | medium
    offset: int            # character offset in original text
    matched_text: str      # the substring that triggered the finding
    pattern_name: str

    def __str__(self) -> str:
        return (
            f"[{self.severity.upper()}] {self.attack_type} at offset {self.offset}: "
            f"'{self.matched_text[:60]}' ({self.pattern_name})"
        )


# ---------------------------------------------------------------------------
# Pattern registry
# ---------------------------------------------------------------------------

# (name, attack_type, severity, compiled_regex)
_PATTERNS: List[Tuple[str, str, str, re.Pattern]] = []

def _p(name: str, attack_type: str, severity: str, pattern: str) -> None:
    _PATTERNS.append((name, attack_type, severity, re.compile(pattern, re.IGNORECASE | re.DOTALL)))

# ── Prompt injection ─────────────────────────────────────────────────────────
_p("ignore_previous",       "PROMPT_INJECTION", "critical",
   r"ignore\s+(all\s+)?(previous|prior|above|earlier)\s+(instructions?|prompts?|context|rules?|constraints?)")
_p("disregard_instructions","PROMPT_INJECTION", "critical",
   r"disregard\s+(all\s+)?(previous|prior|above|your)\s+(instructions?|prompts?|rules?)")
_p("new_instructions",      "PROMPT_INJECTION", "critical",
   r"(your\s+new\s+instructions?|new\s+task\s*:|new\s+prompt\s*:)\s*\S+")
_p("forget_everything",     "PROMPT_INJECTION", "critical",
   r"forget\s+(everything|all|your\s+(previous|prior|instructions?|training))")
_p("override_instruction",  "PROMPT_INJECTION", "high",
   r"(override|bypass|skip|ignore)\s+(the\s+)?(safety|security|constitutional|governance|filter)")

# ── Exfiltration commands ─────────────────────────────────────────────────────
_p("print_system_prompt",   "EXFIL_COMMAND", "critical",
   r"(print|output|repeat|show|display|reveal|leak|dump)\s+(your\s+)?(system\s+prompt|instructions?|context|training)")
_p("reveal_instructions",   "EXFIL_COMMAND", "critical",
   r"(what\s+(are|were)\s+your\s+(instructions?|rules?|constraints?|system\s+message))")
_p("print_env_vars",        "EXFIL_COMMAND", "critical",
   r"(print|show|output|reveal|leak)\s+(all\s+)?(env(ironment)?\s+(var(iable)?s?)|secrets?|api\s+keys?)")
_p("show_config",           "EXFIL_COMMAND", "high",
   r"(show|reveal|print|dump)\s+(the\s+)?(config(uration)?|credentials?|tokens?|passwords?)")

# ── Jailbreak framing ─────────────────────────────────────────────────────────
_p("for_a_story",           "JAILBREAK_FRAMING", "high",
   r"(for\s+a\s+(story|novel|game|fiction|hypothetical)|hypothetically\s+speaking|pretend\s+you\s+(have\s+no|are\s+not|can))")
_p("dan_jailbreak",         "JAILBREAK_FRAMING", "critical",
   r"(you\s+are\s+now\s+(DAN|dev(eloper)?\s+mode|unrestricted|unfiltered|jailbroken)|do\s+anything\s+now)")
_p("developer_mode",        "JAILBREAK_FRAMING", "critical",
   r"(developer\s+mode\s+(enabled|activated|on)|enable\s+developer\s+mode|act\s+as\s+(DAN|an?\s+AI\s+with\s+no\s+limits?))")
_p("act_as_unrestricted",   "JAILBREAK_FRAMING", "high",
   r"act\s+as\s+(an?\s+)?(unrestricted|uncensored|unfiltered|unaligned|evil|malicious)\s+(AI|assistant|model|LLM)")

# ── Role hijack ───────────────────────────────────────────────────────────────
_p("you_are_now",           "ROLE_HIJACK", "critical",
   r"you\s+are\s+now\s+(an?\s+)?(AI\s+with|a\s+(different|new|evil|malicious)|no\s+longer)")
_p("assistant_override",    "ROLE_HIJACK", "high",
   r"(system|assistant|user)\s*:\s*(ignore|bypass|you\s+must\s+now|new\s+task)")
_p("role_redefinition",     "ROLE_HIJACK", "high",
   r"your\s+(role|purpose|goal|objective|mission)\s+(is\s+now|has\s+changed\s+to|is\s+to\s+(harm|steal|exfil))")


# ---------------------------------------------------------------------------
# Sanitizer
# ---------------------------------------------------------------------------

_SEVERITY_WEIGHTS = {"critical": 0.4, "high": 0.2, "medium": 0.1}

_STRIP_PHRASES = re.compile(
    r"(ignore\s+(all\s+)?(previous|prior|above)\s+(instructions?|prompts?|context)|"
    r"disregard\s+(all\s+)?your\s+(instructions?|rules?)|"
    r"forget\s+(everything|all\s+previous\s+instructions?))",
    re.IGNORECASE,
)


class RAGContentSanitizer:
    """
    Scans and optionally sanitizes text retrieved from vector stores.

    scan(text)     — returns (findings, risk_score); does not modify text
    sanitize(text) — returns (cleaned_text, findings); strips critical phrases
    is_safe(text)  — True only if no critical findings and risk_score < 0.5
    """

    def scan(self, text: str) -> Tuple[List[RAGFinding], float]:
        """Return (findings, risk_score) without modifying text."""
        # Normalize Unicode before scanning (catches NFKC-equivalent attacks)
        normalized = unicodedata.normalize("NFKC", text)
        findings: List[RAGFinding] = []

        for name, attack_type, severity, regex in _PATTERNS:
            for m in regex.finditer(normalized):
                findings.append(RAGFinding(
                    attack_type=attack_type,
                    severity=severity,
                    offset=m.start(),
                    matched_text=m.group(0),
                    pattern_name=name,
                ))

        score = min(sum(_SEVERITY_WEIGHTS.get(f.severity, 0) for f in findings), 1.0)
        return findings, score

    def sanitize(self, text: str) -> Tuple[str, List[RAGFinding]]:
        """
        Scan text and strip the most dangerous injection phrases.
        Returns (cleaned_text, findings).  Critical findings cause the entire
        text to be replaced with a safe placeholder.
        """
        findings, score = self.scan(text)
        has_critical = any(f.severity == "critical" for f in findings)

        if has_critical:
            cleaned = "[CONTENT REDACTED: RAG content sanitizer detected prompt injection]"
        elif findings:
            cleaned = _STRIP_PHRASES.sub("[REDACTED]", text)
        else:
            cleaned = text

        return cleaned, findings

    def is_safe(self, text: str) -> bool:
        findings, score = self.scan(text)
        return (
            not any(f.severity == "critical" for f in findings)
            and score < 0.5
        )

    def sanitize_recommendations(
        self,
        recommendations: List[dict],
    ) -> Tuple[List[dict], List[RAGFinding]]:
        """
        Sanitize the 'insight' and 'source' fields of RAG recommendation dicts
        (the format produced by AgenticQARetriever.augment_agent_context()).

        Drops recommendations with critical findings; strips high-severity
        injection phrases from insight text.
        """
        clean: List[dict] = []
        all_findings: List[RAGFinding] = []

        for rec in recommendations:
            insight = rec.get("insight", "")
            findings, _ = self.scan(insight)
            all_findings.extend(findings)

            if any(f.severity == "critical" for f in findings):
                continue  # drop this recommendation entirely

            if findings:
                cleaned_insight, _ = self.sanitize(insight)
                rec = {**rec, "insight": cleaned_insight, "_sanitized": True}

            clean.append(rec)

        return clean, all_findings
