"""
Coverage Tracker — Map test results back to the failure taxonomy.

INTERVIEW CONCEPT: "Coverage" in K8s testing isn't about code coverage.
It's about failure mode coverage — what percentage of known failure
scenarios does your test suite exercise? This is the metric that tells
you how confident you can be in a release.

The coverage model:
    Total scenarios in taxonomy     → "full coverage" denominator
    Scenarios tested (any result)   → numerator
    Scenarios passed                → resilience score
    Scenarios failed                → known vulnerabilities
    Scenarios untested              → risk gaps

Usage:
    taxonomy = FailureTaxonomy.load()
    tracker = CoverageTracker(taxonomy)

    # Record results from chaos experiments
    for result in engine.results:
        tracker.record(result.taxonomy_id, passed=(result.status == "passed"))

    # Record results from probe runner
    for result in probes.run_all():
        for tid in result.taxonomy_ids:
            tracker.record(tid, passed=(result.status == "healthy"))

    # Generate report
    report = tracker.report()
    print(f"Coverage: {report['coverage_percent']:.1f}%")
    print(f"Gaps: {report['untested_scenarios']}")
"""

from __future__ import annotations

import json
import logging
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from agenticqa.k8s.taxonomy import FailureTaxonomy, Scenario

logger = logging.getLogger(__name__)


@dataclass
class TestRecord:
    """Record of a test execution against a taxonomy scenario."""

    taxonomy_id: str
    passed: bool
    timestamp: str = ""
    experiment_name: str = ""
    details: dict = field(default_factory=dict)

    def __post_init__(self):
        if not self.timestamp:
            self.timestamp = datetime.now(timezone.utc).isoformat()


@dataclass
class CoverageGap:
    """An untested failure scenario."""

    scenario: Scenario
    risk_level: str  # "critical", "high", "medium", "low"
    recommendation: str


