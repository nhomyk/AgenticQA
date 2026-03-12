"""
K8s Failure Taxonomy — Structured registry of all known failure scenarios.

INTERVIEW CONCEPT: Kubernetes failure modes are finite and enumerable.
This module loads them from YAML, tags them, and provides filtering so you
can answer "what percentage of K8s failure modes does our test suite cover?"

Usage:
    taxonomy = FailureTaxonomy.load()                    # load default YAML
    taxonomy = FailureTaxonomy.load("custom.yaml")       # load custom catalog

    # Filter
    critical = taxonomy.filter(severity="critical")
    net = taxonomy.filter(category="network")
    tier1 = taxonomy.filter(tier=1)

    # Coverage
    tracker = CoverageTracker(taxonomy)
    tracker.record("POD-001", passed=True)
    report = tracker.report()
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import yaml


@dataclass(frozen=True)
class Scenario:
    """A single K8s failure scenario from the taxonomy."""

    id: str
    name: str
    category: str
    severity: str
    k8s_concept: str
    description: str
    detection: str
    test_method: str
    variants: list[str] = field(default_factory=list)
    tier: int = 1

    @property
    def severity_rank(self) -> int:
        """Numeric severity for sorting (lower = more severe)."""
        return {"critical": 0, "high": 1, "medium": 2, "low": 3}.get(
            self.severity, 4
        )


class FailureTaxonomy:
    """
    Registry of all K8s failure scenarios.

    Loads from YAML, provides filtering, iteration, and summary statistics.
    The taxonomy is the single source of truth for what "full coverage" means.
    """

    def __init__(self, scenarios: list[Scenario]) -> None:
        self._scenarios = scenarios
        self._by_id: dict[str, Scenario] = {s.id: s for s in scenarios}
        self._by_category: dict[str, list[Scenario]] = {}
        for s in scenarios:
            self._by_category.setdefault(s.category, []).append(s)

    @classmethod
    def load(cls, path: Optional[str] = None) -> FailureTaxonomy:
        """Load taxonomy from YAML file. Defaults to bundled taxonomy.yaml."""
        if path is None:
            path = os.path.join(os.path.dirname(__file__), "taxonomy.yaml")
        with open(path) as f:
            data = yaml.safe_load(f)

        scenarios: list[Scenario] = []
        for cat_key, cat_data in data.get("categories", {}).items():
            for raw in cat_data.get("scenarios", []):
                scenarios.append(
                    Scenario(
                        id=raw["id"],
                        name=raw["name"],
                        category=cat_key,
                        severity=raw.get("severity", "medium"),
                        k8s_concept=raw.get("k8s_concept", ""),
                        description=raw.get("description", "").strip(),
                        detection=raw.get("detection", ""),
                        test_method=raw.get("test_method", ""),
                        variants=raw.get("variants", []),
                        tier=raw.get("tier", 1),
                    )
                )
        return cls(scenarios)

    def __len__(self) -> int:
        return len(self._scenarios)

    def __iter__(self):
        return iter(self._scenarios)

    def get(self, scenario_id: str) -> Optional[Scenario]:
        """Look up a scenario by ID (e.g., 'POD-001')."""
        return self._by_id.get(scenario_id)

    @property
    def categories(self) -> list[str]:
        """All category names in the taxonomy."""
        return list(self._by_category.keys())

    def filter(
        self,
        *,
        category: Optional[str] = None,
        severity: Optional[str] = None,
        tier: Optional[int] = None,
    ) -> list[Scenario]:
        """Filter scenarios by category, severity, and/or tier."""
        results = self._scenarios
        if category is not None:
            results = [s for s in results if s.category == category]
        if severity is not None:
            results = [s for s in results if s.severity == severity]
        if tier is not None:
            results = [s for s in results if s.tier == tier]
        return results

    def summary(self) -> dict:
        """
        Summary statistics for the full taxonomy.

        Returns dict with total count, per-category counts, per-severity counts,
        and total variant count (the "expanded" scenario count).
        """
        by_severity: dict[str, int] = {}
        by_category: dict[str, int] = {}
        total_variants = 0

        for s in self._scenarios:
            by_severity[s.severity] = by_severity.get(s.severity, 0) + 1
            by_category[s.category] = by_category.get(s.category, 0) + 1
            total_variants += len(s.variants)

        return {
            "total_scenarios": len(self._scenarios),
            "total_with_variants": len(self._scenarios) + total_variants,
            "by_category": by_category,
            "by_severity": by_severity,
        }

    def study_guide(self, category: Optional[str] = None) -> str:
        """
        Generate an interview study guide from the taxonomy.

        Each scenario includes the K8s concept, what to say in an interview,
        and how to detect/test it.
        """
        scenarios = (
            self._by_category.get(category, []) if category else self._scenarios
        )
        lines: list[str] = []
        current_cat = ""

        for s in sorted(scenarios, key=lambda x: (x.category, x.severity_rank)):
            if s.category != current_cat:
                current_cat = s.category
                lines.append(f"\n## {current_cat.upper().replace('_', ' ')}\n")
            lines.append(f"### {s.id}: {s.name} [{s.severity}]")
            lines.append(f"**K8s Concept:** {s.k8s_concept}")
            lines.append(f"**What happens:** {s.description}")
            lines.append(f"**How to detect:** {s.detection}")
            lines.append(f"**How to test:** {s.test_method}")
            if s.variants:
                lines.append("**Variants:**")
                for v in s.variants:
                    lines.append(f"  - {v}")
            lines.append("")

        return "\n".join(lines)
