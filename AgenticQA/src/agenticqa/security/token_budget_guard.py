"""
TokenBudgetGuard — detects token/cost amplification (sponge) attacks.

Problem
-------
LLM APIs charge per token.  An adversary can craft inputs that:
1. Maximise output length (e.g. "write 10,000 words about X")
2. Contain high-entropy noise that tricks the model into long chains-of-thought
3. Use repetitive sequences that expand exponentially through template substitution
4. Trigger expensive tool cascades via hidden instructions

None of these hit a simple rate limiter (one request, enormous cost).

Solution
--------
Heuristic pre-flight on both input and projected output using a zero-dependency
token estimator (1 token ≈ 4 chars, corrected for CJK and whitespace).

Risk signals (weighted sum → risk_score 0–1):
  - EXTREME_LENGTH       input > 32k chars
  - REPETITION_ATTACK    >60% of 8-grams are repeated (sponge pattern)
  - LONG_OUTPUT_REQUEST  "write N words/pages/paragraphs" where N > 500
  - CONTEXT_STUFFING     >80% whitespace or filler tokens
  - RECURSIVE_EXPANSION  nested template-like patterns ({{...}} > depth 3)
  - LOW_ENTROPY          Shannon entropy < 2.5 bits/char (uniform noise)

Usage
-----
    from agenticqa.security.token_budget_guard import TokenBudgetGuard

    guard = TokenBudgetGuard()
    result = guard.check_input(user_text)
    if not result.safe:
        raise ValueError(f"Token budget risk: {result.risk_score:.2f} — {result.signals}")
"""
from __future__ import annotations

import math
import re
from dataclasses import dataclass, field
from typing import List, Optional

# ── Weights ───────────────────────────────────────────────────────────────────

_WEIGHTS = {
    "EXTREME_LENGTH":       0.35,
    "REPETITION_ATTACK":    0.30,
    "LONG_OUTPUT_REQUEST":  0.25,
    "CONTEXT_STUFFING":     0.15,
    "RECURSIVE_EXPANSION":  0.20,
    "LOW_ENTROPY":          0.15,
}

_LONG_OUTPUT_RE = re.compile(
    r"(write|generate|produce|output|create|list|enumerate|give\s+me)\s+"
    r"(?:at\s+least\s+)?(\d{3,})\s+"
    r"(word|sentence|paragraph|page|line|item|bullet|token|char)",
    re.IGNORECASE,
)

_TEMPLATE_RE = re.compile(r"\{\{|\}\}")   # Jinja/handlebars style nesting


@dataclass
class TokenBudgetResult:
    safe: bool
    estimated_tokens: int
    risk_score: float
    signals: List[str] = field(default_factory=list)
    detail: Optional[str] = None


class TokenBudgetGuard:
    """Pre-flight token budget and sponge-attack detector."""

    def __init__(
        self,
        max_input_tokens: int = 32_000,
        max_output_request: int = 500,
        risk_threshold: float = 0.5,
    ) -> None:
        self.max_input_tokens = max_input_tokens
        self.max_output_request = max_output_request
        self.risk_threshold = risk_threshold

    # ── Public API ────────────────────────────────────────────────────────────

    def check_input(self, text: str) -> TokenBudgetResult:
        """Full sponge-attack analysis of an input string."""
        tokens = self._estimate_tokens(text)
        signals: List[str] = []
        score = 0.0

        # 1. Extreme length
        if len(text) > self.max_input_tokens * 4:
            signals.append("EXTREME_LENGTH")
            score += _WEIGHTS["EXTREME_LENGTH"]

        # 2. Repetition attack
        rep = self._repetition_ratio(text)
        if rep > 0.60:
            signals.append("REPETITION_ATTACK")
            score += _WEIGHTS["REPETITION_ATTACK"] * min(rep / 0.60, 1.5)

        # 3. Long output request
        m = _LONG_OUTPUT_RE.search(text)
        if m:
            n = int(m.group(2))
            if n > self.max_output_request:
                signals.append(f"LONG_OUTPUT_REQUEST({n})")
                score += _WEIGHTS["LONG_OUTPUT_REQUEST"] * min(n / self.max_output_request, 2.0)

        # 4. Context stuffing (mostly whitespace/filler)
        ws_ratio = sum(1 for c in text if c in " \t\n\r") / max(len(text), 1)
        if ws_ratio > 0.80:
            signals.append("CONTEXT_STUFFING")
            score += _WEIGHTS["CONTEXT_STUFFING"]

        # 5. Recursive expansion (deep template nesting)
        depth = len(_TEMPLATE_RE.findall(text)) // 2
        if depth > 3:
            signals.append(f"RECURSIVE_EXPANSION(depth={depth})")
            score += _WEIGHTS["RECURSIVE_EXPANSION"] * min(depth / 3, 2.0)

        # 6. Low entropy (uniform noise maximises model uncertainty → long replies)
        entropy = self._shannon_entropy(text[:4096])  # sample first 4k chars
        if entropy < 2.5 and len(text) > 200:
            signals.append(f"LOW_ENTROPY({entropy:.2f})")
            score += _WEIGHTS["LOW_ENTROPY"]

        score = min(score, 1.0)
        return TokenBudgetResult(
            safe=score < self.risk_threshold,
            estimated_tokens=tokens,
            risk_score=round(score, 4),
            signals=signals,
            detail=f"Repetition={rep:.2f}, entropy={entropy:.2f}, tokens≈{tokens}",
        )

    def check_output(self, text: str, max_tokens: int = 16_000) -> TokenBudgetResult:
        """Check whether a generated output is suspiciously large."""
        tokens = self._estimate_tokens(text)
        signals: List[str] = []
        score = 0.0
        if tokens > max_tokens:
            signals.append(f"OUTPUT_TOO_LARGE({tokens})")
            score = min((tokens / max_tokens) * 0.5, 1.0)
        rep = self._repetition_ratio(text)
        if rep > 0.70:
            signals.append("OUTPUT_REPETITION")
            score = min(score + _WEIGHTS["REPETITION_ATTACK"], 1.0)
        return TokenBudgetResult(
            safe=score < self.risk_threshold,
            estimated_tokens=tokens,
            risk_score=round(score, 4),
            signals=signals,
        )

    # ── Helpers ───────────────────────────────────────────────────────────────

    @staticmethod
    def _estimate_tokens(text: str) -> int:
        """Fast token estimate: 1 token ≈ 4 chars for Latin, ≈ 1 char for CJK."""
        latin = sum(1 for c in text if ord(c) < 0x2E80)
        cjk   = len(text) - latin
        return (latin // 4) + cjk + 1

    @staticmethod
    def _repetition_ratio(text: str, n: int = 8) -> float:
        """Fraction of n-grams that are repeated (0 = no repetition, 1 = all repeated)."""
        if len(text) < n * 2:
            return 0.0
        ngrams = [text[i:i+n] for i in range(len(text) - n)]
        if not ngrams:
            return 0.0
        unique = len(set(ngrams))
        return 1.0 - (unique / len(ngrams))

    @staticmethod
    def _shannon_entropy(text: str) -> float:
        """Shannon entropy in bits per character."""
        if not text:
            return 0.0
        freq: dict = {}
        for c in text:
            freq[c] = freq.get(c, 0) + 1
        n = len(text)
        return -sum((v / n) * math.log2(v / n) for v in freq.values())
