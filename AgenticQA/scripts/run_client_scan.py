#!/usr/bin/env python3
"""Run all AgenticQA security scanners against a target repo.

No API tokens required. Pure static analysis. Outputs JSON for CI ingestion.

Usage:
    python scripts/run_client_scan.py /path/to/repo
    python scripts/run_client_scan.py /path/to/repo --json           # JSON output
    python scripts/run_client_scan.py /path/to/repo --output out.json # save to file
    python scripts/run_client_scan.py /path/to/repo --fail-on-critical # exit 1 if criticals

CI integration:
    - name: Security scan
      run: python scripts/run_client_scan.py . --json --output scan-results.json --fail-on-critical
    - name: Ingest results
      run: python scripts/ingest_scan_results.py scan-results.json
"""
from __future__ import annotations

import argparse
import json
import sys
import time
import traceback
from pathlib import Path

# Ensure src/ is importable
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))
sys.path.insert(0, str(Path(__file__).parent.parent))

_GREEN = "\033[92m"
_RED = "\033[91m"
_YELLOW = "\033[93m"
_BOLD = "\033[1m"
_RESET = "\033[0m"
_DIM = "\033[2m"


def _run_scanner(name, fn):
    """Run a scanner, capture result/error/timing."""
    t0 = time.time()
    try:
        result = fn()
        elapsed = time.time() - t0
        return {"status": "ok", "elapsed_s": round(elapsed, 2), "result": result}
    except Exception as e:
        elapsed = time.time() - t0
        return {
            "status": "error",
            "elapsed_s": round(elapsed, 2),
            "error": f"{type(e).__name__}: {e}",
            "traceback": traceback.format_exc()[-500:],
        }


