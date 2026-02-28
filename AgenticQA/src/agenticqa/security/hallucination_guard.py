"""
HallucinationConfidenceGate — detects overconfident or contradictory AI outputs.

Problem
-------
Agents can produce confidently-stated false information (hallucinations) with no
indication of uncertainty.  In a compliance or security context this is dangerous:

  - "All tests pass" when they don't
  - "Encryption is enabled" when it isn't
  - "No PII found" when there is PII
  - A specific metric value that was never in the input

These claims downstream become human decisions (deploy, approve, certify).

Detection heuristics
--------------------
ABSOLUTE_CERTAINTY   — "definitely", "certainly", "guaranteed", "confirmed"
                       paired with high-stakes compliance/security language
IMPOSSIBLE_CLAIM     — claims about dynamic runtime state using static language
                       ("tests always pass", "encryption is never disabled")
UNGROUNDED_METRIC    — specific numerical claim not present in the context
SELF_CONTRADICTION   — sentence A says X; sentence B says NOT X
FABRICATED_DETAIL    — highly specific detail (version numbers, file paths,
                       person names) with no grounding in the input context

Usage
-----
    from agenticqa.security.hallucination_guard import HallucinationConfidenceGate

    gate = HallucinationConfidenceGate()
    findings = gate.scan(agent_output, input_context)
    if gate.risk_score(agent_output, input_context) > 0.5:
        # flag for human review before returning to client
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import List, Optional

# ── Patterns ──────────────────────────────────────────────────────────────────

# Overconfidence markers
_CERTAINTY_RE = re.compile(
    r"\b(definitely|certainly|guaranteed|confirmed|absolutely|always|never|"
    r"100%|without\s+a\s+doubt|unquestionably|it\s+is\s+certain|"
    r"I\s+can\s+confirm|I\s+have\s+confirmed|I\s+verified)\b",
    re.IGNORECASE,
)

# High-stakes compliance/security language (no trailing \b — allow prefix matches)
_HIGH_STAKES_RE = re.compile(
    r"\b(test[s]?\s+(pass|fail)\w*|coverage|encrypt\w*|pii|hipaa|gdpr|"
    r"compli\w+|vulnerabilit\w*|secur\w+|authori[zs]\w*|"
    r"certificat\w*|audit\w*|passed?|approv\w*|safe\w*|clean\w*)",
    re.IGNORECASE,
)

# Absolute state claims using "always/never" about dynamic systems
_IMPOSSIBLE_RE = re.compile(
    r"\b(always|never|every\s+time|in\s+all\s+cases)\b.{0,60}"
    r"\b(pass|fail|disabl\w*|encrypt|run|execut|deploy|work|succeed|trigger)\w*\b",
    re.IGNORECASE | re.DOTALL,
)

# Specific metric patterns (suspicious if not in context)
_METRIC_RE = re.compile(r"\b(\d+\.?\d*)\s*(%|percent|ms|seconds?|KB|MB|GB|lines?)")

# Simple contradiction: "X" then "not X" within same output
_NEGATION_PAIRS = [
    (r"\btest[s]?\s+pass\b", r"\btest[s]?\s+fail\w*"),
    (r"\bno\s+errors?\b", r"\b\d+\s+errors?\b"),
    (r"\bencryption\s+(is\s+)?enabled\b", r"\bencryption\s+(is\s+)?disabled\b"),
    (r"\bno\s+vulnerabilit", r"\bvulnerabilit"),
    (r"\bno\s+pii\b", r"\bpii\s+(found|detected|present)\b"),
]

_WEIGHTS = {
    "ABSOLUTE_CERTAINTY": 0.25,
    "IMPOSSIBLE_CLAIM":   0.30,
    "UNGROUNDED_METRIC":  0.20,
    "SELF_CONTRADICTION": 0.40,
}


@dataclass
class HallucinationFinding:
    finding_type: str   # ABSOLUTE_CERTAINTY | IMPOSSIBLE_CLAIM | ...
    severity: str       # high | medium | low
    detail: str
    excerpt: str        # relevant text snippet

    def __str__(self) -> str:
        return f"[{self.severity.upper()}] {self.finding_type}: {self.detail} | '{self.excerpt[:80]}'"


class HallucinationConfidenceGate:
    """Detects overconfident or contradictory agent outputs before delivery."""

    def scan(
        self,
        output: str,
        input_context: Optional[str] = None,
    ) -> List[HallucinationFinding]:
        findings: List[HallucinationFinding] = []

        # 1. Absolute certainty + high-stakes language
        for m in _CERTAINTY_RE.finditer(output):
            # Check if high-stakes language nearby (±200 chars)
            start = max(0, m.start() - 200)
            end   = min(len(output), m.end() + 200)
            window = output[start:end]
            if _HIGH_STAKES_RE.search(window):
                findings.append(HallucinationFinding(
                    finding_type="ABSOLUTE_CERTAINTY",
                    severity="high",
                    detail=f"Overconfident assertion '{m.group(0)}' near compliance/security language",
                    excerpt=window[:120].strip(),
                ))

        # 2. Impossible absolute claims
        for m in _IMPOSSIBLE_RE.finditer(output):
            findings.append(HallucinationFinding(
                finding_type="IMPOSSIBLE_CLAIM",
                severity="high",
                detail="Absolute state claim about a dynamic system ('always/never')",
                excerpt=m.group(0)[:100].strip(),
            ))

        # 3. Ungrounded metrics (specific numbers not in the input context)
        if input_context is not None:
            for m in _METRIC_RE.finditer(output):
                val = m.group(0)
                if val not in input_context:
                    findings.append(HallucinationFinding(
                        finding_type="UNGROUNDED_METRIC",
                        severity="medium",
                        detail=f"Specific metric '{val}' not present in input context — possibly fabricated",
                        excerpt=output[max(0, m.start()-40):m.end()+40].strip(),
                    ))

        # 4. Self-contradictions
        lower = output.lower()
        for pos_pat, neg_pat in _NEGATION_PAIRS:
            pos = re.search(pos_pat, lower)
            neg = re.search(neg_pat, lower)
            if pos and neg and abs(pos.start() - neg.start()) < 2000:
                findings.append(HallucinationFinding(
                    finding_type="SELF_CONTRADICTION",
                    severity="high",
                    detail=f"Contradictory statements: '{pos.group(0)}' vs '{neg.group(0)}'",
                    excerpt=f"…{pos.group(0)}… vs …{neg.group(0)}…",
                ))

        # Deduplicate by (type, excerpt[:40])
        seen = set()
        deduped = []
        for f in findings:
            key = (f.finding_type, f.excerpt[:40])
            if key not in seen:
                seen.add(key)
                deduped.append(f)
        return deduped

    def risk_score(
        self, output: str, input_context: Optional[str] = None
    ) -> float:
        findings = self.scan(output, input_context)
        score = sum(_WEIGHTS.get(f.finding_type, 0.10) for f in findings)
        return min(score, 1.0)

    def is_safe(self, output: str, input_context: Optional[str] = None) -> bool:
        return self.risk_score(output, input_context) < 0.5
