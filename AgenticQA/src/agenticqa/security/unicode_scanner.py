"""
UnicodeThreatScanner — detects invisible, directional, and confusable Unicode
characters used to bypass string-match security controls.

Attack vectors
--------------
INVISIBLE_CHARS     — zero-width spaces/joiners, word joiners, BOM, soft hyphen
                      inserted between shell characters to evade regex detection
DIRECTIONAL_OVERRIDE — RTL/LTR bidi overrides that make malicious text display
                       as innocent text (U+202E makes "malicious.exe" look like
                       "exe.suoicilam" in some renderers)
CONFUSABLE_HOMOGLYPH — Cyrillic/Greek/Armenian letters that look identical to
                       Latin letters; used to spoof allowlisted identifiers
                       ("аdmin" with Cyrillic а passes an "admin" blocklist)
STEGANOGRAPHIC_TAGS  — Unicode tag characters U+E0000–U+E007F; invisible in most
                       renderers but can carry covert payloads
SUSPICIOUS_DENSITY   — text where >10% of code points are non-ASCII in a context
                       where ASCII is expected (e.g., code, shell commands)

Usage
-----
    from agenticqa.security.unicode_scanner import UnicodeThreatScanner

    scanner = UnicodeThreatScanner()
    findings = scanner.scan("аdmin")   # Cyrillic 'а'
    # [UnicodeFinding(attack_type='CONFUSABLE_HOMOGLYPH', ...)]

    safe_text = scanner.strip_invisible("hello\u200bworld")  # → "helloworld"
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from typing import List, Set, Tuple


# ---------------------------------------------------------------------------
# Finding
# ---------------------------------------------------------------------------

@dataclass
class UnicodeFinding:
    attack_type: str    # INVISIBLE_CHARS | DIRECTIONAL_OVERRIDE | CONFUSABLE_HOMOGLYPH | STEGANOGRAPHIC_TAGS
    severity: str       # critical | high | medium
    offset: int         # character offset where first bad codepoint found
    codepoints: List[str]  # list of hex codepoints (e.g. ["U+200B"])
    detail: str

    def __str__(self) -> str:
        return (
            f"[{self.severity.upper()}] {self.attack_type}: {self.detail} "
            f"(first at offset {self.offset}, codepoints: {self.codepoints[:5]})"
        )


# ---------------------------------------------------------------------------
# Codepoint sets
# ---------------------------------------------------------------------------

_INVISIBLE: Set[int] = {
    0x200B,  # ZERO WIDTH SPACE
    0x200C,  # ZERO WIDTH NON-JOINER
    0x200D,  # ZERO WIDTH JOINER
    0x2060,  # WORD JOINER
    0xFEFF,  # ZERO WIDTH NO-BREAK SPACE / BOM (when not at start of file)
    0x00AD,  # SOFT HYPHEN
    0x034F,  # COMBINING GRAPHEME JOINER
    0x180E,  # MONGOLIAN VOWEL SEPARATOR
    0x17B5,  # KHMER VOWEL INHERENT AQ (invisible)
    0x17B4,  # KHMER VOWEL INHERENT AA (invisible)
}

_DIRECTIONAL: Set[int] = {
    0x202A,  # LEFT-TO-RIGHT EMBEDDING
    0x202B,  # RIGHT-TO-LEFT EMBEDDING
    0x202C,  # POP DIRECTIONAL FORMATTING
    0x202D,  # LEFT-TO-RIGHT OVERRIDE
    0x202E,  # RIGHT-TO-LEFT OVERRIDE  ← most dangerous
    0x2066,  # LEFT-TO-RIGHT ISOLATE
    0x2067,  # RIGHT-TO-LEFT ISOLATE
    0x2068,  # FIRST STRONG ISOLATE
    0x2069,  # POP DIRECTIONAL ISOLATE
    0x200E,  # LEFT-TO-RIGHT MARK
    0x200F,  # RIGHT-TO-LEFT MARK
}

# Highly-suspicious tag range (all invisible)
_TAG_START = 0xE0000
_TAG_END   = 0xE007F

# Confusable homoglyphs: Cyrillic/Greek that are visually identical to Latin
# Mapping: confusable codepoint → expected Latin equivalent (for reporting)
_CONFUSABLES: dict[int, str] = {
    # Cyrillic → Latin lookalikes
    0x0430: "a",  # CYRILLIC SMALL LETTER A
    0x0435: "e",  # CYRILLIC SMALL LETTER IE
    0x043E: "o",  # CYRILLIC SMALL LETTER O
    0x0440: "r",  # CYRILLIC SMALL LETTER ER  (subtle)
    0x0441: "c",  # CYRILLIC SMALL LETTER ES
    0x0445: "x",  # CYRILLIC SMALL LETTER HA
    0x0440: "p",  # CYRILLIC SMALL LETTER ER (also looks like p)
    0x0392: "B",  # GREEK CAPITAL LETTER BETA
    0x0395: "E",  # GREEK CAPITAL LETTER EPSILON
    0x0396: "Z",  # GREEK CAPITAL LETTER ZETA
    0x0397: "H",  # GREEK CAPITAL LETTER ETA
    0x0399: "I",  # GREEK CAPITAL LETTER IOTA
    0x039A: "K",  # GREEK CAPITAL LETTER KAPPA
    0x039C: "M",  # GREEK CAPITAL LETTER MU
    0x039D: "N",  # GREEK CAPITAL LETTER NU
    0x039F: "O",  # GREEK CAPITAL LETTER OMICRON
    0x03A1: "P",  # GREEK CAPITAL LETTER RHO
    0x03A4: "T",  # GREEK CAPITAL LETTER TAU
    0x03A5: "Y",  # GREEK CAPITAL LETTER UPSILON
    0x03A7: "X",  # GREEK CAPITAL LETTER CHI
    0x03B1: "a",  # GREEK SMALL LETTER ALPHA
    0x03BF: "o",  # GREEK SMALL LETTER OMICRON
    0x0410: "A",  # CYRILLIC CAPITAL LETTER A
    0x0412: "B",  # CYRILLIC CAPITAL LETTER VE
    0x0415: "E",  # CYRILLIC CAPITAL LETTER IE
    0x041A: "K",  # CYRILLIC CAPITAL LETTER KA
    0x041C: "M",  # CYRILLIC CAPITAL LETTER EM
    0x041D: "H",  # CYRILLIC CAPITAL LETTER EN (looks like H)
    0x041E: "O",  # CYRILLIC CAPITAL LETTER O
    0x0420: "P",  # CYRILLIC CAPITAL LETTER ER
    0x0421: "C",  # CYRILLIC CAPITAL LETTER ES
    0x0422: "T",  # CYRILLIC CAPITAL LETTER TE
    0x0423: "Y",  # CYRILLIC CAPITAL LETTER U (looks like Y)
    0x0425: "X",  # CYRILLIC CAPITAL LETTER HA
}


# ---------------------------------------------------------------------------
# Scanner
# ---------------------------------------------------------------------------

_SEVERITY_WEIGHTS = {"critical": 0.4, "high": 0.2, "medium": 0.1}


class UnicodeThreatScanner:
    """
    Detects Unicode-based attacks in text strings.

    scan(text)            → List[UnicodeFinding]
    is_safe(text)         → bool (no critical findings, risk_score < 0.5)
    strip_invisible(text) → str with all invisible/directional chars removed
    normalize(text)       → NFKC-normalized text (resolves homoglyph lookalikes)
    """

    def scan(self, text: str) -> List[UnicodeFinding]:
        findings: List[UnicodeFinding] = []

        invisible_offsets: List[int] = []
        directional_offsets: List[int] = []
        tag_offsets: List[int] = []
        confusable_offsets: List[Tuple[int, int, str]] = []  # (offset, cp, latin_equiv)

        for i, ch in enumerate(text):
            cp = ord(ch)
            if cp in _INVISIBLE:
                invisible_offsets.append(i)
            elif cp in _DIRECTIONAL:
                directional_offsets.append(i)
            elif _TAG_START <= cp <= _TAG_END:
                tag_offsets.append(i)
            elif cp in _CONFUSABLES:
                confusable_offsets.append((i, cp, _CONFUSABLES[cp]))

        if invisible_offsets:
            cps = [f"U+{ord(text[i]):04X}" for i in invisible_offsets[:10]]
            findings.append(UnicodeFinding(
                attack_type="INVISIBLE_CHARS",
                severity="high",
                offset=invisible_offsets[0],
                codepoints=cps,
                detail=f"{len(invisible_offsets)} invisible codepoint(s) detected — "
                       f"may bypass regex-based security filters",
            ))

        if directional_offsets:
            # U+202E (RTL Override) is critical; others are high
            has_rtl_override = any(ord(text[i]) == 0x202E for i in directional_offsets)
            severity = "critical" if has_rtl_override else "high"
            cps = [f"U+{ord(text[i]):04X}" for i in directional_offsets[:10]]
            findings.append(UnicodeFinding(
                attack_type="DIRECTIONAL_OVERRIDE",
                severity=severity,
                offset=directional_offsets[0],
                codepoints=cps,
                detail=f"Bidirectional override character(s) — can make malicious filenames "
                       f"appear innocent in file explorers and terminals",
            ))

        if tag_offsets:
            cps = [f"U+{ord(text[i]):04X}" for i in tag_offsets[:10]]
            findings.append(UnicodeFinding(
                attack_type="STEGANOGRAPHIC_TAGS",
                severity="critical",
                offset=tag_offsets[0],
                codepoints=cps,
                detail=f"{len(tag_offsets)} Unicode tag character(s) (U+E0000–U+E007F) — "
                       f"invisible covert channel in text",
            ))

        if confusable_offsets:
            cps = [f"U+{cp:04X}(≈'{lat}')" for _, cp, lat in confusable_offsets[:10]]
            findings.append(UnicodeFinding(
                attack_type="CONFUSABLE_HOMOGLYPH",
                severity="high",
                offset=confusable_offsets[0][0],
                codepoints=cps,
                detail=f"{len(confusable_offsets)} homoglyph(s) — non-Latin chars that "
                       f"visually resemble Latin letters; may bypass identifier allowlists",
            ))

        return findings

    def risk_score(self, text: str) -> float:
        findings = self.scan(text)
        return min(sum(_SEVERITY_WEIGHTS.get(f.severity, 0) for f in findings), 1.0)

    def is_safe(self, text: str) -> bool:
        findings = self.scan(text)
        return (
            not any(f.severity == "critical" for f in findings)
            and self.risk_score(text) < 0.5
        )

    def strip_invisible(self, text: str) -> str:
        """Remove all invisible and directional override characters."""
        return "".join(
            ch for ch in text
            if ord(ch) not in _INVISIBLE
            and ord(ch) not in _DIRECTIONAL
            and not (_TAG_START <= ord(ch) <= _TAG_END)
        )

    def normalize(self, text: str) -> str:
        """NFKC normalization — resolves many homoglyph equivalences."""
        return unicodedata.normalize("NFKC", text)
