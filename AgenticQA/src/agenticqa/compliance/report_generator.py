"""Compliance report generator — one-click audit-ready reports.

Generates structured compliance reports from AgenticQA scan data,
suitable for SOC2, HIPAA, and EU AI Act auditors.

Output formats:
  - Markdown (default, human-readable)
  - JSON (machine-readable)
  - HTML (for PDF conversion via browser print)
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional


@dataclass
class ComplianceReportSection:
    """One section of a compliance report."""
    title: str
    status: str  # "pass" | "fail" | "partial" | "not_applicable"
    findings_count: int = 0
    critical_count: int = 0
    details: list = field(default_factory=list)
    recommendations: list = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "title": self.title,
            "status": self.status,
            "findings_count": self.findings_count,
            "critical_count": self.critical_count,
            "details": self.details,
            "recommendations": self.recommendations,
        }


@dataclass
class ComplianceReport:
    """Full compliance report."""
    repo_id: str
    generated_at: str
    scan_summary: dict
    sections: list = field(default_factory=list)
    overall_score: float = 0.0
    overall_status: str = "unknown"

    def to_dict(self) -> dict:
        return {
            "repo_id": self.repo_id,
            "generated_at": self.generated_at,
            "overall_score": self.overall_score,
            "overall_status": self.overall_status,
            "scan_summary": self.scan_summary,
            "sections": [s.to_dict() for s in self.sections],
        }


class ComplianceReportGenerator:
    """Generate compliance reports from scan results."""

    def generate(
        self,
        scan_output: dict,
        repo_id: str = "",
        frameworks: Optional[list[str]] = None,
    ) -> ComplianceReport:
        """Generate a compliance report from scan results.

        Args:
            scan_output: Output from scan_repo() or GitHub Action
            repo_id: Repository identifier
            frameworks: Compliance frameworks to include (default: all detected)
        """
        summary = scan_output.get("summary", {})
        scanners = scan_output.get("scanners", {})
        frameworks = frameworks or ["hipaa", "eu_ai_act", "security", "supply_chain"]

        report = ComplianceReport(
            repo_id=repo_id or summary.get("repo_path", "unknown"),
            generated_at=datetime.now(timezone.utc).isoformat(),
            scan_summary={
                "total_findings": summary.get("total_findings", 0),
                "total_critical": summary.get("total_critical", 0),
                "risk_level": summary.get("risk_level", "unknown"),
                "scanners_ok": summary.get("scanners_ok", 0),
            },
        )

        # Build sections based on scanner results
        if "hipaa" in frameworks:
            report.sections.append(self._hipaa_section(scanners))
        if "eu_ai_act" in frameworks:
            report.sections.append(self._eu_ai_act_section(scanners))
        if "security" in frameworks:
            report.sections.append(self._security_section(scanners))
        if "supply_chain" in frameworks:
            report.sections.append(self._supply_chain_section(scanners))

        # Calculate overall score
        if report.sections:
            scores = {"pass": 1.0, "partial": 0.5, "fail": 0.0, "not_applicable": None}
            scored = [scores.get(s.status) for s in report.sections if scores.get(s.status) is not None]
            report.overall_score = round(sum(scored) / len(scored), 2) if scored else 0
            report.overall_status = (
                "compliant" if report.overall_score >= 0.8
                else "partially_compliant" if report.overall_score >= 0.5
                else "non_compliant"
            )

        return report

    def to_markdown(self, report: ComplianceReport) -> str:
        """Render report as markdown."""
        status_icon = {
            "compliant": "✅", "partially_compliant": "⚠️", "non_compliant": "❌"
        }.get(report.overall_status, "❓")

        lines = [
            "# AgenticQA Compliance Report",
            "",
            f"**Repository**: `{report.repo_id}`",
            f"**Generated**: {report.generated_at}",
            f"**Overall Status**: {status_icon} {report.overall_status.replace('_', ' ').title()}",
            f"**Compliance Score**: {report.overall_score:.0%}",
            "",
            "---",
            "",
            "## Executive Summary",
            "",
            f"| Metric | Value |",
            f"|--------|-------|",
            f"| Total Findings | {report.scan_summary.get('total_findings', 0)} |",
            f"| Critical Findings | {report.scan_summary.get('total_critical', 0)} |",
            f"| Risk Level | {report.scan_summary.get('risk_level', 'unknown').upper()} |",
            f"| Scanners Passed | {report.scan_summary.get('scanners_ok', 0)} |",
            "",
        ]

        for section in report.sections:
            icon = {"pass": "✅", "fail": "❌", "partial": "⚠️", "not_applicable": "➖"}.get(section.status, "❓")
            lines += [
                f"## {icon} {section.title}",
                "",
                f"**Status**: {section.status.replace('_', ' ').title()}",
                f"**Findings**: {section.findings_count} ({section.critical_count} critical)",
                "",
            ]

            if section.details:
                lines.append("### Findings")
                lines.append("")
                for detail in section.details[:20]:
                    lines.append(f"- {detail}")
                lines.append("")

            if section.recommendations:
                lines.append("### Recommendations")
                lines.append("")
                for rec in section.recommendations:
                    lines.append(f"- {rec}")
                lines.append("")

            lines.append("---")
            lines.append("")

        lines += [
            "## Methodology",
            "",
            "This report was generated by AgenticQA's automated compliance scanning engine.",
            "Scanners used: architecture analysis, legal risk, HIPAA PHI, EU AI Act,",
            "CVE reachability, AI model SBOM, prompt injection, agent trust graph,",
            "MCP security, data flow tracing, shadow AI detection, bias detection,",
            "and indirect injection guard.",
            "",
            "---",
            "*Generated by [AgenticQA](https://github.com/nhomyk/AgenticQA)*",
        ]

        return "\n".join(lines)

    def to_html(self, report: ComplianceReport) -> str:
        """Render report as HTML (for PDF printing)."""
        md = self.to_markdown(report)
        # Simple markdown→HTML conversion for the report
        html_lines = [
            "<!DOCTYPE html>",
            "<html><head>",
            "<meta charset='utf-8'>",
            "<title>AgenticQA Compliance Report</title>",
            "<style>",
            "body { font-family: -apple-system, sans-serif; max-width: 800px; margin: 40px auto; padding: 20px; }",
            "table { border-collapse: collapse; width: 100%; margin: 16px 0; }",
            "th, td { border: 1px solid #ddd; padding: 8px; text-align: left; }",
            "th { background: #f5f5f5; }",
            "h1 { color: #1a1a1a; border-bottom: 2px solid #6b46c1; padding-bottom: 8px; }",
            "h2 { color: #2d2d2d; margin-top: 32px; }",
            "hr { border: none; border-top: 1px solid #eee; margin: 24px 0; }",
            "code { background: #f5f5f5; padding: 2px 6px; border-radius: 3px; }",
            ".status-pass { color: #22c55e; } .status-fail { color: #ef4444; }",
            ".status-partial { color: #f59e0b; }",
            "@media print { body { margin: 0; } }",
            "</style>",
            "</head><body>",
        ]

        # Convert markdown to basic HTML
        for line in md.split("\n"):
            if line.startswith("# "):
                html_lines.append(f"<h1>{line[2:]}</h1>")
            elif line.startswith("## "):
                html_lines.append(f"<h2>{line[3:]}</h2>")
            elif line.startswith("### "):
                html_lines.append(f"<h3>{line[4:]}</h3>")
            elif line.startswith("| ") and "---" not in line:
                cells = [c.strip() for c in line.split("|")[1:-1]]
                tag = "th" if "Metric" in cells or "-----" in line else "td"
                row = "".join(f"<{tag}>{c}</{tag}>" for c in cells)
                html_lines.append(f"<tr>{row}</tr>")
            elif line.startswith("|---"):
                continue  # Skip markdown table separator
            elif line.startswith("- "):
                html_lines.append(f"<li>{line[2:]}</li>")
            elif line.startswith("**") and line.endswith("**"):
                html_lines.append(f"<p><strong>{line[2:-2]}</strong></p>")
            elif line.startswith("---"):
                html_lines.append("<hr>")
            elif line.strip():
                # Handle inline formatting
                formatted = line.replace("**", "<strong>", 1).replace("**", "</strong>", 1)
                formatted = formatted.replace("`", "<code>", 1).replace("`", "</code>", 1)
                html_lines.append(f"<p>{formatted}</p>")

        html_lines += ["</body></html>"]
        return "\n".join(html_lines)

    # ── Section builders ────────────────────────────────────────────────

    def _hipaa_section(self, scanners: dict) -> ComplianceReportSection:
        hipaa = scanners.get("hipaa", {})
        if hipaa.get("status") != "ok":
            return ComplianceReportSection(
                title="HIPAA / PHI Protection",
                status="not_applicable",
            )

        r = hipaa["result"]
        findings = r.get("total_findings", 0)
        critical = r.get("critical", 0)
        status = "pass" if critical == 0 and findings == 0 else ("fail" if critical > 0 else "partial")

        recs = []
        if critical > 0:
            recs.append("Immediately address critical PHI exposure findings")
        if findings > 0:
            recs.append("Review PHI handling practices against HIPAA §164.312")
            recs.append("Implement encryption at rest and in transit for all PHI")

        return ComplianceReportSection(
            title="HIPAA / PHI Protection",
            status=status,
            findings_count=findings,
            critical_count=critical,
            details=[
                f"Risk score: {r.get('risk_score', 0):.2f}",
                f"PHI findings: {findings} ({critical} critical)",
            ],
            recommendations=recs,
        )

    def _eu_ai_act_section(self, scanners: dict) -> ComplianceReportSection:
        ai_act = scanners.get("ai_act", {})
        if ai_act.get("status") != "ok":
            return ComplianceReportSection(
                title="EU AI Act Compliance",
                status="not_applicable",
            )

        r = ai_act["result"]
        score = r.get("conformity_score", 0)
        risk_cat = r.get("risk_category", "unknown")
        missing = r.get("missing", 0)
        status = "pass" if score >= 0.7 else ("partial" if score >= 0.4 else "fail")

        recs = []
        if missing > 0:
            recs.append(f"Address {missing} missing compliance controls")
        if risk_cat == "high_risk":
            recs.append("Implement Art.9 risk management system")
            recs.append("Ensure Art.13 transparency requirements are met")
            recs.append("Establish Art.14 human oversight mechanisms")
        if score < 0.7:
            recs.append("Review EU AI Act obligations timeline for deadlines")

        return ComplianceReportSection(
            title="EU AI Act Compliance",
            status=status,
            findings_count=r.get("findings_count", 0),
            critical_count=missing,
            details=[
                f"Risk category: {risk_cat}",
                f"Conformity score: {score:.0%}",
                f"Annex III high-risk: {'Yes' if r.get('annex_iii') else 'No'}",
                f"Missing controls: {missing}",
            ],
            recommendations=recs,
        )

    def _security_section(self, scanners: dict) -> ComplianceReportSection:
        details = []
        total_findings = 0
        total_critical = 0
        recs = []

        # Architecture
        arch = scanners.get("architecture", {})
        if arch.get("status") == "ok":
            r = arch["result"]
            total_findings += r.get("total_findings", 0)
            total_critical += r.get("critical_count", 0)
            details.append(f"Architecture: {r.get('total_findings', 0)} integration points, "
                           f"attack surface score {r.get('attack_surface_score', 0):.0f}/100")

        # Prompt injection
        pi = scanners.get("prompt_injection", {})
        if pi.get("status") == "ok":
            r = pi["result"]
            total_findings += r.get("total_findings", 0)
            total_critical += r.get("critical", 0)
            if r.get("critical", 0) > 0:
                details.append(f"Prompt injection: {r.get('critical', 0)} critical vulnerabilities")
                recs.append("Sanitize all user inputs before passing to LLM prompts")

        # Legal risk
        legal = scanners.get("legal_risk", {})
        if legal.get("status") == "ok":
            r = legal["result"]
            total_findings += r.get("total_findings", 0)
            total_critical += r.get("critical", 0)
            if r.get("critical", 0) > 0:
                recs.append("Address hardcoded credentials and PII exposure")

        # Trust graph
        trust = scanners.get("trust_graph", {})
        if trust.get("status") == "ok":
            r = trust["result"]
            if r.get("has_cycles"):
                details.append("Agent trust graph: circular delegation detected")
                recs.append("Break circular trust chains between agents")
                total_critical += 1

        status = "pass" if total_critical == 0 else ("fail" if total_critical > 3 else "partial")

        return ComplianceReportSection(
            title="Security Posture",
            status=status,
            findings_count=total_findings,
            critical_count=total_critical,
            details=details,
            recommendations=recs,
        )

    def _supply_chain_section(self, scanners: dict) -> ComplianceReportSection:
        details = []
        total_findings = 0
        total_critical = 0
        recs = []

        # AI Model SBOM
        sbom = scanners.get("ai_model_sbom", {})
        if sbom.get("status") == "ok":
            r = sbom["result"]
            details.append(f"AI providers: {', '.join(r.get('providers', []))}")
            details.append(f"Unique models: {r.get('unique_models', 0)}")
            violations = r.get("license_violations", 0)
            total_findings += violations
            if violations > 0:
                total_critical += violations
                recs.append("Review AI model licenses for commercial use compliance")

        # Shadow AI
        shadow = scanners.get("shadow_ai", {})
        if shadow.get("status") == "ok":
            r = shadow["result"]
            if r.get("has_shadow_ai"):
                providers = r.get("providers_found", [])
                details.append(f"Shadow AI detected: {', '.join(providers)}")
                total_findings += r.get("total_findings", 0)
                recs.append("Register all AI API calls through approved gateway")

        # CVE reachability
        cve = scanners.get("cve_reachability", {})
        if cve.get("status") == "ok":
            r = cve["result"]
            reachable = r.get("python_reachable", 0) + r.get("js_reachable", 0)
            if reachable > 0:
                details.append(f"Reachable CVEs: {reachable}")
                total_critical += reachable
                recs.append("Update dependencies with known reachable CVEs")

        status = "pass" if total_critical == 0 else ("fail" if total_critical > 2 else "partial")

        return ComplianceReportSection(
            title="Supply Chain & AI Governance",
            status=status,
            findings_count=total_findings,
            critical_count=total_critical,
            details=details,
            recommendations=recs,
        )
