#!/usr/bin/env python3
"""GitHub Action entrypoint for AgenticQA security scanning.

Reads configuration from environment variables set by action.yml inputs,
runs the scan, writes results + summary, and sets GitHub Action outputs.
"""
from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

# Ensure src/ is importable
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))
sys.path.insert(0, str(Path(__file__).parent.parent))


def _set_output(name: str, value: str) -> None:
    """Set a GitHub Actions output variable."""
    output_file = os.environ.get("GITHUB_OUTPUT", "")
    if output_file:
        with open(output_file, "a") as f:
            f.write(f"{name}={value}\n")
    else:
        # Fallback for local testing
        print(f"::set-output name={name}::{value}")


def _write_summary(summary_md: str) -> None:
    """Write to the GitHub Actions job summary."""
    summary_file = os.environ.get("GITHUB_STEP_SUMMARY", "")
    if summary_file:
        with open(summary_file, "a") as f:
            f.write(summary_md)


def _risk_level(critical: int, total: int) -> str:
    if critical > 100:
        return "critical"
    if critical > 10:
        return "high"
    if total > 100:
        return "medium"
    return "low"


def main() -> int:
    scan_path = os.environ.get("AGENTICQA_SCAN_PATH", ".")
    output_file = os.environ.get("AGENTICQA_OUTPUT_FILE", "agenticqa-results.json")
    fail_on_critical = os.environ.get("AGENTICQA_FAIL_ON_CRITICAL", "true").lower() == "true"
    generate_sarif = os.environ.get("AGENTICQA_SARIF", "false").lower() == "true"
    sarif_file = os.environ.get("AGENTICQA_SARIF_FILE", "agenticqa.sarif")

    # Resolve path
    repo_path = str(Path(scan_path).resolve())
    if not Path(repo_path).exists():
        print(f"::error::Scan path does not exist: {repo_path}")
        return 2

    print(f"{'='*60}")
    print(f"  AgenticQA Security Scan")
    print(f"  Scanning: {repo_path}")
    print(f"{'='*60}")

    # Import scan_repo from sibling script
    import importlib.util
    _scan_script = Path(__file__).parent / "run_client_scan.py"
    _spec = importlib.util.spec_from_file_location("run_client_scan", _scan_script)
    _mod = importlib.util.module_from_spec(_spec)
    _spec.loader.exec_module(_mod)
    scan_repo = _mod.scan_repo

    t0 = time.time()
    results = scan_repo(repo_path)
    elapsed = round(time.time() - t0, 2)

    # Calculate totals
    total_findings = 0
    total_critical = 0
    scanners_ok = 0
    scanners_failed = 0

    for name, data in results.items():
        if data["status"] == "ok":
            scanners_ok += 1
            r = data["result"]
            total_findings += r.get("total_findings", r.get("findings_count", 0))
            total_critical += r.get("critical", 0)
        else:
            scanners_failed += 1

    risk = _risk_level(total_critical, total_findings)

    # Build output
    output = {
        "summary": {
            "repo_path": repo_path,
            "scanners_ok": scanners_ok,
            "scanners_failed": scanners_failed,
            "total_findings": total_findings,
            "total_critical": total_critical,
            "total_elapsed_s": elapsed,
            "risk_level": risk,
        },
        "scanners": results,
    }

    # Write JSON results
    with open(output_file, "w") as f:
        json.dump(output, f, indent=2, default=str)

    # Set GitHub Action outputs
    _set_output("total_findings", str(total_findings))
    _set_output("critical_findings", str(total_critical))
    _set_output("scanners_ok", str(scanners_ok))
    _set_output("risk_level", risk)
    _set_output("result_file", output_file)

    # Print summary table
    print(f"\n{'='*60}")
    print(f"  RESULTS: {scanners_ok}/{len(results)} scanners OK")
    print(f"  Findings: {total_findings} total, {total_critical} critical")
    print(f"  Risk level: {risk.upper()}")
    print(f"  Elapsed: {elapsed}s")
    print(f"{'='*60}\n")

    for name, data in results.items():
        if data["status"] == "ok":
            r = data["result"]
            findings = r.get("total_findings", r.get("findings_count", "?"))
            crit = r.get("critical", 0)
            icon = "CRIT" if crit else "OK  "
            print(f"  [{icon}] {name:<25} findings={findings}  ({data['elapsed_s']}s)")
        else:
            print(f"  [FAIL] {name:<25} {data['error'][:60]}  ({data['elapsed_s']}s)")

    # Write GitHub Step Summary (markdown)
    summary_md = f"""## AgenticQA Security Scan Results

| Metric | Value |
|--------|-------|
| Total findings | **{total_findings}** |
| Critical findings | **{total_critical}** |
| Scanners passed | {scanners_ok}/{len(results)} |
| Risk level | **{risk.upper()}** |
| Scan time | {elapsed}s |

### Scanner Breakdown

| Scanner | Findings | Critical | Time |
|---------|----------|----------|------|
"""
    for name, data in results.items():
        if data["status"] == "ok":
            r = data["result"]
            findings = r.get("total_findings", r.get("findings_count", 0))
            crit = r.get("critical", 0)
            summary_md += f"| {name} | {findings} | {crit} | {data['elapsed_s']}s |\n"
        else:
            summary_md += f"| {name} | ERROR | - | {data['elapsed_s']}s |\n"

    if total_critical > 0:
        summary_md += f"\n> **{total_critical} critical findings detected.** Review the full report in the artifacts.\n"

    _write_summary(summary_md)

    # Generate SARIF if requested
    if generate_sarif:
        sarif_output = _generate_sarif(results, repo_path)
        with open(sarif_file, "w") as f:
            json.dump(sarif_output, f, indent=2)
        print(f"\nSARIF output written to {sarif_file}")

    # Exit code
    if fail_on_critical and total_critical > 0:
        print(f"\n::error::{total_critical} critical security findings detected. Failing workflow.")
        return 1

    return 0


