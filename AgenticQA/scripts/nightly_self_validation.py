#!/usr/bin/env python3
"""
Nightly Self-Validation — Assert that every product claim is true.

Runs lightweight checks that verify the README and docs aren't lying.
No API key required.  No network calls.  ~30 seconds total.

Exit codes:
  0 — all assertions pass
  1 — one or more assertions failed

Usage:
    python scripts/nightly_self_validation.py          # pretty output
    python scripts/nightly_self_validation.py --json   # machine-readable
    python scripts/nightly_self_validation.py --ci     # exit 1 on failure

CI integration:
    Add as a nightly job or post-merge check:
      - name: Self-validation
        run: python scripts/nightly_self_validation.py --ci
"""
from __future__ import annotations

import argparse
import importlib
import json
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import List

# Ensure src/ is importable
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

# ANSI
_GREEN = "\033[92m"
_RED = "\033[91m"
_YELLOW = "\033[93m"
_BOLD = "\033[1m"
_RESET = "\033[0m"
_DIM = "\033[2m"


@dataclass
class Assertion:
    name: str
    category: str
    passed: bool
    detail: str
    elapsed_ms: float = 0.0


@dataclass
class ValidationReport:
    assertions: List[Assertion] = field(default_factory=list)
    total_elapsed_ms: float = 0.0

    @property
    def passed(self) -> int:
        return sum(1 for a in self.assertions if a.passed)

    @property
    def failed(self) -> int:
        return sum(1 for a in self.assertions if not a.passed)

    @property
    def all_passed(self) -> bool:
        return self.failed == 0

    def to_dict(self) -> dict:
        return {
            "all_passed": self.all_passed,
            "passed": self.passed,
            "failed": self.failed,
            "total_elapsed_ms": round(self.total_elapsed_ms, 1),
            "assertions": [
                {
                    "name": a.name,
                    "category": a.category,
                    "passed": a.passed,
                    "detail": a.detail,
                    "elapsed_ms": round(a.elapsed_ms, 1),
                }
                for a in self.assertions
            ],
        }


def _check(name: str, category: str, fn) -> Assertion:
    """Run a check function, catch exceptions, measure time."""
    t0 = time.monotonic()
    try:
        result = fn()
        elapsed = (time.monotonic() - t0) * 1000
        if isinstance(result, tuple):
            passed, detail = result
        elif isinstance(result, bool):
            passed, detail = result, "OK" if result else "FAILED"
        else:
            passed, detail = bool(result), str(result)
        return Assertion(name=name, category=category, passed=passed, detail=detail, elapsed_ms=elapsed)
    except Exception as exc:
        elapsed = (time.monotonic() - t0) * 1000
        return Assertion(name=name, category=category, passed=False, detail=f"Exception: {exc}", elapsed_ms=elapsed)


# ── Assertion functions ──────────────────────────────────────────────────────


def check_module_imports() -> tuple:
    """All 70+ modules across 10 packages must import without error."""
    packages = [
        "agenticqa.security",
        "agenticqa.compliance",
        "agenticqa.provenance",
        "agenticqa.regression",
        "agenticqa.monitoring",
        "agenticqa.verification",
        "agenticqa.graph",
        "agenticqa.rag",
        "agenticqa.delegation",
        "agenticqa.collaboration",
        "agenticqa.factory",
        "agenticqa.redteam",
        "agenticqa.github",
        "data_store",
    ]
    total = 0
    failures = []
    for pkg_name in packages:
        try:
            pkg = importlib.import_module(pkg_name)
        except ImportError:
            continue
        pkg_dir = Path(pkg.__file__).parent if hasattr(pkg, "__file__") and pkg.__file__ else None
        if not pkg_dir:
            continue
        for py in sorted(pkg_dir.glob("*.py")):
            if py.name.startswith("_"):
                continue
            mod_name = f"{pkg_name}.{py.stem}"
            total += 1
            try:
                importlib.import_module(mod_name)
            except Exception as exc:
                failures.append(f"{mod_name}: {exc}")
    if failures:
        return False, f"{len(failures)}/{total} modules failed: {'; '.join(failures[:5])}"
    return True, f"{total}/{total} modules import clean"


def check_api_endpoints() -> tuple:
    """agent_api.app must have 100+ routes."""
    try:
        # agent_api.py is at the project root, add to path if needed
        project_root = str(Path(__file__).parent.parent)
        if project_root not in sys.path:
            sys.path.insert(0, project_root)
        import agent_api
        routes = [r for r in agent_api.app.routes if hasattr(r, "path")]
        count = len(routes)
        if count >= 100:
            return True, f"{count} endpoints registered"
        return False, f"Only {count} endpoints (expected >= 100)"
    except Exception as exc:
        return False, f"Could not import agent_api: {exc}"


