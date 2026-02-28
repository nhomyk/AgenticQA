"""
Repo Onboarder — First-Run Client Experience

When AgenticQA is pointed at a new repository, this module:

  Phase 1 — Learn architecture
    Runs ArchitectureScanner across all languages and maps every
    integration point (SHELL_EXEC, EXTERNAL_HTTP, DATABASE, …).

  Phase 2 — Security sweep
    Runs OWASP, Secrets, CVE Reachability, Legal Risk, HIPAA PHI,
    EU AI Act, and Prompt Injection scanners in parallel.

  Phase 3 — Coverage mapping
    Finds all source files and existing tests.
    Marks uncovered files that have high-risk integration points.

  Phase 4 — Test generation
    Uses FrontendTestGenerator to create tests for the top uncovered
    high-risk files (capped at MAX_GENERATED_FILES per run).

  Phase 5 — Baseline snapshot
    Saves the baseline to ~/.agenticqa/baselines/{repo_id}.json so
    future runs can compare and show improvement over time.

Output
------
    OnboardingReport — full baseline summary, all findings, generated tests,
                       and a baseline_delta if a previous snapshot exists.
"""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional

from agenticqa.onboarding.coverage_mapper import CoverageMap, CoverageMapper
from agenticqa.testing.frontend_test_generator import (
    FrontendTestGenerator,
    FrameworkDetector,
)

MAX_GENERATED_FILES = 10   # cap test generation per onboarding run


# ── Dataclasses ────────────────────────────────────────────────────────────────

@dataclass
class GeneratedTestSummary:
    source_file: str
    test_file: str
    framework: str
    test_runner: str
    setup_instructions: List[str]
    status: str = "generated"   # "generated" | "failed"
    error: str = ""


@dataclass
class BaselineDelta:
    """Comparison against a previous onboarding snapshot."""
    previous_date: str
    attack_surface_change: float       # positive = worse
    coverage_change: float             # positive = better
    vulnerability_change: int          # positive = more found (worse)
    trend: str                         # "improving" | "stable" | "declining"


@dataclass
class OnboardingReport:
    repo_path: str
    repo_name: str
    timestamp: str

    # Architecture
    architecture: dict                         # ArchitectureScanResult.to_dict()
    attack_surface_score: float

    # Vulnerabilities
    owasp_findings: List[dict]
    secret_findings: List[dict]
    cve_findings: List[dict]
    legal_findings: List[dict]
    hipaa_findings: List[dict]
    eu_ai_act: dict
    prompt_injection_findings: List[dict]
    total_vulnerabilities: int

    # Coverage
    coverage: CoverageMap

    # Generated tests
    generated_tests: List[GeneratedTestSummary] = field(default_factory=list)

    # Baseline
    baseline_stored: bool = False
    baseline_delta: Optional[BaselineDelta] = None
    repo_id: str = ""

    # PR
    pr_url: str = ""

    @property
    def overall_risk(self) -> str:
        if self.attack_surface_score >= 60 or self.total_vulnerabilities >= 10:
            return "HIGH"
        if self.attack_surface_score >= 30 or self.total_vulnerabilities >= 3:
            return "MEDIUM"
        return "LOW"

    def to_dict(self) -> dict:
        return {
            "repo_path": self.repo_path,
            "repo_name": self.repo_name,
            "timestamp": self.timestamp,
            "overall_risk": self.overall_risk,
            "attack_surface_score": self.attack_surface_score,
            "total_vulnerabilities": self.total_vulnerabilities,
            "coverage": self.coverage.to_dict(),
            "generated_tests_count": len(self.generated_tests),
            "generated_tests": [
                {
                    "source_file": t.source_file,
                    "test_file": t.test_file,
                    "framework": t.framework,
                    "test_runner": t.test_runner,
                    "status": t.status,
                    "setup_instructions": t.setup_instructions,
                }
                for t in self.generated_tests
            ],
            "architecture": self.architecture,
            "owasp_count": len(self.owasp_findings),
            "secret_count": len(self.secret_findings),
            "cve_count": len(self.cve_findings),
            "legal_count": len(self.legal_findings),
            "hipaa_count": len(self.hipaa_findings),
            "prompt_injection_count": len(self.prompt_injection_findings),
            "eu_ai_act": self.eu_ai_act,
            "baseline_stored": self.baseline_stored,
            "baseline_delta": (
                {
                    "previous_date": self.baseline_delta.previous_date,
                    "attack_surface_change": self.baseline_delta.attack_surface_change,
                    "coverage_change": self.baseline_delta.coverage_change,
                    "vulnerability_change": self.baseline_delta.vulnerability_change,
                    "trend": self.baseline_delta.trend,
                }
                if self.baseline_delta else None
            ),
            "repo_id": self.repo_id,
            "pr_url": self.pr_url,
        }

    def plain_english_summary(self) -> str:
        lines = [
            f"AgenticQA Onboarding Report — {self.repo_name}",
            f"Scanned: {self.timestamp[:10]}",
            "=" * 60,
            "",
            f"Overall Risk:           {self.overall_risk}",
            f"Attack Surface Score:   {self.attack_surface_score:.0f}/100",
            f"Total Vulnerabilities:  {self.total_vulnerabilities}",
            f"  OWASP findings:       {len(self.owasp_findings)}",
            f"  Secrets detected:     {len(self.secret_findings)}",
            f"  CVE reachability:     {len(self.cve_findings)}",
            f"  Legal/Privacy risks:  {len(self.legal_findings)}",
            f"  HIPAA PHI issues:     {len(self.hipaa_findings)}",
            f"  Prompt injection:     {len(self.prompt_injection_findings)}",
            "",
            f"Test Coverage:          {self.coverage.coverage_pct}%",
            f"  Source files:         {self.coverage.total_source_files}",
            f"  Files with tests:     {len(self.coverage.covered_files)}",
            f"  Untested files:       {len(self.coverage.uncovered_files)}",
            f"  High-risk untested:   {len(self.coverage.high_risk_uncovered)}",
            "",
            f"Tests Generated:        {len(self.generated_tests)}",
        ]
        for t in self.generated_tests:
            lines.append(f"  {t.source_file} → {t.test_file} ({t.framework})")

        if self.baseline_delta:
            d = self.baseline_delta
            lines += [
                "",
                f"Since Last Scan ({d.previous_date[:10]}):  {d.trend.upper()}",
                f"  Attack surface:  {d.attack_surface_change:+.0f}",
                f"  Coverage:        {d.coverage_change:+.1f}%",
                f"  Vulnerabilities: {d.vulnerability_change:+d}",
            ]

        if self.pr_url:
            lines += ["", f"PR with generated tests: {self.pr_url}"]

        return "\n".join(lines)


