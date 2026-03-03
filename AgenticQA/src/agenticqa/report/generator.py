"""
Multi-repo security scan → structured report generator.

Orchestrates all AgenticQA scanners against one or more repositories and
produces a professional markdown or JSON report.

Usage (programmatic):
    from agenticqa.report import ReportGenerator
    gen = ReportGenerator()
    report = gen.scan_repos(["/path/to/repo1", "/path/to/repo2"])
    print(report.to_markdown())

Usage (CLI):
    python -m agenticqa.report /path/to/repo1 /path/to/repo2 --output report.md
"""
from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional


@dataclass
class RepoScanResult:
    """Scan results for a single repository."""
    repo_path: str
    repo_name: str
    scanners: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    elapsed_s: float = 0.0

    @property
    def total_findings(self) -> int:
        total = 0
        for v in self.scanners.values():
            if v.get("status") == "ok":
                r = v.get("result", {})
                total += r.get("total_findings", r.get("findings_count", 0))
        return total

    @property
    def total_critical(self) -> int:
        total = 0
        for v in self.scanners.values():
            if v.get("status") == "ok":
                total += v.get("result", {}).get("critical", 0)
        return total

    @property
    def scanners_ok(self) -> int:
        return sum(1 for v in self.scanners.values() if v.get("status") == "ok")

    @property
    def scanners_failed(self) -> int:
        return sum(1 for v in self.scanners.values() if v.get("status") == "error")


@dataclass
class ScanReport:
    """Complete multi-repo scan report."""
    repos: List[RepoScanResult] = field(default_factory=list)
    generated_at: str = ""
    total_elapsed_s: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "generated_at": self.generated_at,
            "total_elapsed_s": self.total_elapsed_s,
            "repos": [
                {
                    "repo_path": r.repo_path,
                    "repo_name": r.repo_name,
                    "total_findings": r.total_findings,
                    "total_critical": r.total_critical,
                    "scanners_ok": r.scanners_ok,
                    "scanners_failed": r.scanners_failed,
                    "elapsed_s": r.elapsed_s,
                    "scanners": r.scanners,
                }
                for r in self.repos
            ],
        }

    def to_json(self, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent, default=str)

    def to_markdown(self) -> str:
        return _render_markdown(self)


class ReportGenerator:
    """Orchestrates multi-repo scanning and report generation."""

    def scan_repos(self, repo_paths: List[str]) -> ScanReport:
        """Scan multiple repos and return a ScanReport."""
        report = ScanReport(
            generated_at=datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC"),
        )
        t0 = time.time()

        for rpath in repo_paths:
            resolved = Path(rpath).resolve()
            if not resolved.exists():
                repo_result = RepoScanResult(
                    repo_path=str(resolved),
                    repo_name=resolved.name,
                )
                repo_result.scanners["_error"] = {
                    "status": "error",
                    "error": f"Path does not exist: {resolved}",
                }
                report.repos.append(repo_result)
                continue

            repo_result = self._scan_single_repo(str(resolved))
            report.repos.append(repo_result)

        report.total_elapsed_s = round(time.time() - t0, 2)
        return report

    def _scan_single_repo(self, repo_path: str) -> RepoScanResult:
        """Run all scanners against a single repo."""
        from scripts.run_client_scan import scan_repo

        name = Path(repo_path).name
        t0 = time.time()
        scanners = scan_repo(repo_path)
        elapsed = round(time.time() - t0, 2)

        return RepoScanResult(
            repo_path=repo_path,
            repo_name=name,
            scanners=scanners,
            elapsed_s=elapsed,
        )


# ---------------------------------------------------------------------------
# Markdown rendering
# ---------------------------------------------------------------------------

def _risk_label(critical: int, findings: int) -> str:
    if critical >= 10:
        return "CRITICAL"
    if critical >= 3:
        return "HIGH"
    if findings >= 50:
        return "MEDIUM"
    return "LOW"