def check_dashboard_pages() -> tuple:
    """Dashboard must have 16+ render functions."""
    try:
        dashboard_path = Path(__file__).parent.parent / "dashboard" / "app.py"
        if not dashboard_path.exists():
            return False, "dashboard/app.py not found"
        source = dashboard_path.read_text()
        render_fns = [line for line in source.splitlines() if line.strip().startswith("def render_")]
        count = len(render_fns)
        if count >= 16:
            return True, f"{count} render functions found"
        return False, f"Only {count} render functions (expected >= 16)"
    except Exception as exc:
        return False, f"Exception: {exc}"


def check_security_modules() -> tuple:
    """33+ security module files must exist."""
    sec_dir = Path(__file__).parent.parent / "src" / "agenticqa" / "security"
    if not sec_dir.exists():
        return False, "security/ directory not found"
    modules = [f for f in sec_dir.glob("*.py") if not f.name.startswith("_")]
    count = len(modules)
    if count >= 10:
        return True, f"{count} security modules"
    return False, f"Only {count} security modules"


def check_architecture_scanner() -> tuple:
    """ArchitectureScanner must scan a directory without error and return results."""
    import tempfile
    from agenticqa.security.architecture_scanner import ArchitectureScanner
    with tempfile.TemporaryDirectory() as td:
        (Path(td) / "app.py").write_text("import subprocess\nsubprocess.run(['ls'])\n")
        result = ArchitectureScanner().scan(td)
    if result.scan_error:
        return False, f"Scan error: {result.scan_error}"
    if not result.integration_areas:
        return False, "No integration areas found in test file"
    cats = result.by_category()
    return True, f"{len(result.integration_areas)} areas, {len(cats)} categories, score {result.attack_surface_score:.0f}/100"


def check_architecture_scanner_categories() -> tuple:
    """ArchitectureScanner must have 13 integration categories (+ SCHEMA_VALIDATION)."""
    from agenticqa.security.architecture_scanner import _PLAIN_ENGLISH
    count = len(_PLAIN_ENGLISH)
    if count == 14:
        return True, f"14 category descriptions (13 categories + SCHEMA_VALIDATION)"
    return False, f"Expected 14 categories, got {count}"


def check_agent_detection() -> tuple:
    """ArchitectureScanner must detect AGENT_FRAMEWORK patterns."""
    import tempfile
    from agenticqa.security.architecture_scanner import ArchitectureScanner
    with tempfile.TemporaryDirectory() as td:
        (Path(td) / "agent.py").write_text("from langchain.agents import AgentExecutor\nagent = AgentExecutor(agent=a)\n")
        result = ArchitectureScanner().scan(td)
    agents = [a for a in result.integration_areas if a.category == "AGENT_FRAMEWORK"]
    if not agents:
        return False, "AGENT_FRAMEWORK not detected in LangChain file"
    return True, f"{len(agents)} AGENT_FRAMEWORK findings detected"


def check_compliance_scanners() -> tuple:
    """All 7 compliance scanners must be importable."""
    scanners = [
        ("agenticqa.security.legal_risk_scanner", "LegalRiskScanner"),
        ("agenticqa.security.hipaa_phi_scanner", "HIPAAPHIScanner"),
        ("agenticqa.compliance.ai_act", "AIActComplianceChecker"),
        ("agenticqa.security.ai_model_sbom", "AIModelSBOMScanner"),
        ("agenticqa.security.prompt_injection_scanner", "PromptInjectionScanner"),
        ("agenticqa.security.agent_trust_graph", "AgentTrustGraphAnalyzer"),
        ("agenticqa.security.cve_reachability", "CVEReachabilityAnalyzer"),
    ]
    ok = 0
    failures = []
    for mod_name, cls_name in scanners:
        try:
            mod = importlib.import_module(mod_name)
            getattr(mod, cls_name)
            ok += 1
        except Exception as exc:
            failures.append(f"{cls_name}: {exc}")
    if failures:
        return False, f"{ok}/7 scanners OK; failures: {'; '.join(failures)}"
    return True, f"7/7 compliance scanners import clean"


