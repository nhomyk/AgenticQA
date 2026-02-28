"""
Compliance Obligations Timeline

Given an organization's EU AI Act risk tier and HIPAA conformity score,
returns a prioritized, deadline-stamped action plan telling them exactly
what they must fix and by when.

Regulations covered
-------------------
EU AI Act (enforcement dates from 2024 regulation text)
  - Prohibited practices:        Aug 2, 2025  (already in force)
  - GPAI / general purpose AI:   Aug 2, 2025
  - High-risk obligations:       Aug 2, 2026
  - Limited/minimal risk:        Aug 2, 2027

HIPAA Security Rule
  - No hard calendar deadline — obligations are continuous.
  - Graded by severity: CRITICAL overdue, HIGH within 90 days,
    MEDIUM within 180 days.

Output
------
    from agenticqa.compliance.obligations_timeline import ObligationsTimeline

    timeline = ObligationsTimeline()
    plan = timeline.generate(
        eu_ai_act_tier="high_risk",
        eu_conformity_score=0.45,
        hipaa_score=0.60,
    )
    for item in plan.obligations:
        print(item.deadline, item.priority, item.action)
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import List, Optional


# ── EU AI Act enforcement calendar ────────────────────────────────────────────

_TODAY = date.today()

_EU_DEADLINES = {
    "prohibited":   date(2025, 8, 2),   # Art.5 — in force
    "gpai":         date(2025, 8, 2),   # GPAI model obligations
    "high_risk":    date(2026, 8, 2),   # Annex III high-risk systems
    "limited_risk": date(2027, 8, 2),   # transparency obligations
    "minimal_risk": date(2027, 8, 2),   # codes of conduct
}


def _days_until(d: date) -> int:
    return (d - _TODAY).days


def _deadline_priority(d: date) -> str:
    days = _days_until(d)
    if days < 0:
        return "OVERDUE"
    if days <= 90:
        return "CRITICAL"
    if days <= 180:
        return "HIGH"
    if days <= 365:
        return "MEDIUM"
    return "LOW"


# ── Dataclasses ────────────────────────────────────────────────────────────────

@dataclass
class Obligation:
    regulation: str          # "EU AI Act" | "HIPAA"
    article: str             # "Art.9", "§164.312(a)", …
    title: str               # short label
    action: str              # one-sentence action the org must take
    deadline: str            # ISO date string or "Ongoing"
    days_remaining: int      # negative = overdue
    priority: str            # OVERDUE | CRITICAL | HIGH | MEDIUM | LOW
    met: bool = False        # True when score threshold satisfied

    def to_dict(self) -> dict:
        return {
            "regulation": self.regulation,
            "article": self.article,
            "title": self.title,
            "action": self.action,
            "deadline": self.deadline,
            "days_remaining": self.days_remaining,
            "priority": self.priority,
            "met": self.met,
        }


@dataclass
class ObligationsPlan:
    eu_ai_act_tier: str
    eu_conformity_score: float
    hipaa_score: float
    obligations: List[Obligation] = field(default_factory=list)

    # Derived counts
    @property
    def overdue_count(self) -> int:
        return sum(1 for o in self.obligations if o.priority == "OVERDUE" and not o.met)

    @property
    def critical_count(self) -> int:
        return sum(1 for o in self.obligations if o.priority == "CRITICAL" and not o.met)

    @property
    def unmet_count(self) -> int:
        return sum(1 for o in self.obligations if not o.met)

    def summary(self) -> str:
        lines = [
            f"Compliance Obligations Timeline",
            f"  EU AI Act tier:       {self.eu_ai_act_tier}",
            f"  EU conformity score:  {self.eu_conformity_score:.0%}",
            f"  HIPAA score:          {self.hipaa_score:.0%}",
            f"  Total obligations:    {len(self.obligations)}",
            f"  Unmet:                {self.unmet_count}",
            f"  Overdue:              {self.overdue_count}",
            f"  Critical (≤90 days):  {self.critical_count}",
            "",
        ]
        _PRIORITY_ORDER = ["OVERDUE", "CRITICAL", "HIGH", "MEDIUM", "LOW"]
        shown = sorted(
            self.obligations,
            key=lambda o: (_PRIORITY_ORDER.index(o.priority), o.days_remaining),
        )
        for ob in shown:
            status = "✓" if ob.met else "✗"
            lines.append(
                f"  [{ob.priority:8}] {status} {ob.regulation} {ob.article} — {ob.title}"
            )
            lines.append(f"             Deadline: {ob.deadline}  Action: {ob.action}")
        return "\n".join(lines)

    def to_dict(self) -> dict:
        return {
            "eu_ai_act_tier": self.eu_ai_act_tier,
            "eu_conformity_score": round(self.eu_conformity_score, 3),
            "hipaa_score": round(self.hipaa_score, 3),
            "unmet_count": self.unmet_count,
            "overdue_count": self.overdue_count,
            "critical_count": self.critical_count,
            "obligations": [o.to_dict() for o in self.obligations],
        }


# ── Main class ─────────────────────────────────────────────────────────────────

class ObligationsTimeline:
    """Generate a deadline-stamped compliance action plan."""

    # Score thresholds — obligations below threshold are flagged as unmet
    _EU_MET_THRESHOLD = 0.70
    _HIPAA_MET_THRESHOLD = 0.75

    def generate(
        self,
        eu_ai_act_tier: str = "minimal_risk",
        eu_conformity_score: float = 1.0,
        hipaa_score: float = 1.0,
        include_met: bool = True,
    ) -> ObligationsPlan:
        """
        Generate a prioritized compliance action plan.

        Parameters
        ----------
        eu_ai_act_tier:       "high_risk" | "limited_risk" | "minimal_risk" | "unknown"
        eu_conformity_score:  0.0–1.0  (from AIActComplianceChecker)
        hipaa_score:          0.0–1.0  (from HIPAAPhiScanner or manual input)
        include_met:          include already-satisfied obligations in output
        """
        obligations: List[Obligation] = []
        eu_met = eu_conformity_score >= self._EU_MET_THRESHOLD

        # ── EU AI Act obligations ──────────────────────────────────────────────

        # Art.5 — prohibited practices apply to everyone
        d = _EU_DEADLINES["prohibited"]
        obligations.append(Obligation(
            regulation="EU AI Act",
            article="Art.5",
            title="Prohibited Practices Ban",
            action=(
                "Audit your system for any use of subliminal manipulation, "
                "social scoring, or real-time biometric surveillance. "
                "These are banned outright — no conformity path exists."
            ),
            deadline=d.isoformat(),
            days_remaining=_days_until(d),
            priority=_deadline_priority(d),
            met=eu_met,
        ))

        if eu_ai_act_tier in ("high_risk", "unknown"):
            d = _EU_DEADLINES["high_risk"]
            # Art.9 — risk management
            obligations.append(Obligation(
                regulation="EU AI Act",
                article="Art.9",
                title="Risk Management System",
                action=(
                    "Establish and document a continuous risk management process: "
                    "identify foreseeable risks, estimate severity, implement mitigations, "
                    "and maintain a log of residual risks."
                ),
                deadline=d.isoformat(),
                days_remaining=_days_until(d),
                priority=_deadline_priority(d),
                met=eu_conformity_score >= 0.65,
            ))
            # Art.13 — transparency
            obligations.append(Obligation(
                regulation="EU AI Act",
                article="Art.13",
                title="Transparency & Logging",
                action=(
                    "Ensure the AI system logs all decisions with sufficient context "
                    "for post-hoc review. Publish a plain-language description of the "
                    "system's purpose, logic, and limitations."
                ),
                deadline=d.isoformat(),
                days_remaining=_days_until(d),
                priority=_deadline_priority(d),
                met=eu_conformity_score >= 0.60,
            ))
            # Art.14 — human oversight
            obligations.append(Obligation(
                regulation="EU AI Act",
                article="Art.14",
                title="Human Oversight Mechanism",
                action=(
                    "Implement controls that allow a human operator to monitor, "
                    "intervene in, and override AI outputs. Document who is responsible "
                    "and how override is triggered."
                ),
                deadline=d.isoformat(),
                days_remaining=_days_until(d),
                priority=_deadline_priority(d),
                met=eu_conformity_score >= 0.70,
            ))
            # Art.17 — quality management
            obligations.append(Obligation(
                regulation="EU AI Act",
                article="Art.17",
                title="Quality Management System",
                action=(
                    "Document your data governance strategy, model testing methodology, "
                    "and post-market monitoring plan. This must be available for "
                    "inspection by national authorities."
                ),
                deadline=d.isoformat(),
                days_remaining=_days_until(d),
                priority=_deadline_priority(d),
                met=eu_conformity_score >= 0.75,
            ))
            # Art.22 — automated decisions
            obligations.append(Obligation(
                regulation="EU AI Act",
                article="Art.22",
                title="Accuracy & Robustness Testing",
                action=(
                    "Validate system accuracy, robustness against adversarial inputs, "
                    "and cybersecurity resilience. Document results in the technical file."
                ),
                deadline=d.isoformat(),
                days_remaining=_days_until(d),
                priority=_deadline_priority(d),
                met=eu_conformity_score >= 0.80,
            ))

        if eu_ai_act_tier in ("limited_risk", "high_risk", "unknown"):
            d = _EU_DEADLINES["limited_risk"]
            obligations.append(Obligation(
                regulation="EU AI Act",
                article="Art.52",
                title="Limited-Risk Transparency Disclosure",
                action=(
                    "Inform users that they are interacting with an AI system "
                    "whenever it is not obvious. Add a clear AI disclosure to all "
                    "user-facing interfaces."
                ),
                deadline=d.isoformat(),
                days_remaining=_days_until(d),
                priority=_deadline_priority(d),
                met=eu_conformity_score >= 0.50,
            ))

        # GPAI obligations (general purpose AI model providers)
        d = _EU_DEADLINES["gpai"]
        obligations.append(Obligation(
            regulation="EU AI Act",
            article="Art.53",
            title="GPAI Model Documentation",
            action=(
                "If you provide or use a general-purpose AI model, maintain a "
                "technical document covering training data sources, parameters, "
                "energy consumption, and copyright compliance."
            ),
            deadline=d.isoformat(),
            days_remaining=_days_until(d),
            priority=_deadline_priority(d),
            met=eu_met,
        ))

        # ── HIPAA obligations ──────────────────────────────────────────────────

        hipaa_met = hipaa_score >= self._HIPAA_MET_THRESHOLD

        def _hipaa_priority(threshold: float) -> str:
            """HIPAA has no hard date — severity based on gap to threshold."""
            gap = threshold - hipaa_score
            if gap <= 0:
                return "LOW"      # already met
            if gap > 0.4:
                return "CRITICAL"
            if gap > 0.2:
                return "HIGH"
            return "MEDIUM"

        hipaa_deadline_days = 90 if hipaa_score < 0.5 else 180
        hipaa_deadline = (_TODAY + timedelta(days=hipaa_deadline_days)).isoformat()

        obligations.append(Obligation(
            regulation="HIPAA",
            article="§164.308(a)(1)",
            title="Security Management Process",
            action=(
                "Conduct and document a risk analysis covering all PHI. "
                "Implement a risk management plan that reduces identified risks "
                "to a reasonable and appropriate level."
            ),
            deadline=hipaa_deadline,
            days_remaining=hipaa_deadline_days,
            priority=_hipaa_priority(0.60),
            met=hipaa_score >= 0.60,
        ))

        obligations.append(Obligation(
            regulation="HIPAA",
            article="§164.312(a)(1)",
            title="Access Control",
            action=(
                "Assign unique user IDs, enforce automatic logoff, "
                "encrypt/decrypt PHI in electronic form. "
                "Remove all hardcoded credentials from source code immediately."
            ),
            deadline=hipaa_deadline,
            days_remaining=hipaa_deadline_days,
            priority=_hipaa_priority(0.70),
            met=hipaa_score >= 0.70,
        ))

        obligations.append(Obligation(
            regulation="HIPAA",
            article="§164.312(b)",
            title="Audit Controls",
            action=(
                "Implement hardware, software, and procedural mechanisms that "
                "record and examine system activity. Ensure PHI access is logged "
                "and logs are retained for a minimum of 6 years."
            ),
            deadline=hipaa_deadline,
            days_remaining=hipaa_deadline_days,
            priority=_hipaa_priority(0.75),
            met=hipaa_score >= 0.75,
        ))

        obligations.append(Obligation(
            regulation="HIPAA",
            article="§164.312(e)(1)",
            title="Transmission Security",
            action=(
                "Ensure PHI transmitted over networks is encrypted (TLS 1.2+). "
                "Verify that no PHI is sent to LLM APIs or logged in plaintext."
            ),
            deadline=hipaa_deadline,
            days_remaining=hipaa_deadline_days,
            priority=_hipaa_priority(0.80),
            met=hipaa_score >= 0.80,
        ))

        # ── Sort and optionally filter ─────────────────────────────────────────
        _ORDER = {"OVERDUE": 0, "CRITICAL": 1, "HIGH": 2, "MEDIUM": 3, "LOW": 4}
        obligations.sort(key=lambda o: (_ORDER[o.priority], o.days_remaining, o.regulation))

        if not include_met:
            obligations = [o for o in obligations if not o.met]

        return ObligationsPlan(
            eu_ai_act_tier=eu_ai_act_tier,
            eu_conformity_score=eu_conformity_score,
            hipaa_score=hipaa_score,
            obligations=obligations,
        )