def _render_markdown(report: ScanReport) -> str:
    lines: List[str] = []
    lines.append("# AgenticQA Security Scan Report")
    lines.append(f"**Generated:** {report.generated_at}")
    lines.append(f"**Scanner:** AgenticQA (14 scanners)")
    lines.append(f"**Total scan time:** {report.total_elapsed_s}s")
    lines.append("")
    lines.append("---")
    lines.append("")

    # Executive summary
    total_findings = sum(r.total_findings for r in report.repos)
    total_critical = sum(r.total_critical for r in report.repos)
    lines.append("## Executive Summary")
    lines.append("")
    lines.append(f"- **Repositories scanned:** {len(report.repos)}")
    lines.append(f"- **Total findings:** {total_findings}")
    lines.append(f"- **Critical findings:** {total_critical}")
    lines.append(f"- **Overall risk:** {_risk_label(total_critical, total_findings)}")
    lines.append("")

    # Highest-risk repo
    if report.repos:
        worst = max(report.repos, key=lambda r: (r.total_critical, r.total_findings))
        if worst.total_findings > 0:
            lines.append(
                f"**Highest-risk repository:** `{worst.repo_name}` "
                f"({worst.total_critical} critical, {worst.total_findings} total findings)"
            )
            lines.append("")

    lines.append("---")
    lines.append("")

    # Cross-repo comparison table
    lines.append("## Cross-Repository Comparison")
    lines.append("")
    lines.append("| Repository | Findings | Critical | Risk | Scanners OK | Time |")
    lines.append("|-----------|----------|----------|------|-------------|------|")
    for r in report.repos:
        risk = _risk_label(r.total_critical, r.total_findings)
        lines.append(
            f"| {r.repo_name} | {r.total_findings} | {r.total_critical} "
            f"| {risk} | {r.scanners_ok}/{r.scanners_ok + r.scanners_failed} "
            f"| {r.elapsed_s}s |"
        )
    lines.append("")
    lines.append("---")
    lines.append("")

    # Per-repo details
    for r in report.repos:
        lines.append(f"## {r.repo_name}")
        lines.append("")
        lines.append(f"**Path:** `{r.repo_path}`")
        lines.append(f"**Scan time:** {r.elapsed_s}s")
        lines.append("")

        lines.append("| Scanner | Status | Findings | Critical | Details |")
        lines.append("|---------|--------|----------|----------|---------|")

        for scanner_name, data in r.scanners.items():
            if scanner_name.startswith("_"):
                continue
            status = data.get("status", "unknown")
            if status == "ok":
                result = data.get("result", {})
                findings = result.get("total_findings", result.get("findings_count", "?"))
                crit = result.get("critical", 0)
                detail = _scanner_detail(scanner_name, result)
                lines.append(f"| {scanner_name} | OK | {findings} | {crit} | {detail} |")
            else:
                err = data.get("error", "Unknown error")[:80]
                lines.append(f"| {scanner_name} | FAIL | - | - | {err} |")

        lines.append("")

        # Add notable findings section for repos with findings
        notable = _get_notable_findings(r)
        if notable:
            lines.append("### Notable Findings")
            lines.append("")
            for note in notable:
                lines.append(f"- {note}")
            lines.append("")

        lines.append("---")
        lines.append("")

    # Recommendations
    recommendations = _generate_recommendations(report)
    if recommendations:
        lines.append("## Recommendations")
        lines.append("")
        for i, rec in enumerate(recommendations, 1):
            lines.append(f"{i}. {rec}")
        lines.append("")
        lines.append("---")
        lines.append("")

    # Methodology
    lines.append("## Methodology")
    lines.append("")
    lines.append(
        "All scans were performed via static analysis. No code was executed, "
        "no network requests were made to scanned services, no credentials were "
        "accessed or tested, and no vulnerabilities were exploited."
    )
    lines.append("")
    lines.append(
        "*Generated by [AgenticQA](https://github.com/nhomyk/AgenticQA) "
        "-- Multi-agent quality and security platform.*"
    )
    lines.append("")

    return "\n".join(lines)