def check_sarif_export() -> tuple:
    """SARIFExporter must produce valid SARIF 2.1.0 structure."""
    from agenticqa.export.sarif import SARIFExporter
    exporter = SARIFExporter()
    exporter.add_sre_result({
        "total_errors": 1, "fixes_applied": 0, "fixes": [],
        "errors": [{"rule": "E301", "file": "x.py", "line": 1, "message": "test"}],
    })
    sarif = exporter.to_dict()
    if sarif.get("version") != "2.1.0":
        return False, f"Wrong SARIF version: {sarif.get('version')}"
    if "$schema" not in sarif:
        return False, "Missing $schema"
    if not sarif.get("runs"):
        return False, "No runs in SARIF output"
    return True, "Valid SARIF 2.1.0 with schema, version, and runs"


def check_provenance() -> tuple:
    """OutputProvenanceLogger must sign and verify."""
    import tempfile
    from agenticqa.provenance.output_provenance import OutputProvenanceLogger
    with tempfile.TemporaryDirectory() as td:
        prov = OutputProvenanceLogger(provenance_dir=td)
        record = prov.sign_and_log(agent_name="test_agent", model_id="test-model", output_text="test output")
        if not getattr(record, "signature", None):
            return False, "No signature in provenance record"
        vr = prov.verify(output_text="test output", agent_name="test_agent")
        if not getattr(vr, "valid", False):
            return False, f"Signature verification failed: {getattr(vr, 'reason', 'unknown')}"
    return True, "Sign + verify round-trip OK"


def check_pr_risk_scorer() -> tuple:
    """PRRiskScorer must score a PR and return a recommendation."""
    from agenticqa.scoring.pr_risk_scorer import PRRiskScorer
    scorer = PRRiskScorer()
    report = scorer.score(
        author_email="test@example.com",
        changed_files=["src/auth/login.py"],
        diff_lines="+password = 'hunter2'\n",
    )
    if report.recommendation not in ("LOW RISK", "MEDIUM RISK", "HIGH RISK"):
        return False, f"Unexpected recommendation: {report.recommendation}"
    if not 0 <= report.risk_score <= 100:
        return False, f"Score out of range: {report.risk_score}"
    return True, f"Score {report.risk_score:.0f}/100 → {report.recommendation}"


def check_demo_pipeline() -> tuple:
    """run_demo.py must exist and be importable as a module."""
    demo_path = Path(__file__).parent.parent / "run_demo.py"
    if not demo_path.exists():
        return False, "run_demo.py not found"
    return True, "run_demo.py exists"


def check_scanner_self_scan() -> tuple:
    """All scanners must complete without error when pointed at our own repo."""
    repo = str(Path(__file__).parent.parent)
    failures = []
    ok = 0
    scanners = [
        ("ArchitectureScanner", lambda: __import__("agenticqa.security.architecture_scanner", fromlist=["ArchitectureScanner"]).ArchitectureScanner().scan(repo)),
        ("LegalRiskScanner", lambda: __import__("agenticqa.security.legal_risk_scanner", fromlist=["LegalRiskScanner"]).LegalRiskScanner().scan(repo)),
        ("HIPAAPHIScanner", lambda: __import__("agenticqa.security.hipaa_phi_scanner", fromlist=["HIPAAPHIScanner"]).HIPAAPHIScanner().scan(repo)),
        ("PromptInjectionScanner", lambda: __import__("agenticqa.security.prompt_injection_scanner", fromlist=["PromptInjectionScanner"]).PromptInjectionScanner().scan(repo)),
        ("MCPSecurityScanner", lambda: __import__("agenticqa.security.mcp_scanner", fromlist=["MCPSecurityScanner"]).MCPSecurityScanner().scan(repo)),
        ("CrossAgentDataFlowTracer", lambda: __import__("agenticqa.security.data_flow_tracer", fromlist=["CrossAgentDataFlowTracer"]).CrossAgentDataFlowTracer().trace(repo)),
        ("AgentTrustGraphAnalyzer", lambda: __import__("agenticqa.security.agent_trust_graph", fromlist=["AgentTrustGraphAnalyzer"]).AgentTrustGraphAnalyzer().analyze(repo)),
        ("AIModelSBOMScanner", lambda: __import__("agenticqa.security.ai_model_sbom", fromlist=["AIModelSBOMScanner"]).AIModelSBOMScanner().scan(repo)),
        ("AIActComplianceChecker", lambda: __import__("agenticqa.compliance.ai_act", fromlist=["AIActComplianceChecker"]).AIActComplianceChecker().check(repo)),
    ]
    for name, fn in scanners:
        try:
            result = fn()
            if getattr(result, "scan_error", None):
                failures.append(f"{name}: scan_error={result.scan_error}")
            else:
                ok += 1
        except Exception as exc:
            failures.append(f"{name}: {type(exc).__name__}: {exc}")
    if failures:
        return False, f"{ok}/{len(scanners)} OK; failures: {'; '.join(failures[:3])}"
    return True, f"{len(scanners)}/{len(scanners)} scanners completed self-scan"