def _generate_sarif(results: dict, repo_path: str) -> dict:
    """Convert scan results to SARIF 2.1.0 format for GitHub Code Scanning."""
    rules = []
    sarif_results = []
    rule_index = {}

    for scanner_name, data in results.items():
        if data["status"] != "ok":
            continue

        r = data["result"]

        # Create a rule for each scanner
        rule_id = f"agenticqa/{scanner_name}"
        if rule_id not in rule_index:
            rule_index[rule_id] = len(rules)
            severity = "error" if r.get("critical", 0) > 0 else "warning"
            rules.append({
                "id": rule_id,
                "name": scanner_name.replace("_", " ").title(),
                "shortDescription": {"text": f"AgenticQA {scanner_name} scanner"},
                "defaultConfiguration": {"level": severity},
            })

        findings_count = r.get("total_findings", r.get("findings_count", 0))
        if findings_count > 0:
            sarif_results.append({
                "ruleId": rule_id,
                "ruleIndex": rule_index[rule_id],
                "level": "error" if r.get("critical", 0) > 0 else "warning",
                "message": {
                    "text": f"{scanner_name}: {findings_count} findings ({r.get('critical', 0)} critical)"
                },
                "locations": [{
                    "physicalLocation": {
                        "artifactLocation": {"uri": ".", "uriBaseId": "%SRCROOT%"},
                    }
                }],
            })

    return {
        "$schema": "https://raw.githubusercontent.com/oasis-tcs/sarif-spec/main/sarif-2.1/schema/sarif-schema-2.1.0.json",
        "version": "2.1.0",
        "runs": [{
            "tool": {
                "driver": {
                    "name": "AgenticQA",
                    "version": "1.0.0",
                    "informationUri": "https://github.com/nhomyk/AgenticQA",
                    "rules": rules,
                }
            },
            "results": sarif_results,
        }],
    }


if __name__ == "__main__":
    sys.exit(main())
