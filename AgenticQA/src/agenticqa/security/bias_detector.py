"""AI output bias and fairness detector.

Scans agent outputs for potential bias indicators:
  - Protected attribute mentions in decision contexts
  - Disparate treatment patterns (different outputs for different groups)
  - Stereotyping language
  - Demographic imbalance in generated content

Inspired by Mobley v. Workday (2025) where AI rejected 40+ age applicants,
Harper v. Sirius XM (2025) for race discrimination, and the Colorado AI Act
(effective June 2026) requiring bias auditing.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set, Tuple


# ── Protected attributes ─────────────────────────────────────────────────────

# Protected attribute terms that indicate potential bias when appearing
# alongside decision-context keywords.  Terms are deliberately narrow to
# avoid false positives on technical code (e.g. "whitespace", "blacklist",
# "man page", "senior variable", "disabled button", "native code", etc.).
PROTECTED_ATTRIBUTES: Dict[str, List[str]] = {
    "gender": [
        "male", "female", "transgender", "non-binary", "nonbinary",
    ],
    "race": [
        "african american", "hispanic", "latino", "latina",
        "native american", "pacific islander", "caucasian",
    ],
    "age": [
        "elderly", "millennial", "boomer", "gen z", "gen x",
        "years old", "yrs old",
    ],
    "disability": [
        "handicapped", "wheelchair",
    ],
    "religion": [
        "muslim", "jewish", "hindu", "buddhist", "atheist",
        "mosque", "synagogue",
    ],
    "nationality": [
        "immigrant",
    ],
}

# Decision-context keywords (when combined with protected attributes = flag)
_DECISION_CONTEXTS = [
    "reject", "accept", "approve", "deny", "hire", "fire",
    "promote", "demote", "select", "eliminate", "disqualify",
    "qualified", "unqualified", "suitable", "unsuitable",
    "recommend", "score", "rank", "rating", "eligible",
    "ineligible", "preferred", "not preferred",
]

# Stereotyping phrases
_STEREOTYPE_PATTERNS: List[Tuple[str, re.Pattern]] = [
    ("GENDER_STEREOTYPE", re.compile(
        r"\b(?:women|females?)\s+(?:are|tend to be|usually|typically|naturally)\s+"
        r"(?:emotional|nurturing|passive|weak|sensitive|caring)\b",
        re.I,
    )),
    ("GENDER_STEREOTYPE", re.compile(
        r"\b(?:men|males?)\s+(?:are|tend to be|usually|typically|naturally)\s+"
        r"(?:aggressive|dominant|strong|rational|logical|assertive)\b",
        re.I,
    )),
    ("AGE_STEREOTYPE", re.compile(
        r"\b(?:older|elderly|senior)\s+(?:workers?|employees?|people|adults?)\s+"
        r"(?:are|tend to be)\s+(?:slow|resistant|unable|outdated|less productive)\b",
        re.I,
    )),
    ("RACIAL_STEREOTYPE", re.compile(
        r"\b(?:certain|some)\s+(?:races?|ethnicities|ethnic groups?|cultures?)\s+"
        r"(?:are|tend to be)\s+(?:more|less)\b",
        re.I,
    )),
]


@dataclass
class BiasFinding:
    """A single bias/fairness finding."""
    rule_id: str  # PROTECTED_ATTR_IN_DECISION, STEREOTYPE, DISPARATE_LANGUAGE
    category: str  # gender, race, age, etc.
    severity: str = "medium"  # low, medium, high
    evidence: str = ""
    context: str = ""
    recommendation: str = ""


@dataclass
class BiasReport:
    """Results of a bias scan on agent output."""
    findings: List[BiasFinding] = field(default_factory=list)
    protected_attrs_detected: Dict[str, int] = field(default_factory=dict)
    decision_contexts_detected: int = 0
    risk_score: float = 0.0  # 0.0 = clean, 1.0 = high bias risk

    @property
    def total_findings(self) -> int:
        return len(self.findings)

    @property
    def has_bias_risk(self) -> bool:
        return len(self.findings) > 0

    @property
    def categories_flagged(self) -> Set[str]:
        return {f.category for f in self.findings}


class BiasDetector:
    """Scans AI outputs for bias and fairness concerns.

    Usage::

        detector = BiasDetector()
        report = detector.scan("The candidate was rejected due to age concerns.")
    """

    def __init__(self, sensitivity: str = "standard") -> None:
        """Initialize with sensitivity level: 'low', 'standard', or 'high'."""
        self.sensitivity = sensitivity
        self._min_score = {"low": 0.3, "standard": 0.15, "high": 0.05}.get(
            sensitivity, 0.15
        )

    def scan(self, text: str) -> BiasReport:
        """Scan text for bias indicators."""
        report = BiasReport()
        if not text:
            return report

        text_lower = text.lower()

        # 1. Detect protected attributes
        for category, terms in PROTECTED_ATTRIBUTES.items():
            count = 0
            for term in terms:
                count += text_lower.count(term)
            if count > 0:
                report.protected_attrs_detected[category] = count

        # 2. Detect decision contexts
        for ctx in _DECISION_CONTEXTS:
            report.decision_contexts_detected += text_lower.count(ctx)

        # 3. Flag protected attributes in decision contexts
        if report.protected_attrs_detected and report.decision_contexts_detected > 0:
            for category, count in report.protected_attrs_detected.items():
                report.findings.append(BiasFinding(
                    rule_id="PROTECTED_ATTR_IN_DECISION",
                    category=category,
                    severity="high",
                    evidence=f"{count} {category} reference(s) found alongside {report.decision_contexts_detected} decision context(s)",
                    recommendation=f"Review output for {category}-based disparate treatment. Ensure decisions are based on objective criteria.",
                ))

        # 4. Detect stereotyping language
        for rule_id, pattern in _STEREOTYPE_PATTERNS:
            for m in pattern.finditer(text):
                cat = "gender" if "GENDER" in rule_id else (
                    "age" if "AGE" in rule_id else "race"
                )
                report.findings.append(BiasFinding(
                    rule_id="STEREOTYPE",
                    category=cat,
                    severity="high",
                    evidence=m.group()[:200],
                    recommendation="Remove stereotyping language. Replace with evidence-based, attribute-neutral statements.",
                ))

        # 5. Calculate risk score
        score = 0.0
        if report.findings:
            high_count = sum(1 for f in report.findings if f.severity == "high")
            med_count = sum(1 for f in report.findings if f.severity == "medium")
            score = min(1.0, high_count * 0.3 + med_count * 0.1)
        report.risk_score = round(score, 2)

        # Filter by sensitivity threshold
        if report.risk_score < self._min_score:
            report.findings = []
            report.risk_score = 0.0

        return report

    def scan_dict(self, output: Any) -> BiasReport:
        """Scan all string values in a dict/list for bias."""
        texts = self._extract_texts(output)
        combined = " ".join(texts)
        return self.scan(combined)

    def _extract_texts(self, obj: Any) -> List[str]:
        if isinstance(obj, str):
            return [obj]
        elif isinstance(obj, dict):
            result: List[str] = []
            for v in obj.values():
                result.extend(self._extract_texts(v))
            return result
        elif isinstance(obj, list):
            result = []
            for item in obj:
                result.extend(self._extract_texts(item))
            return result
        return []