def scan_repo(repo_path: str) -> dict:
    """Run all scanners against a repo and return structured results."""
    results = {}

    # 1. Architecture Scanner
    def run_arch():
        from agenticqa.security.architecture_scanner import ArchitectureScanner
        r = ArchitectureScanner().scan(repo_path)
        return {
            "total_findings": r.total_findings,
            "files_scanned": r.files_scanned,
            "attack_surface_score": r.attack_surface_score,
            "categories": r.category_counts,
            "severity_counts": r.severity_counts,
            "critical_count": len(r.critical_areas),
            "untested_count": len(r.untested_areas),
        }
    results["architecture"] = _run_scanner("architecture", run_arch)

    # 2. Legal Risk Scanner
    def run_legal():
        from agenticqa.security.legal_risk_scanner import LegalRiskScanner
        r = LegalRiskScanner().scan(repo_path)
        return {
            "total_findings": len(r.findings),
            "risk_score": r.risk_score,
            "critical": len(r.critical_findings),
            "findings": [{"rule_id": f.rule_id, "file": f.file, "line": f.line,
                         "severity": f.severity} for f in r.findings[:20]],
        }
    results["legal_risk"] = _run_scanner("legal_risk", run_legal)

    # 3. CVE Reachability
    def run_cve():
        from agenticqa.security.cve_reachability import CVEReachabilityAnalyzer
        a = CVEReachabilityAnalyzer()
        py = a.scan_python(repo_path)
        js = a.scan_javascript(repo_path)
        return {
            "python_cves": len(py.cves),
            "python_reachable": len(py.reachable_cves),
            "python_error": py.scan_error,
            "js_cves": len(js.cves),
            "js_reachable": len(js.reachable_cves),
            "js_error": js.scan_error,
        }
    results["cve_reachability"] = _run_scanner("cve_reachability", run_cve)

    # 4. HIPAA PHI Scanner
    def run_hipaa():
        from agenticqa.security.hipaa_phi_scanner import HIPAAPHIScanner
        r = HIPAAPHIScanner().scan(repo_path)
        return {
            "total_findings": len(r.findings),
            "risk_score": r.risk_score,
            "critical": len(r.critical_findings),
        }
    results["hipaa"] = _run_scanner("hipaa", run_hipaa)

    # 5. AI Model SBOM
    def run_sbom():
        from agenticqa.security.ai_model_sbom import AIModelSBOMScanner
        r = AIModelSBOMScanner().scan(repo_path)
        return {
            "providers": r.providers_detected,
            "unique_models": len(r.unique_model_ids),
            "risk_score": r.risk_score,
            "license_violations": len(r.license_violations),
        }
    results["ai_model_sbom"] = _run_scanner("ai_model_sbom", run_sbom)

    # 6. EU AI Act
    def run_aiact():
        from agenticqa.compliance.ai_act import AIActComplianceChecker
        r = AIActComplianceChecker().check(repo_path)
        return {
            "risk_category": r.risk_category,
            "conformity_score": r.conformity_score,
            "annex_iii": r.annex_iii_match,
            "findings_count": len(r.findings),
            "missing": sum(1 for f in r.findings if f.status == "missing"),
        }
    results["ai_act"] = _run_scanner("ai_act", run_aiact)

    # 7. Agent Trust Graph
    def run_trust():
        from agenticqa.security.agent_trust_graph import AgentTrustGraphAnalyzer
        r = AgentTrustGraphAnalyzer().analyze(repo_path)
        return {
            "frameworks": r.frameworks_detected,
            "agents": len(r.agents),
            "edges": len(r.edges),
            "findings_count": len(r.findings),
            "has_cycles": r.has_cycles,
            "risk_score": r.risk_score,
        }
    results["trust_graph"] = _run_scanner("trust_graph", run_trust)

    # 8. Prompt Injection Scanner
    def run_pi():
        from agenticqa.security.prompt_injection_scanner import PromptInjectionScanner
        r = PromptInjectionScanner().scan(repo_path)
        return {
            "total_findings": r.total_findings,
            "risk_score": r.risk_score,
            "critical": len(r.critical_findings),
        }
    results["prompt_injection"] = _run_scanner("prompt_injection", run_pi)

    # 9. MCP Security Scanner
    def run_mcp():
        from agenticqa.security.mcp_scanner import MCPSecurityScanner
        r = MCPSecurityScanner().scan(repo_path)
        return {
            "total_findings": r.total_findings,
            "files_scanned": r.files_scanned,
            "risk_score": r.risk_score,
            "categories": r.category_counts,
        }
    results["mcp_security"] = _run_scanner("mcp_security", run_mcp)

    # 10. Data Flow Tracer
    def run_dft():
        from agenticqa.security.data_flow_tracer import CrossAgentDataFlowTracer
        r = CrossAgentDataFlowTracer().trace(repo_path)
        return {
            "total_findings": r.total_findings,
            "files_scanned": r.files_scanned,
            "risk_score": r.risk_score,
        }
    results["data_flow"] = _run_scanner("data_flow", run_dft)

    # 11. Shadow AI Detection (AI-specific — no traditional tool equivalent)
    def run_shadow():
        from agenticqa.security.shadow_ai_detector import ShadowAIDetector
        r = ShadowAIDetector().scan(repo_path)
        return {
            "has_shadow_ai": r.has_shadow_ai,
            "total_findings": r.total_findings,
            "providers_found": sorted(r.providers_found),
            "files_scanned": r.files_scanned,
        }
    results["shadow_ai"] = _run_scanner("shadow_ai", run_shadow)

    # 12. Bias Detection (AI-specific — scans for demographic bias in outputs)
    def run_bias():
        from agenticqa.security.bias_detector import BiasDetector
        from agenticqa.security.safe_file_iter import iter_source_files, safe_read_text
        detector = BiasDetector(sensitivity="high")
        total_risk = 0.0
        files_flagged = 0
        categories: set = set()
        for fpath in iter_source_files(Path(repo_path), extensions={".py", ".js", ".ts"}, max_files=5000):
            content = safe_read_text(fpath)
            if not content:
                continue
            report = detector.scan(content)
            if report.has_bias_risk:
                files_flagged += 1
                total_risk = max(total_risk, report.risk_score)
                categories.update(report.categories_flagged)
        return {
            "total_findings": files_flagged,
            "max_risk_score": round(total_risk, 2),
            "categories_flagged": sorted(categories),
        }
    results["bias_detection"] = _run_scanner("bias_detection", run_bias)

    # 13. Indirect Injection Guard (AI-specific — RAG pipeline safety)
    def run_injection():
        from agenticqa.security.indirect_injection_guard import IndirectInjectionGuard
        from agenticqa.security.safe_file_iter import iter_source_files, safe_read_text
        guard = IndirectInjectionGuard()
        unsafe_files = 0
        total_findings = 0
        critical_findings = 0
        for fpath in iter_source_files(Path(repo_path), extensions={".py", ".js", ".ts", ".md", ".txt"}, max_files=5000):
            content = safe_read_text(fpath)
            if not content:
                continue
            report = guard.scan(content)
            if not report.is_safe:
                unsafe_files += 1
                total_findings += report.total_findings
                critical_findings += len(report.critical_findings)
        return {
            "total_findings": total_findings,
            "unsafe_files": unsafe_files,
            "critical": critical_findings,
        }
    results["injection_guard"] = _run_scanner("injection_guard", run_injection)

    return results


