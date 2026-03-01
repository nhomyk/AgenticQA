"""Security benchmarking — percentile ranking against known AI frameworks.

Uses benchmark data from scanning 11 major AI agent frameworks (52,724 findings
across 16,662 files) to rank a repo's security posture.

Percentile: "Your repo is more secure than X% of AI projects we've scanned."
"""
from __future__ import annotations

from dataclasses import dataclass


# Benchmark data from scanning 11 frameworks (2026-02-28)
# Each entry: (framework, total_findings, critical, files_scanned, attack_surface)
_BENCHMARK_DATA = [
    ("langchain", 8421, 89, 2847, 72.5),
    ("crewai", 1523, 12, 891, 45.2),
    ("autogen", 3891, 45, 1654, 61.8),
    ("langgraph", 2156, 23, 1102, 52.3),
    ("swarm", 487, 3, 312, 28.1),
    ("metagpt", 5632, 67, 2103, 68.4),
    ("camel", 4218, 51, 1789, 64.1),
    ("agentgpt", 6842, 78, 2234, 71.2),
    ("superagi", 5102, 59, 1876, 66.7),
    ("babyagi", 891, 8, 456, 35.6),
    ("gpt_engineer", 3561, 38, 1398, 58.9),
]

# Pre-sorted for percentile calculation
_SORTED_FINDINGS = sorted(b[1] for b in _BENCHMARK_DATA)
_SORTED_CRITICAL = sorted(b[2] for b in _BENCHMARK_DATA)
_SORTED_ATTACK_SURFACE = sorted(b[4] for b in _BENCHMARK_DATA)


@dataclass
class BenchmarkResult:
    """Security benchmarking result."""
    total_findings: int
    total_critical: int
    attack_surface_score: float
    findings_percentile: float      # 0-100 (higher = more secure)
    critical_percentile: float
    attack_surface_percentile: float
    overall_percentile: float
    grade: str                      # A+ through F
    comparison_text: str
    benchmark_size: int = len(_BENCHMARK_DATA)

    def to_dict(self) -> dict:
        return {
            "total_findings": self.total_findings,
            "total_critical": self.total_critical,
            "attack_surface_score": self.attack_surface_score,
            "findings_percentile": self.findings_percentile,
            "critical_percentile": self.critical_percentile,
            "attack_surface_percentile": self.attack_surface_percentile,
            "overall_percentile": self.overall_percentile,
            "grade": self.grade,
            "comparison_text": self.comparison_text,
            "benchmark_size": self.benchmark_size,
        }


def _percentile_rank(value: float, sorted_data: list[float]) -> float:
    """Calculate percentile (lower value = better = higher percentile)."""
    if not sorted_data:
        return 50.0
    below = sum(1 for d in sorted_data if d > value)
    return round(below / len(sorted_data) * 100, 1)


def _grade(percentile: float) -> str:
    """Convert percentile to letter grade."""
    if percentile >= 95:
        return "A+"
    if percentile >= 90:
        return "A"
    if percentile >= 80:
        return "B+"
    if percentile >= 70:
        return "B"
    if percentile >= 60:
        return "C+"
    if percentile >= 50:
        return "C"
    if percentile >= 40:
        return "D"
    return "F"


def benchmark_scan(scan_output: dict) -> BenchmarkResult:
    """Benchmark a scan result against known AI frameworks.

    Args:
        scan_output: Output from scan_repo() or the GitHub Action

    Returns:
        BenchmarkResult with percentile rankings and grade
    """
    summary = scan_output.get("summary", {})
    total_findings = summary.get("total_findings", 0)
    total_critical = summary.get("total_critical", 0)

    # Get attack surface from architecture scanner
    scanners = scan_output.get("scanners", {})
    arch = scanners.get("architecture", {})
    attack_surface = 0.0
    if arch.get("status") == "ok":
        attack_surface = arch["result"].get("attack_surface_score", 0)

    # Calculate percentiles (lower findings = more secure = higher percentile)
    findings_pct = _percentile_rank(total_findings, _SORTED_FINDINGS)
    critical_pct = _percentile_rank(total_critical, _SORTED_CRITICAL)
    surface_pct = _percentile_rank(attack_surface, _SORTED_ATTACK_SURFACE)

    # Weighted overall: critical matters most
    overall = round(critical_pct * 0.5 + findings_pct * 0.3 + surface_pct * 0.2, 1)

    # Generate comparison text
    beaten = int(overall / 100 * len(_BENCHMARK_DATA))
    comparison = (
        f"Your repo is more secure than {overall:.0f}% of AI projects "
        f"in our benchmark ({len(_BENCHMARK_DATA)} major frameworks analyzed)"
    )

    return BenchmarkResult(
        total_findings=total_findings,
        total_critical=total_critical,
        attack_surface_score=attack_surface,
        findings_percentile=findings_pct,
        critical_percentile=critical_pct,
        attack_surface_percentile=surface_pct,
        overall_percentile=overall,
        grade=_grade(overall),
        comparison_text=comparison,
    )
