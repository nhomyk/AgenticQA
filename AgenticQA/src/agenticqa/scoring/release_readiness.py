"""
ReleaseReadinessScorer — single 0-100 confidence score for production deployments.

The Problem
-----------
After an LLM writes a feature, a human developer stares at a wall of CI checks
and has to mentally aggregate: did tests pass? are there CVEs? is there a regression?
did compliance fail? They usually can't — and they ship anyway, or they block forever.

This module aggregates every AgenticQA signal into one authoritative answer:
  "Can I ship this?"

Signals (weighted to 100 pts total):
  test_coverage           20 pts  — SDET current_coverage %
  security_findings       25 pts  — RedTeam / Compliance critical+high findings
  cve_exposure            20 pts  — CVE Reachability critical CVEs in reachable code
  performance_regression  15 pts  — Perf Agent regression_detected
  compliance_violations   10 pts  — HIPAA + EU AI Act + Legal risk violations
  architecture_coverage   10 pts  — untested critical/high areas (Architecture Scanner)

Score thresholds:
  ≥ 85  →  SHIP IT           (all clear)
  ≥ 65  →  REVIEW REQUIRED   (issues present, human judgement needed)
  <  65  →  DO NOT SHIP       (blocking issues or score too low)

Any signal with blocking=True and status="red" forces DO NOT SHIP regardless of score.

Usage
-----
    from agenticqa.scoring import ReleaseReadinessScorer

    scorer = ReleaseReadinessScorer()
    report = scorer.score(
        sdet_result={"current_coverage": 82.5, "coverage_status": "passing"},
        security_findings=[],          # list of finding dicts with "severity" key
        cve_result={"critical_cves": 0, "reachable_cves": []},
        perf_result={"regression_detected": False},
        compliance_result={"violations": [], "conformity_score": 0.9},
        architecture_result={"untested_critical_high": 3, "total_areas": 40},
    )
    print(report.recommendation)  # "SHIP IT"
    print(report.overall_score)   # 91.5
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


# ── Thresholds ────────────────────────────────────────────────────────────────

_SHIP_THRESHOLD = 85.0
_REVIEW_THRESHOLD = 65.0

_WEIGHTS = {
    "test_coverage":           20,
    "security_findings":       25,
    "cve_exposure":            20,
    "performance_regression":  15,
    "compliance_violations":   10,
    "architecture_coverage":   10,
}

# Colours for status
_GREEN  = "green"
_YELLOW = "yellow"
_RED    = "red"
_GREY   = "grey"   # signal not provided


# ── Dataclasses ───────────────────────────────────────────────────────────────

@dataclass
class ReadinessSignal:
    """A single scored dimension of release readiness."""
    name: str
    display_name: str
    score: float           # 0–100 (100 = perfect for this signal)
    weight: int            # points this signal contributes to total (out of 100)
    weighted_contribution: float  # score * weight / 100
    status: str            # green | yellow | red | grey
    blocking: bool         # if True AND red → forces DO NOT SHIP
    detail: str            # human-readable explanation
    raw: Optional[Dict]    # original agent output (for audit)

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "display_name": self.display_name,
            "score": round(self.score, 1),
            "weight": self.weight,
            "weighted_contribution": round(self.weighted_contribution, 2),
            "status": self.status,
            "blocking": self.blocking,
            "detail": self.detail,
        }


@dataclass
class ReleaseReadinessReport:
    """Full release readiness assessment."""
    overall_score: float         # 0–100
    recommendation: str          # SHIP IT | REVIEW REQUIRED | DO NOT SHIP
    recommendation_reason: str
    signals: List[ReadinessSignal]
    blocking_issues: List[str]
    signals_provided: int        # how many signals had real data (vs. grey)
    signals_total: int
    timestamp: float = field(default_factory=time.time)

    @property
    def color(self) -> str:
        if self.recommendation == "SHIP IT":
            return _GREEN
        if self.recommendation == "REVIEW REQUIRED":
            return _YELLOW
        return _RED

    def by_name(self, name: str) -> Optional[ReadinessSignal]:
        return next((s for s in self.signals if s.name == name), None)

    def to_dict(self) -> dict:
        return {
            "overall_score": round(self.overall_score, 1),
            "recommendation": self.recommendation,
            "recommendation_reason": self.recommendation_reason,
            "color": self.color,
            "signals": [s.to_dict() for s in self.signals],
            "blocking_issues": self.blocking_issues,
            "signals_provided": self.signals_provided,
            "signals_total": self.signals_total,
            "timestamp": self.timestamp,
        }


# ── Scorer ────────────────────────────────────────────────────────────────────

class ReleaseReadinessScorer:
    """
    Aggregates AgenticQA agent outputs into a single 0-100 release readiness score.
    Partial inputs are fine — missing signals are treated as grey (neutral weight).
    """

    def score(
        self,
        sdet_result: Optional[Dict[str, Any]] = None,
        security_findings: Optional[List[Dict]] = None,
        cve_result: Optional[Dict[str, Any]] = None,
        perf_result: Optional[Dict[str, Any]] = None,
        compliance_result: Optional[Dict[str, Any]] = None,
        architecture_result: Optional[Dict[str, Any]] = None,
    ) -> ReleaseReadinessReport:
        """
        Score a release candidate.

        Args:
            sdet_result:         SDET agent output dict (needs current_coverage %)
            security_findings:   list of finding dicts with at least {"severity": str}
            cve_result:          CVE Reachability result dict
            perf_result:         Performance agent result dict
            compliance_result:   Compliance agent result dict
            architecture_result: dict with untested_critical_high + total_areas counts,
                                 OR an ArchitectureScanResult.to_dict() output

        Returns:
            ReleaseReadinessReport
        """
        signals: List[ReadinessSignal] = []

        signals.append(self._score_test_coverage(sdet_result))
        signals.append(self._score_security_findings(security_findings))
        signals.append(self._score_cve_exposure(cve_result))
        signals.append(self._score_performance(perf_result))
        signals.append(self._score_compliance(compliance_result))
        signals.append(self._score_architecture_coverage(architecture_result))

        # Compute weighted score (only over provided signals)
        provided = [s for s in signals if s.status != _GREY]
        grey     = [s for s in signals if s.status == _GREY]

        if not provided:
            # No data at all → conservative score
            overall = 50.0
        else:
            # Redistribute grey signal weights proportionally to provided signals
            provided_weight = sum(s.weight for s in provided)
            # Scale each provided signal's contribution to fill 100%
            scale = 100.0 / provided_weight if provided_weight else 1.0
            overall = sum(s.score * (s.weight * scale) / 100.0 for s in provided)

        # Collect blocking issues
        blocking_issues: List[str] = []
        for s in provided:
            if s.blocking and s.status == _RED:
                blocking_issues.append(s.detail)

        # Determine recommendation
        if blocking_issues:
            recommendation = "DO NOT SHIP"
            reason = f"{len(blocking_issues)} blocking issue(s) detected: {blocking_issues[0]}"
        elif overall >= _SHIP_THRESHOLD:
            recommendation = "SHIP IT"
            reason = f"All signals green. Score {overall:.1f}/100 exceeds threshold of {_SHIP_THRESHOLD}."
        elif overall >= _REVIEW_THRESHOLD:
            recommendation = "REVIEW REQUIRED"
            reason = f"Score {overall:.1f}/100 requires human review before shipping."
        else:
            recommendation = "DO NOT SHIP"
            reason = f"Score {overall:.1f}/100 is below minimum threshold of {_REVIEW_THRESHOLD}."

        return ReleaseReadinessReport(
            overall_score=round(overall, 1),
            recommendation=recommendation,
            recommendation_reason=reason,
            signals=signals,
            blocking_issues=blocking_issues,
            signals_provided=len(provided),
            signals_total=len(signals),
        )

    # ── Individual signal scorers ─────────────────────────────────────────────

    def _score_test_coverage(self, sdet: Optional[Dict]) -> ReadinessSignal:
        weight = _WEIGHTS["test_coverage"]
        if sdet is None:
            return self._grey("test_coverage", "Test Coverage", weight)

        coverage = float(sdet.get("current_coverage", sdet.get("coverage", 0)) or 0)

        if coverage >= 80:
            score, status, blocking = 100.0, _GREEN, False
            detail = f"Test coverage {coverage:.1f}% meets the 80% threshold."
        elif coverage >= 70:
            score, status, blocking = 75.0, _YELLOW, False
            detail = f"Test coverage {coverage:.1f}% is adequate but below 80% target."
        elif coverage >= 50:
            score, status, blocking = 40.0, _YELLOW, False
            detail = f"Test coverage {coverage:.1f}% is low — significant gaps exist."
        else:
            score, status, blocking = 0.0, _RED, True
            detail = f"Test coverage {coverage:.1f}% is critically low (<50%). BLOCKING."

        return ReadinessSignal(
            name="test_coverage", display_name="Test Coverage",
            score=score, weight=weight,
            weighted_contribution=score * weight / 100,
            status=status, blocking=blocking, detail=detail, raw=sdet,
        )

    def _score_security_findings(self, findings: Optional[List[Dict]]) -> ReadinessSignal:
        weight = _WEIGHTS["security_findings"]
        if findings is None:
            return self._grey("security_findings", "Security Findings", weight)

        criticals = sum(1 for f in findings if str(f.get("severity", "")).lower() == "critical")
        highs     = sum(1 for f in findings if str(f.get("severity", "")).lower() == "high")

        if criticals >= 2:
            score, status, blocking = 0.0, _RED, True
            detail = f"{criticals} CRITICAL security findings. BLOCKING release."
        elif criticals == 1:
            score, status, blocking = 10.0, _RED, True
            detail = f"1 CRITICAL security finding. BLOCKING release."
        elif highs >= 3:
            score, status, blocking = 40.0, _YELLOW, False
            detail = f"{highs} HIGH severity findings — review before shipping."
        elif highs >= 1:
            score, status, blocking = 70.0, _YELLOW, False
            detail = f"{highs} HIGH severity finding(s) — monitor closely."
        else:
            score, status, blocking = 100.0, _GREEN, False
            detail = f"No critical or high security findings. {len(findings)} total (low/info)."

        return ReadinessSignal(
            name="security_findings", display_name="Security Findings",
            score=score, weight=weight,
            weighted_contribution=score * weight / 100,
            status=status, blocking=blocking, detail=detail,
            raw={"critical": criticals, "high": highs, "total": len(findings)},
        )

    def _score_cve_exposure(self, cve: Optional[Dict]) -> ReadinessSignal:
        weight = _WEIGHTS["cve_exposure"]
        if cve is None:
            return self._grey("cve_exposure", "CVE Exposure", weight)

        critical_cves = int(cve.get("critical_cves", len([
            v for v in cve.get("reachable_cves", [])
            if str(v.get("severity", "")).lower() == "critical"
        ])))
        high_cves = int(cve.get("high_cves", len([
            v for v in cve.get("reachable_cves", [])
            if str(v.get("severity", "")).lower() == "high"
        ])))
        total_reachable = int(cve.get("total_reachable", len(cve.get("reachable_cves", []))))

        if critical_cves >= 1:
            score, status, blocking = 0.0, _RED, True
            detail = f"{critical_cves} critical CVE(s) in reachable code paths. BLOCKING."
        elif high_cves >= 3:
            score, status, blocking = 30.0, _RED, True
            detail = f"{high_cves} high CVEs in reachable paths. BLOCKING."
        elif high_cves >= 1:
            score, status, blocking = 60.0, _YELLOW, False
            detail = f"{high_cves} high CVE(s) reachable — upgrade dependencies before shipping."
        elif total_reachable > 0:
            score, status, blocking = 85.0, _YELLOW, False
            detail = f"{total_reachable} low/medium CVE(s) reachable — acceptable with monitoring."
        else:
            score, status, blocking = 100.0, _GREEN, False
            detail = "No reachable CVEs detected in call graph."

        return ReadinessSignal(
            name="cve_exposure", display_name="CVE Exposure",
            score=score, weight=weight,
            weighted_contribution=score * weight / 100,
            status=status, blocking=blocking, detail=detail, raw=cve,
        )

    def _score_performance(self, perf: Optional[Dict]) -> ReadinessSignal:
        weight = _WEIGHTS["performance_regression"]
        if perf is None:
            return self._grey("performance_regression", "Performance", weight)

        regression = bool(perf.get("regression_detected", False))
        duration_ms = float(perf.get("duration_ms", 0) or 0)
        baseline_ms = float(perf.get("baseline_ms", 0) or 0)

        if regression:
            pct = ""
            if baseline_ms > 0:
                pct = f" ({(duration_ms - baseline_ms) / baseline_ms * 100:.0f}% slower)"
            score, status, blocking = 0.0, _RED, True
            detail = f"Performance regression detected{pct}. BLOCKING."
        else:
            score, status, blocking = 100.0, _GREEN, False
            detail = "No performance regression detected."

        return ReadinessSignal(
            name="performance_regression", display_name="Performance",
            score=score, weight=weight,
            weighted_contribution=score * weight / 100,
            status=status, blocking=blocking, detail=detail, raw=perf,
        )

    def _score_compliance(self, compliance: Optional[Dict]) -> ReadinessSignal:
        weight = _WEIGHTS["compliance_violations"]
        if compliance is None:
            return self._grey("compliance_violations", "Compliance", weight)

        violations = compliance.get("violations", [])
        n_violations = len(violations) if isinstance(violations, list) else int(violations or 0)
        conformity = float(compliance.get("conformity_score", compliance.get("score", 1.0)) or 1.0)

        if n_violations >= 3 or conformity < 0.5:
            score, status, blocking = 0.0, _RED, True
            detail = f"{n_violations} compliance violation(s), conformity score {conformity:.2f}. BLOCKING."
        elif n_violations >= 1 or conformity < 0.8:
            score, status, blocking = 50.0, _YELLOW, False
            detail = f"{n_violations} compliance violation(s). Review required."
        else:
            score, status, blocking = 100.0, _GREEN, False
            detail = f"No compliance violations. Conformity score {conformity:.2f}."

        return ReadinessSignal(
            name="compliance_violations", display_name="Compliance",
            score=score, weight=weight,
            weighted_contribution=score * weight / 100,
            status=status, blocking=blocking, detail=detail, raw=compliance,
        )

    def _score_architecture_coverage(self, arch: Optional[Dict]) -> ReadinessSignal:
        weight = _WEIGHTS["architecture_coverage"]
        if arch is None:
            return self._grey("architecture_coverage", "Architecture Coverage", weight)

        # Accept either pre-computed counts or a full to_dict() result
        if "untested_critical_high" in arch:
            untested = int(arch["untested_critical_high"])
            total = int(arch.get("total_areas", max(untested, 1)))
        else:
            # Parse from ArchitectureScanResult.to_dict() output
            areas = arch.get("integration_areas", [])
            untested = sum(
                1 for a in areas
                if not a.get("test_files") and a.get("severity") in ("critical", "high")
            )
            total = len(areas)

        if total == 0:
            return self._grey("architecture_coverage", "Architecture Coverage", weight)

        fraction_untested = untested / total

        if fraction_untested >= 0.5:
            score, status, blocking = 20.0, _RED, False
            detail = f"{untested}/{total} critical/high areas have no test coverage (≥50%). High risk."
        elif fraction_untested >= 0.25:
            score, status, blocking = 60.0, _YELLOW, False
            detail = f"{untested}/{total} critical/high areas untested — consider adding coverage."
        elif untested > 0:
            score, status, blocking = 85.0, _YELLOW, False
            detail = f"{untested}/{total} critical/high areas untested."
        else:
            score, status, blocking = 100.0, _GREEN, False
            detail = f"All critical/high integration areas are covered by tests."

        return ReadinessSignal(
            name="architecture_coverage", display_name="Architecture Coverage",
            score=score, weight=weight,
            weighted_contribution=score * weight / 100,
            status=status, blocking=blocking, detail=detail, raw=arch,
        )

    @staticmethod
    def _grey(name: str, display_name: str, weight: int) -> ReadinessSignal:
        """Return a neutral grey signal for a missing input."""
        return ReadinessSignal(
            name=name, display_name=display_name,
            score=0.0, weight=weight,
            weighted_contribution=0.0,
            status=_GREY, blocking=False,
            detail="Signal not provided — excluded from score calculation.",
            raw=None,
        )