def main():
    parser = argparse.ArgumentParser(description="Run AgenticQA security scanners against a repo")
    parser.add_argument("repo_path", help="Path to the repository to scan")
    parser.add_argument("--json", action="store_true", help="JSON output only")
    parser.add_argument("--output", "-o", help="Save results to file")
    parser.add_argument("--fail-on-critical", action="store_true",
                        help="Exit 1 if any scanner finds critical issues")
    args = parser.parse_args()

    repo = args.repo_path
    if not Path(repo).exists():
        print(f"Error: {repo} does not exist", file=sys.stderr)
        sys.exit(2)

    t0 = time.time()
    results = scan_repo(repo)
    total_elapsed = round(time.time() - t0, 2)

    # Build summary
    scanners_ok = sum(1 for v in results.values() if v["status"] == "ok")
    scanners_failed = sum(1 for v in results.values() if v["status"] == "error")
    total_findings = 0
    total_critical = 0
    for v in results.values():
        if v["status"] == "ok":
            r = v["result"]
            total_findings += r.get("total_findings", r.get("findings_count", 0))
            total_critical += r.get("critical", 0)

    summary = {
        "repo_path": str(Path(repo).resolve()),
        "scanners_ok": scanners_ok,
        "scanners_failed": scanners_failed,
        "total_findings": total_findings,
        "total_critical": total_critical,
        "total_elapsed_s": total_elapsed,
    }

    output = {"summary": summary, "scanners": results}

    if args.output:
        with open(args.output, "w") as f:
            json.dump(output, f, indent=2, default=str)

    if args.json:
        print(json.dumps(output, indent=2, default=str))
    else:
        print(f"\n{_BOLD}{'='*60}{_RESET}")
        print(f"{_BOLD}  AGENTICQA SECURITY SCAN — {Path(repo).name}{_RESET}")
        print(f"{'='*60}\n")

        for name, data in results.items():
            if data["status"] == "ok":
                r = data["result"]
                findings = r.get("total_findings", r.get("findings_count", "?"))
                crit = r.get("critical", 0)
                icon = f"{_RED}CRIT" if crit else f"{_GREEN}OK  "
                print(f"  [{icon}{_RESET}] {name:<25} findings={findings}"
                      f"  ({data['elapsed_s']}s)")
            else:
                print(f"  [{_RED}FAIL{_RESET}] {name:<25} {data['error'][:60]}"
                      f"  ({data['elapsed_s']}s)")

        print(f"\n{'='*60}")
        color = _RED if total_critical > 0 else _GREEN
        print(f"  {color}{_BOLD}{scanners_ok}/{len(results)} scanners OK{_RESET}"
              f"  |  {total_findings} findings  |  {total_critical} critical"
              f"  |  {total_elapsed}s")
        if scanners_failed:
            print(f"  {_RED}{scanners_failed} scanners FAILED{_RESET}")
        print(f"{'='*60}\n")

    if args.fail_on_critical and total_critical > 0:
        sys.exit(1)


if __name__ == "__main__":
    main()