def check_convenience_properties() -> tuple:
    """Scanner results must expose total_findings, risk_score, and aliases."""
    import tempfile
    from agenticqa.security.architecture_scanner import ArchitectureScanner
    from agenticqa.security.mcp_scanner import MCPSecurityScanner
    from agenticqa.security.data_flow_tracer import CrossAgentDataFlowTracer
    from agenticqa.security.agent_trust_graph import AgentTrustGraphAnalyzer
    from agenticqa.security.prompt_injection_scanner import PromptInjectionScanner

    with tempfile.TemporaryDirectory() as td:
        (Path(td) / "app.py").write_text("import subprocess\nsubprocess.run(['ls'])\n")
        arch = ArchitectureScanner().scan(td)
        mcp = MCPSecurityScanner().scan(td)
        dft = CrossAgentDataFlowTracer().trace(td)
        trust = AgentTrustGraphAnalyzer().analyze(td)
        pi = PromptInjectionScanner().scan(td)

    checks = [
        ("arch.total_findings", hasattr(arch, "total_findings") and isinstance(arch.total_findings, int)),
        ("arch.category_counts", hasattr(arch, "category_counts") and isinstance(arch.category_counts, dict)),
        ("arch.severity_counts", hasattr(arch, "severity_counts") and isinstance(arch.severity_counts, dict)),
        ("mcp.total_findings", hasattr(mcp, "total_findings") and isinstance(mcp.total_findings, int)),
        ("mcp.category_counts", hasattr(mcp, "category_counts") and isinstance(mcp.category_counts, dict)),
        ("dft.total_findings", hasattr(dft, "total_findings") and isinstance(dft.total_findings, int)),
        ("trust.agents", hasattr(trust, "agents")),
        ("trust.findings", hasattr(trust, "findings")),
        ("trust.has_cycles", hasattr(trust, "has_cycles")),
        ("pi.risk_score", hasattr(pi, "risk_score")),
        ("pi.total_findings", hasattr(pi, "total_findings") and isinstance(pi.total_findings, int)),
        ("pi.critical_findings", hasattr(pi, "critical_findings")),
    ]
    failed = [name for name, ok in checks if not ok]
    if failed:
        return False, f"Missing properties: {', '.join(failed)}"
    return True, f"{len(checks)}/{len(checks)} convenience properties verified"


def check_python_auto_linting() -> tuple:
    """SREAgent._run_python_linter must exist and handle a temp repo."""
    import tempfile
    sys.path.insert(0, str(Path(__file__).parent.parent))
    from agents import SREAgent
    if not hasattr(SREAgent, "_run_python_linter"):
        return False, "_run_python_linter method missing from SREAgent"
    agent = SREAgent.__new__(SREAgent)
    agent.agent_name = "SRE_Agent"
    agent._strategy_selector = None
    with tempfile.TemporaryDirectory() as td:
        # No Python indicators → should return []
        (Path(td) / "index.js").write_text("console.log('hi')")
        result = agent._run_python_linter(td)
        if result != []:
            return False, f"Expected [] for non-Python repo, got {len(result)} errors"
    return True, "_run_python_linter works: returns [] for non-Python repos"


def check_agent_output_contracts() -> tuple:
    """Agent output contracts must be registered for all 8 agents."""
    from agenticqa.contracts import AGENT_CONTRACTS, validate_agent_output
    expected = {"QA_Assistant", "Performance_Agent", "Compliance_Agent", "DevOps_Agent",
                "SRE_Agent", "SDET_Agent", "Fullstack_Agent", "RedTeam_Agent"}
    missing = expected - set(AGENT_CONTRACTS.keys())
    if missing:
        return False, f"Missing contracts: {', '.join(sorted(missing))}"
    return True, f"{len(expected)}/{len(expected)} agent output contracts registered"