def _scanner_detail(name: str, result: Dict[str, Any]) -> str:
    """Extract a short detail string for a scanner result."""
    if name == "architecture":
        score = result.get("attack_surface_score", "?")
        files = result.get("files_scanned", "?")
        return f"attack_surface={score}, files={files}"
    if name == "ai_act":
        cat = result.get("risk_category", "?")
        score = result.get("conformity_score", "?")
        return f"risk={cat}, conformity={score}"
    if name == "trust_graph":
        agents = result.get("agents", 0)
        cycles = result.get("has_cycles", False)
        return f"agents={agents}, cycles={cycles}"
    if name == "ai_model_sbom":
        providers = result.get("providers", [])
        models = result.get("unique_models", 0)
        return f"providers={providers}, models={models}"
    if name == "shadow_ai":
        has = result.get("has_shadow_ai", False)
        providers = result.get("providers_found", [])
        return f"shadow_ai={has}, providers={providers}"
    risk = result.get("risk_score", result.get("max_risk_score"))
    if risk is not None:
        return f"risk_score={risk}"
    return ""


def _get_notable_findings(repo: RepoScanResult) -> List[str]:
    """Extract notable findings from scanner results."""
    notes: List[str] = []

    for scanner_name, data in repo.scanners.items():
        if data.get("status") != "ok":
            continue
        result = data.get("result", {})

        if scanner_name == "architecture":
            score = result.get("attack_surface_score", 0)
            if score > 5:
                notes.append(
                    f"**Architecture:** Elevated attack surface score ({score}/100)"
                )
            untested = result.get("untested_count", 0)
            if untested > 0:
                notes.append(
                    f"**Architecture:** {untested} untested high-risk integration areas"
                )

        if scanner_name == "prompt_injection":
            crit = result.get("critical", 0)
            if crit > 0:
                notes.append(
                    f"**Prompt Injection:** {crit} critical prompt injection surfaces"
                )

        if scanner_name == "data_flow":
            risk = result.get("risk_score", 0)
            if risk > 0.5:
                notes.append(
                    f"**DataFlow:** High taint risk score ({risk})"
                )

        if scanner_name == "ai_act":
            cat = result.get("risk_category", "")
            missing = result.get("missing", 0)
            if cat == "high_risk" and missing > 0:
                notes.append(
                    f"**EU AI Act:** Classified as HIGH-RISK with {missing} missing requirement(s)"
                )

        if scanner_name == "shadow_ai":
            if result.get("has_shadow_ai"):
                providers = result.get("providers_found", [])
                notes.append(
                    f"**Shadow AI:** Undeclared AI usage detected — {', '.join(providers)}"
                )

    return notes


def _generate_recommendations(report: ScanReport) -> List[str]:
    """Generate actionable recommendations from scan results."""
    recs: List[str] = []

    for repo in report.repos:
        for scanner_name, data in repo.scanners.items():
            if data.get("status") != "ok":
                continue
            result = data.get("result", {})

            if scanner_name == "architecture":
                untested = result.get("untested_count", 0)
                if untested > 0:
                    recs.append(
                        f"**{repo.repo_name}:** Add tests for {untested} untested "
                        f"high-risk integration areas identified by the architecture scanner."
                    )

            if scanner_name == "prompt_injection":
                crit = result.get("critical", 0)
                if crit > 0:
                    recs.append(
                        f"**{repo.repo_name}:** Address {crit} critical prompt injection "
                        f"surface(s) — user input flows directly into LLM prompts."
                    )

            if scanner_name == "ai_act":
                missing = result.get("missing", 0)
                if missing > 0:
                    recs.append(
                        f"**{repo.repo_name}:** Address {missing} missing EU AI Act "
                        f"compliance requirement(s). Enforcement begins August 2026."
                    )

            if scanner_name == "shadow_ai":
                if result.get("has_shadow_ai"):
                    recs.append(
                        f"**{repo.repo_name}:** Audit undeclared AI provider usage. "
                        f"Consider adding an AI SBOM or vendor registry."
                    )

    return recs
