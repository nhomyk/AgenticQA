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
import shutil
import subprocess
import tempfile
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

    def to_html(self) -> str:
        return _render_html(self)


def clone_github_repo(url_or_slug: str, dest: Optional[Path] = None) -> Path:
    """Shallow-clone a GitHub repo and return the local path.

    Accepts:
      - Full URL: ``https://github.com/owner/repo``
      - Slug:     ``owner/repo``

    The clone is ``--depth 1`` to minimise bandwidth.  If *dest* is None a
    temporary directory is created (caller is responsible for cleanup).
    """
    if "/" in url_or_slug and not url_or_slug.startswith(("http://", "https://")):
        url = f"https://github.com/{url_or_slug}.git"
    else:
        url = url_or_slug
        if not url.endswith(".git"):
            url = url + ".git"

    if dest is None:
        dest = Path(tempfile.mkdtemp(prefix="agenticqa_"))

    subprocess.run(
        ["git", "clone", "--depth", "1", url, str(dest)],
        check=True,
        capture_output=True,
        timeout=120,
    )
    return dest


def _is_github_ref(path: str) -> bool:
    """Return True if *path* looks like a GitHub URL or owner/repo slug."""
    if path.startswith(("https://github.com/", "http://github.com/")):
        return True
    # owner/repo pattern (exactly one slash, no dots or spaces)
    parts = path.split("/")
    if len(parts) == 2 and all(p and " " not in p and "." not in p for p in parts):
        return True
    return False


class ReportGenerator:
    """Orchestrates multi-repo scanning and report generation."""

    def scan_repos(self, repo_paths: List[str]) -> ScanReport:
        """Scan multiple repos and return a ScanReport.

        Each entry in *repo_paths* may be a local path, a GitHub URL
        (``https://github.com/owner/repo``), or a GitHub slug
        (``owner/repo``).  Remote repos are shallow-cloned into a temp
        directory and cleaned up after scanning.
        """
        report = ScanReport(
            generated_at=datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC"),
        )
        t0 = time.time()

        for rpath in repo_paths:
            clone_dir: Optional[Path] = None
            try:
                if _is_github_ref(rpath):
                    clone_dir = clone_github_repo(rpath)
                    resolved = clone_dir
                else:
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
                # For GitHub repos, store the original ref as the path label
                if clone_dir is not None:
                    repo_result.repo_path = rpath
                report.repos.append(repo_result)
            except subprocess.CalledProcessError as exc:
                repo_result = RepoScanResult(
                    repo_path=rpath,
                    repo_name=rpath.rsplit("/", 1)[-1] if "/" in rpath else rpath,
                )
                stderr = exc.stderr.decode("utf-8", errors="replace") if exc.stderr else str(exc)
                repo_result.scanners["_clone_error"] = {
                    "status": "error",
                    "error": f"Failed to clone: {stderr[:200]}",
                }
                report.repos.append(repo_result)
            finally:
                if clone_dir is not None and clone_dir.exists():
                    shutil.rmtree(clone_dir, ignore_errors=True)

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
                    f"**Shadow AI:** Undeclared AI usage detected  - {', '.join(providers)}"
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
                        f"surface(s)  - user input flows directly into LLM prompts."
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


# ---------------------------------------------------------------------------
# HTML rendering (self-contained, inline Plotly CDN)
# ---------------------------------------------------------------------------

_PLOTLY_CDN = "https://cdn.plot.ly/plotly-2.35.0.min.js"