# ── Onboarder ──────────────────────────────────────────────────────────────────

class RepoOnboarder:
    """Orchestrate a complete first-run scan of a new client repository."""

    def run(
        self,
        repo_path: str,
        github_token: str = "",
        github_repo: str = "",
        create_pr: bool = False,
        max_generated: int = MAX_GENERATED_FILES,
    ) -> OnboardingReport:
        root = Path(repo_path).resolve()
        repo_name = root.name
        timestamp = datetime.now(tz=timezone.utc).isoformat()
        repo_id = self._repo_id(root)

        # ── Phase 1: Architecture ──────────────────────────────────────────────
        arch_result = self._run_architecture(str(root))

        # ── Phase 2: Security sweeps ───────────────────────────────────────────
        owasp = self._run_owasp(str(root))
        secrets = self._run_secrets(str(root))
        cve = self._run_cve(str(root))
        legal = self._run_legal(str(root))
        hipaa = self._run_hipaa(str(root))
        eu_act = self._run_eu_ai_act(str(root))
        prompt_inj = self._run_prompt_injection(str(root))

        total_vulns = (
            len(owasp) + len(secrets) + len(cve) +
            len(legal) + len(hipaa) + len(prompt_inj)
        )

        # ── Phase 3: Coverage mapping ──────────────────────────────────────────
        cov_map = CoverageMapper().scan(str(root))

        # Tag uncovered files that the architecture scanner flagged as risky
        arch_files = {
            a["source_file"]
            for a in arch_result.get("integration_areas", [])
            if a.get("severity") in ("critical", "high")
        }
        cov_map.high_risk_uncovered = [
            f for f in cov_map.uncovered_files
            if any(f.endswith(af) or af.endswith(f) for af in arch_files)
        ]

        # ── Phase 4: Test generation ───────────────────────────────────────────
        # Priority: high-risk uncovered first, then any uncovered, capped at max
        priority_files = (
            cov_map.high_risk_uncovered +
            [f for f in cov_map.uncovered_files if f not in cov_map.high_risk_uncovered]
        )[:max_generated]

        generated = self._generate_tests_for_files(priority_files, str(root))

        # ── Phase 5: Baseline snapshot ─────────────────────────────────────────
        delta = self._load_previous_baseline(repo_id, arch_result, cov_map, total_vulns)
        self._save_baseline(repo_id, arch_result, cov_map, total_vulns)

        # ── Optional: Create PR ────────────────────────────────────────────────
        pr_url = ""
        if create_pr and github_token and generated:
            pr_url = self._create_pr(
                str(root), github_token, github_repo, generated, repo_name
            )

        return OnboardingReport(
            repo_path=str(root),
            repo_name=repo_name,
            timestamp=timestamp,
            architecture=arch_result,
            attack_surface_score=arch_result.get("attack_surface_score", 0.0),
            owasp_findings=owasp,
            secret_findings=secrets,
            cve_findings=cve,
            legal_findings=legal,
            hipaa_findings=hipaa,
            eu_ai_act=eu_act,
            prompt_injection_findings=prompt_inj,
            total_vulnerabilities=total_vulns,
            coverage=cov_map,
            generated_tests=generated,
            baseline_stored=True,
            baseline_delta=delta,
            repo_id=repo_id,
            pr_url=pr_url,
        )

    # ── Scanner helpers ────────────────────────────────────────────────────────

    def _run_architecture(self, repo_path: str) -> dict:
        try:
            from agenticqa.security.architecture_scanner import ArchitectureScanner
            result = ArchitectureScanner().scan(repo_path)
            return result.to_dict()
        except Exception as e:
            return {"error": str(e), "integration_areas": [],
                    "attack_surface_score": 0.0, "files_scanned": 0}

    def _run_owasp(self, repo_path: str) -> List[dict]:
        try:
            from agenticqa.security.owasp_scanner import OWASPScanner
            result = OWASPScanner().scan_directory(repo_path)
            return result.get("findings", [])
        except Exception:
            return []

    def _run_secrets(self, repo_path: str) -> List[dict]:
        try:
            from agenticqa.security.secrets_scanner import SecretsHistoryScanner
            result = SecretsHistoryScanner().scan_directory(repo_path)
            return result.get("findings", [])
        except Exception:
            return []

    def _run_cve(self, repo_path: str) -> List[dict]:
        try:
            from agenticqa.security.cve_reachability import CVEReachabilityScanner
            result = CVEReachabilityScanner().scan(repo_path)
            return result.get("reachable_cves", [])
        except Exception:
            return []

    def _run_legal(self, repo_path: str) -> List[dict]:
        try:
            from agenticqa.security.legal_risk_scanner import LegalRiskScanner
            result = LegalRiskScanner().scan(repo_path)
            return result.get("findings", [])
        except Exception:
            return []

    def _run_hipaa(self, repo_path: str) -> List[dict]:
        try:
            from agenticqa.security.hipaa_phi_scanner import HIPAAPhiScanner
            result = HIPAAPhiScanner().scan(repo_path)
            return result.get("findings", [])
        except Exception:
            return []

    def _run_eu_ai_act(self, repo_path: str) -> dict:
        try:
            from agenticqa.compliance.ai_act import AIActComplianceChecker
            result = AIActComplianceChecker().check(repo_path)
            return {
                "risk_category": result.risk_category,
                "conformity_score": result.conformity_score,
                "findings_count": len(result.findings),
            }
        except Exception:
            return {}

    def _run_prompt_injection(self, repo_path: str) -> List[dict]:
        try:
            from agenticqa.security.prompt_injection_scanner import PromptInjectionScanner
            result = PromptInjectionScanner().scan(repo_path)
            return result.get("findings", [])
        except Exception:
            return []

    # ── Test generation ────────────────────────────────────────────────────────

    def _generate_tests_for_files(
        self, files: List[str], repo_path: str
    ) -> List[GeneratedTestSummary]:
        results = []
        root = Path(repo_path)

        for rel_path in files:
            abs_path = root / rel_path
            if not abs_path.exists():
                continue
            try:
                code = abs_path.read_text(encoding="utf-8", errors="ignore")[:8000]
                detection = FrameworkDetector().detect(repo_path, rel_path)
                gen = FrontendTestGenerator().generate(
                    description=f"Existing code in {rel_path}",
                    code=code,
                    file_path=rel_path,
                    repo_path=repo_path,
                    detection=detection,
                )
                # Write the test file
                test_abs = root / gen.test_filename
                test_abs.parent.mkdir(parents=True, exist_ok=True)
                test_abs.write_text(gen.test_code, encoding="utf-8")

                results.append(GeneratedTestSummary(
                    source_file=rel_path,
                    test_file=gen.test_filename,
                    framework=gen.framework.value,
                    test_runner=gen.test_runner,
                    setup_instructions=gen.setup_instructions,
                ))
            except Exception as exc:
                results.append(GeneratedTestSummary(
                    source_file=rel_path,
                    test_file="",
                    framework="unknown",
                    test_runner="unknown",
                    setup_instructions=[],
                    status="failed",
                    error=str(exc),
                ))
        return results

    # ── Baseline ───────────────────────────────────────────────────────────────

    def _repo_id(self, root: Path) -> str:
        return hashlib.md5(str(root).encode()).hexdigest()[:12]

    def _baseline_path(self, repo_id: str) -> Path:
        return Path.home() / ".agenticqa" / "baselines" / f"{repo_id}.json"

    def _save_baseline(
        self,
        repo_id: str,
        arch: dict,
        cov: CoverageMap,
        total_vulns: int,
    ) -> None:
        path = self._baseline_path(repo_id)
        path.parent.mkdir(parents=True, exist_ok=True)
        snapshot = {
            "timestamp": datetime.now(tz=timezone.utc).isoformat(),
            "attack_surface_score": arch.get("attack_surface_score", 0.0),
            "coverage_pct": cov.coverage_pct,
            "total_vulnerabilities": total_vulns,
        }
        path.write_text(json.dumps(snapshot, indent=2), encoding="utf-8")

    def _load_previous_baseline(
        self,
        repo_id: str,
        arch: dict,
        cov: CoverageMap,
        total_vulns: int,
    ) -> Optional[BaselineDelta]:
        path = self._baseline_path(repo_id)
        if not path.exists():
            return None
        try:
            prev = json.loads(path.read_text())
            prev_score = prev.get("attack_surface_score", 0.0)
            prev_cov = prev.get("coverage_pct", 0.0)
            prev_vulns = prev.get("total_vulnerabilities", 0)
            curr_score = arch.get("attack_surface_score", 0.0)

            attack_change = curr_score - prev_score
            cov_change = cov.coverage_pct - prev_cov
            vuln_change = total_vulns - prev_vulns

            # Trend: improving if score down AND coverage up AND vulns down/same
            if attack_change < -5 and cov_change > 2:
                trend = "improving"
            elif attack_change > 5 or vuln_change > 3:
                trend = "declining"
            else:
                trend = "stable"

            return BaselineDelta(
                previous_date=prev.get("timestamp", ""),
                attack_surface_change=round(attack_change, 1),
                coverage_change=round(cov_change, 1),
                vulnerability_change=vuln_change,
                trend=trend,
            )
        except Exception:
            return None

    # ── PR creation ────────────────────────────────────────────────────────────

    def _create_pr(
        self,
        repo_path: str,
        github_token: str,
        github_repo: str,
        generated: List[GeneratedTestSummary],
        repo_name: str,
    ) -> str:
        try:
            import urllib.request
            branch = f"agenticqa/onboarding-tests-{datetime.now().strftime('%Y%m%d-%H%M%S')}"

            # Create branch and commit generated tests
            subprocess.run(["git", "checkout", "-b", branch], cwd=repo_path,
                           capture_output=True, check=True)

            for t in generated:
                if t.status == "generated" and t.test_file:
                    subprocess.run(["git", "add", t.test_file],
                                   cwd=repo_path, capture_output=True)

            subprocess.run(
                ["git", "commit", "-m",
                 f"test(agenticqa): add baseline test coverage for {len(generated)} files\n\n"
                 f"Generated by AgenticQA onboarding scan.\n"
                 f"Frameworks: {', '.join(set(t.framework for t in generated if t.status=='generated'))}"],
                cwd=repo_path, capture_output=True,
            )
            subprocess.run(["git", "push", "origin", branch], cwd=repo_path,
                           capture_output=True)

            # Open draft PR via GitHub REST API
            body = json.dumps({
                "title": f"test(agenticqa): baseline test coverage — {repo_name}",
                "body": (
                    "## AgenticQA Onboarding — Baseline Test Coverage\n\n"
                    f"Generated tests for **{len(generated)}** previously untested files.\n\n"
                    "### Files covered\n" +
                    "\n".join(f"- `{t.source_file}` → `{t.test_file}`"
                              for t in generated if t.status == "generated") +
                    "\n\n_Generated by AgenticQA · Review before merging_"
                ),
                "head": branch,
                "base": "main",
                "draft": True,
            }).encode("utf-8")

            req = urllib.request.Request(
                f"https://api.github.com/repos/{github_repo}/pulls",
                data=body,
                headers={
                    "Authorization": f"Bearer {github_token}",
                    "Accept": "application/vnd.github+json",
                    "Content-Type": "application/json",
                },
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=15) as resp:
                data = json.loads(resp.read())
                return data.get("html_url", "")
        except Exception:
            return ""