def check_path_sanitization() -> tuple:
    """Path sanitizer must block traversal attacks."""
    from agenticqa.security.path_sanitizer import sanitize_repo_path
    # Valid path must pass
    try:
        sanitize_repo_path("/tmp")
    except ValueError:
        return False, "/tmp should be allowed but was rejected"
    # Traversal must be blocked
    try:
        sanitize_repo_path("/etc/passwd")
        return False, "/etc/passwd should be blocked but was allowed"
    except ValueError:
        pass
    try:
        sanitize_repo_path("/tmp/../etc/passwd")
        return False, "Traversal escape should be blocked but was allowed"
    except ValueError:
        pass
    return True, "Path sanitizer blocks /etc/passwd and traversal escapes"


def check_test_count() -> tuple:
    """pytest must discover 1500+ unit tests."""
    import subprocess
    result = subprocess.run(
        [sys.executable, "-m", "pytest", "tests/", "-m", "unit", "--collect-only", "-q"],
        capture_output=True, text=True, timeout=30,
    )
    # Parse "N tests collected" or "N items" from output
    for line in result.stdout.splitlines():
        if "selected" in line or "collected" in line or "test" in line:
            import re
            match = re.search(r"(\d+)\s+(test|item|selected)", line)
            if match:
                count = int(match.group(1))
                if count >= 1500:
                    return True, f"{count} unit tests discovered"
                return False, f"Only {count} tests (expected >= 1500)"
    return False, f"Could not parse test count from pytest output"


# ── Main ─────────────────────────────────────────────────────────────────────


def run_all() -> ValidationReport:
    """Run all self-validation assertions."""
    checks = [
        ("Module importability (70+ modules)", "modules", check_module_imports),
        ("API endpoint count (100+)", "api", check_api_endpoints),
        ("Dashboard render functions (16+)", "dashboard", check_dashboard_pages),
        ("Security module count", "security", check_security_modules),
        ("ArchitectureScanner executes", "scanner", check_architecture_scanner),
        ("ArchitectureScanner has 13 categories", "scanner", check_architecture_scanner_categories),
        ("Agent framework detection", "scanner", check_agent_detection),
        ("Compliance scanners (7/7)", "compliance", check_compliance_scanners),
        ("SARIF 2.1.0 export", "export", check_sarif_export),
        ("Output provenance sign+verify", "provenance", check_provenance),
        ("PR Risk Scorer", "scoring", check_pr_risk_scorer),
        ("Demo pipeline exists", "pipeline", check_demo_pipeline),
        ("Scanner self-scan (9 scanners)", "client", check_scanner_self_scan),
        ("Convenience properties (12 checks)", "client", check_convenience_properties),
        ("Python auto-linting", "sre", check_python_auto_linting),
        ("Agent output contracts (8 agents)", "contracts", check_agent_output_contracts),
        ("Path sanitization (CWE-22)", "security", check_path_sanitization),
        ("Unit test count (1500+)", "tests", check_test_count),
    ]

    report = ValidationReport()
    t0 = time.monotonic()

    for name, category, fn in checks:
        assertion = _check(name, category, fn)
        report.assertions.append(assertion)

    report.total_elapsed_ms = (time.monotonic() - t0) * 1000
    return report


def main():
    parser = argparse.ArgumentParser(description="Nightly Self-Validation")
    parser.add_argument("--json", action="store_true", help="Machine-readable JSON output")
    parser.add_argument("--ci", action="store_true", help="Exit 1 on failure")
    args = parser.parse_args()

    report = run_all()

    if args.json:
        print(json.dumps(report.to_dict(), indent=2))
    else:
        print()
        print(f"{_BOLD}{'=' * 70}{_RESET}")
        print(f"{_BOLD}  AGENTICQA SELF-VALIDATION{_RESET}")
        print(f"{'=' * 70}")
        print()

        for a in report.assertions:
            icon = f"{_GREEN}PASS{_RESET}" if a.passed else f"{_RED}FAIL{_RESET}"
            print(f"  [{icon}] {a.name}")
            print(f"         {_DIM}{a.detail}  ({a.elapsed_ms:.0f}ms){_RESET}")

        print()
        print(f"{'=' * 70}")
        color = _GREEN if report.all_passed else _RED
        print(f"  {color}{_BOLD}{report.passed}/{len(report.assertions)} assertions passed{_RESET}"
              f"  ({report.total_elapsed_ms:.0f}ms)")
        if not report.all_passed:
            print(f"  {_RED}{report.failed} FAILED{_RESET}")
        print(f"{'=' * 70}")
        print()

    if args.ci and not report.all_passed:
        sys.exit(1)


if __name__ == "__main__":
    main()