def _render_html(report: ScanReport) -> str:
    """Generate a self-contained HTML report with inline Plotly charts."""
    total_findings = sum(r.total_findings for r in report.repos)
    total_critical = sum(r.total_critical for r in report.repos)
    risk = _risk_label(total_critical, total_findings)

    # Build data for charts
    repo_names = [r.repo_name for r in report.repos]
    repo_findings = [r.total_findings for r in report.repos]
    repo_critical = [r.total_critical for r in report.repos]

    # Scanner breakdown across all repos
    scanner_totals: Dict[str, int] = {}
    for r in report.repos:
        for sname, data in r.scanners.items():
            if sname.startswith("_") or data.get("status") != "ok":
                continue
            result = data.get("result", {})
            count = result.get("total_findings", result.get("findings_count", 0))
            scanner_totals[sname] = scanner_totals.get(sname, 0) + count

    scanner_names_sorted = sorted(scanner_totals.keys(), key=lambda k: scanner_totals[k], reverse=True)
    scanner_counts = [scanner_totals[s] for s in scanner_names_sorted]

    # Per-repo scanner table rows
    table_rows = ""
    for r in report.repos:
        for sname, data in r.scanners.items():
            if sname.startswith("_"):
                continue
            status = data.get("status", "unknown")
            if status == "ok":
                result = data.get("result", {})
                findings = result.get("total_findings", result.get("findings_count", 0))
                crit = result.get("critical", 0)
                detail = _scanner_detail(sname, result)
                status_badge = '<span class="badge ok">OK</span>'
            else:
                findings = "-"
                crit = "-"
                detail = (data.get("error", "Unknown error"))[:80]
                status_badge = '<span class="badge fail">FAIL</span>'
            table_rows += (
                f"<tr><td>{r.repo_name}</td><td>{sname}</td>"
                f"<td>{status_badge}</td><td>{findings}</td>"
                f"<td>{crit}</td><td>{detail}</td></tr>\n"
            )

    # Recommendations
    recommendations = _generate_recommendations(report)
    recs_html = ""
    if recommendations:
        recs_items = "".join(f"<li>{rec}</li>" for rec in recommendations)
        recs_html = f"<h2>Recommendations</h2><ol>{recs_items}</ol>"

    risk_color = {
        "CRITICAL": "#dc3545",
        "HIGH": "#fd7e14",
        "MEDIUM": "#ffc107",
        "LOW": "#28a745",
    }.get(risk, "#6c757d")

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>AgenticQA Security Scan Report</title>
<script src="{_PLOTLY_CDN}"></script>
<style>
  * {{ margin: 0; padding: 0; box-sizing: border-box; }}
  body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
         background: #f8f9fa; color: #212529; padding: 2rem; }}
  .container {{ max-width: 1200px; margin: 0 auto; }}
  h1 {{ font-size: 1.8rem; margin-bottom: 0.5rem; }}
  h2 {{ font-size: 1.4rem; margin: 2rem 0 1rem; border-bottom: 2px solid #dee2e6; padding-bottom: 0.5rem; }}
  .meta {{ color: #6c757d; margin-bottom: 1.5rem; }}
  .summary-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 1rem; margin-bottom: 2rem; }}
  .summary-card {{ background: #fff; border-radius: 8px; padding: 1.5rem; box-shadow: 0 1px 3px rgba(0,0,0,0.1); text-align: center; }}
  .summary-card .value {{ font-size: 2rem; font-weight: 700; }}
  .summary-card .label {{ color: #6c757d; font-size: 0.85rem; text-transform: uppercase; letter-spacing: 0.05em; }}
  .charts {{ display: grid; grid-template-columns: 1fr 1fr; gap: 1.5rem; margin-bottom: 2rem; }}
  .chart-box {{ background: #fff; border-radius: 8px; padding: 1rem; box-shadow: 0 1px 3px rgba(0,0,0,0.1); }}
  table {{ width: 100%; border-collapse: collapse; background: #fff; border-radius: 8px; overflow: hidden;
           box-shadow: 0 1px 3px rgba(0,0,0,0.1); margin-bottom: 2rem; }}
  th {{ background: #343a40; color: #fff; padding: 0.75rem; text-align: left; font-size: 0.85rem;
       text-transform: uppercase; letter-spacing: 0.05em; }}
  td {{ padding: 0.65rem 0.75rem; border-bottom: 1px solid #dee2e6; font-size: 0.9rem; }}
  tr:hover {{ background: #f1f3f5; }}
  .badge {{ display: inline-block; padding: 0.2em 0.6em; border-radius: 4px; font-size: 0.75rem; font-weight: 600; }}
  .badge.ok {{ background: #d4edda; color: #155724; }}
  .badge.fail {{ background: #f8d7da; color: #721c24; }}
  ol {{ padding-left: 1.5rem; }}
  li {{ margin-bottom: 0.5rem; line-height: 1.5; }}
  .footer {{ margin-top: 2rem; padding-top: 1rem; border-top: 1px solid #dee2e6; color: #6c757d; font-size: 0.8rem; }}
  @media (max-width: 768px) {{ .charts {{ grid-template-columns: 1fr; }} }}
</style>
</head>
<body>
<div class="container">
  <h1>AgenticQA Security Scan Report</h1>
  <p class="meta">Generated {report.generated_at} | Scan time: {report.total_elapsed_s}s</p>

  <div class="summary-grid">
    <div class="summary-card">
      <div class="value">{len(report.repos)}</div>
      <div class="label">Repositories</div>
    </div>
    <div class="summary-card">
      <div class="value">{total_findings}</div>
      <div class="label">Total Findings</div>
    </div>
    <div class="summary-card">
      <div class="value">{total_critical}</div>
      <div class="label">Critical</div>
    </div>
    <div class="summary-card">
      <div class="value" style="color:{risk_color}">{risk}</div>
      <div class="label">Overall Risk</div>
    </div>
  </div>

  <div class="charts">
    <div class="chart-box"><div id="chart-repos"></div></div>
    <div class="chart-box"><div id="chart-scanners"></div></div>
  </div>

  <h2>Scanner Results</h2>
  <table>
    <thead>
      <tr><th>Repository</th><th>Scanner</th><th>Status</th><th>Findings</th><th>Critical</th><th>Details</th></tr>
    </thead>
    <tbody>
      {table_rows}
    </tbody>
  </table>

  {recs_html}

  <h2>Methodology</h2>
  <p>All scans were performed via static analysis. No code was executed, no network requests were made
     to scanned services, no credentials were accessed or tested, and no vulnerabilities were exploited.</p>

  <p class="footer">Generated by <a href="https://github.com/nhomyk/AgenticQA">AgenticQA</a> - Multi-agent quality and security platform.</p>
</div>

<script>
Plotly.newPlot('chart-repos', [
  {{ x: {json.dumps(repo_names)}, y: {json.dumps(repo_findings)}, name: 'Findings', type: 'bar', marker: {{ color: '#4c6ef5' }} }},
  {{ x: {json.dumps(repo_names)}, y: {json.dumps(repo_critical)}, name: 'Critical', type: 'bar', marker: {{ color: '#dc3545' }} }}
], {{
  title: 'Findings by Repository',
  barmode: 'group',
  paper_bgcolor: 'rgba(0,0,0,0)',
  plot_bgcolor: 'rgba(0,0,0,0)',
  margin: {{ t: 40, b: 40, l: 40, r: 20 }},
  font: {{ family: '-apple-system, sans-serif', size: 12 }}
}}, {{ responsive: true }});

Plotly.newPlot('chart-scanners', [{{
  labels: {json.dumps(scanner_names_sorted)},
  values: {json.dumps(scanner_counts)},
  type: 'pie',
  hole: 0.4,
  textinfo: 'label+value',
  marker: {{ colors: ['#4c6ef5','#dc3545','#fd7e14','#ffc107','#28a745','#6f42c1','#20c997','#e83e8c','#17a2b8','#6c757d','#343a40','#adb5bd','#868e96','#495057'] }}
}}], {{
  title: 'Findings by Scanner',
  paper_bgcolor: 'rgba(0,0,0,0)',
  margin: {{ t: 40, b: 20, l: 20, r: 20 }},
  font: {{ family: '-apple-system, sans-serif', size: 11 }},
  showlegend: false
}}, {{ responsive: true }});
</script>
</body>
</html>"""