class CoverageTracker:
    """
    Tracks which failure taxonomy scenarios have been tested.

    Maps chaos experiment results, probe results, and manual test
    records back to the taxonomy to calculate coverage percentage.
    """

    def __init__(self, taxonomy: FailureTaxonomy) -> None:
        self._taxonomy = taxonomy
        self._records: dict[str, list[TestRecord]] = defaultdict(list)

    def record(
        self,
        taxonomy_id: str,
        passed: bool,
        experiment_name: str = "",
        details: Optional[dict] = None,
    ) -> None:
        """Record a test result against a taxonomy scenario."""
        self._records[taxonomy_id].append(
            TestRecord(
                taxonomy_id=taxonomy_id,
                passed=passed,
                experiment_name=experiment_name,
                details=details or {},
            )
        )

    def record_from_chaos_results(self, results: list) -> None:
        """
        Record results from ChaosEngine.results.

        Accepts list of ExperimentResult dataclasses.
        """
        for r in results:
            if hasattr(r, "taxonomy_id") and hasattr(r, "status"):
                passed = r.status.value == "passed" if hasattr(r.status, "value") else r.status == "passed"
                self.record(
                    taxonomy_id=r.taxonomy_id,
                    passed=passed,
                    experiment_name=getattr(r, "experiment_name", ""),
                    details=getattr(r, "details", {}),
                )

    @property
    def tested_ids(self) -> set[str]:
        """Set of taxonomy IDs that have at least one test record."""
        return set(self._records.keys())

    @property
    def untested_ids(self) -> set[str]:
        """Set of taxonomy IDs with no test records."""
        all_ids = {s.id for s in self._taxonomy}
        return all_ids - self.tested_ids

    def coverage_percent(self) -> float:
        """Overall coverage percentage."""
        total = len(self._taxonomy)
        if total == 0:
            return 100.0
        return (len(self.tested_ids) / total) * 100

    def resilience_score(self) -> float:
        """
        Percentage of tested scenarios that passed.

        This is different from coverage — coverage tells you what you've
        tested, resilience tells you what your system actually survives.
        """
        tested = [
            tid
            for tid, records in self._records.items()
            if any(r.passed for r in records)
        ]
        total_tested = len(self.tested_ids)
        if total_tested == 0:
            return 0.0
        return (len(tested) / total_tested) * 100

    def gaps(self) -> list[CoverageGap]:
        """
        List untested scenarios as coverage gaps, sorted by severity.

        This is the "what should we test next?" output.
        """
        gaps = []
        for scenario_id in self.untested_ids:
            scenario = self._taxonomy.get(scenario_id)
            if not scenario:
                continue
            gaps.append(
                CoverageGap(
                    scenario=scenario,
                    risk_level=scenario.severity,
                    recommendation=f"Add test for: {scenario.test_method}",
                )
            )
        # Sort by severity (critical first)
        return sorted(gaps, key=lambda g: g.scenario.severity_rank)

    def report(self) -> dict:
        """
        Full coverage report.

        Returns a dict with:
            - coverage_percent: % of taxonomy scenarios tested
            - resilience_score: % of tested scenarios that passed
            - by_category: per-category coverage breakdown
            - by_severity: per-severity coverage breakdown
            - untested_critical: critical scenarios with no tests
            - untested_count: total untested scenarios
        """
        tested = self.tested_ids
        by_category = {}
        by_severity = {}

        for cat in self._taxonomy.categories:
            scenarios = self._taxonomy.filter(category=cat)
            total = len(scenarios)
            covered = sum(1 for s in scenarios if s.id in tested)
            by_category[cat] = {
                "total": total,
                "tested": covered,
                "coverage": (covered / total * 100) if total > 0 else 100.0,
            }

        for sev in ("critical", "high", "medium", "low"):
            scenarios = self._taxonomy.filter(severity=sev)
            total = len(scenarios)
            covered = sum(1 for s in scenarios if s.id in tested)
            by_severity[sev] = {
                "total": total,
                "tested": covered,
                "coverage": (covered / total * 100) if total > 0 else 100.0,
            }

        untested_critical = [
            s.id
            for s in self._taxonomy.filter(severity="critical")
            if s.id not in tested
        ]

        return {
            "coverage_percent": self.coverage_percent(),
            "resilience_score": self.resilience_score(),
            "total_scenarios": len(self._taxonomy),
            "tested_scenarios": len(tested),
            "untested_count": len(self._taxonomy) - len(tested),
            "by_category": by_category,
            "by_severity": by_severity,
            "untested_critical": untested_critical,
        }

    def save(self, path: str) -> None:
        """Save coverage data to JSON for historical tracking."""
        data = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "report": self.report(),
            "records": {
                tid: [
                    {
                        "passed": r.passed,
                        "timestamp": r.timestamp,
                        "experiment": r.experiment_name,
                    }
                    for r in records
                ]
                for tid, records in self._records.items()
            },
        }
        Path(path).write_text(json.dumps(data, indent=2))
        logger.info("Coverage data saved to %s", path)

    @classmethod
    def load(cls, path: str, taxonomy: FailureTaxonomy) -> CoverageTracker:
        """Load coverage data from a previous save."""
        data = json.loads(Path(path).read_text())
        tracker = cls(taxonomy)
        for tid, records in data.get("records", {}).items():
            for r in records:
                tracker.record(
                    taxonomy_id=tid,
                    passed=r["passed"],
                    experiment_name=r.get("experiment", ""),
                )
        return tracker

    def diff(self, previous: CoverageTracker) -> dict:
        """
        Compare coverage with a previous run.

        Useful for PR gates: "this change must not decrease coverage."
        """
        prev_tested = previous.tested_ids
        curr_tested = self.tested_ids

        return {
            "new_coverage": sorted(curr_tested - prev_tested),
            "lost_coverage": sorted(prev_tested - curr_tested),
            "coverage_delta": self.coverage_percent() - previous.coverage_percent(),
            "resilience_delta": self.resilience_score() - previous.resilience_score(),
        }
