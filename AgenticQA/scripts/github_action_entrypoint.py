#!/usr/bin/env python3
"""GitHub Action entrypoint for AgenticQA security scanning.

Reads configuration from environment variables set by action.yml inputs,
runs the scan, writes results + summary, posts PR comments, and sets
GitHub Action outputs.
"""
from __future__ import annotations

import json
import os
import subprocess
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


def _risk_color(level: str) -> str:
    """Shield.io color for a risk level."""
    return {"critical": "red", "high": "orange", "medium": "yellow", "low": "brightgreen"}.get(level, "lightgrey")


# ── Delta scan (new findings only) ─────────────────────────────────────────


def _load_baseline(baseline_file: str) -> dict | None:
    """Load a previous scan result as baseline for delta comparison."""
    if not baseline_file or not Path(baseline_file).exists():
        return None
    try:
        with open(baseline_file) as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return None


def _compute_delta(current: dict, baseline: dict) -> dict:
    """Compare current vs baseline scan results, return only delta."""
    delta = {}
    current_scanners = current.get("scanners", current)
    baseline_scanners = baseline.get("scanners", baseline)

    for name, data in current_scanners.items():
        if data.get("status") != "ok":
            delta[name] = {"status": "new_error", "detail": data.get("error", "")}
            continue

        cur_result = data["result"]
        cur_findings = cur_result.get("total_findings", cur_result.get("findings_count", 0))
        cur_critical = cur_result.get("critical", 0)

        base_data = baseline_scanners.get(name)
        if base_data is None or base_data.get("status") != "ok":
            # New scanner or scanner was broken before
            delta[name] = {
                "new_findings": cur_findings,
                "new_critical": cur_critical,
                "baseline_findings": 0,
                "baseline_critical": 0,
            }
            continue

        base_result = base_data["result"]
        base_findings = base_result.get("total_findings", base_result.get("findings_count", 0))
        base_critical = base_result.get("critical", 0)

        new_findings = max(0, cur_findings - base_findings)
        new_critical = max(0, cur_critical - base_critical)

        delta[name] = {
            "new_findings": new_findings,
            "new_critical": new_critical,
            "baseline_findings": base_findings,
            "baseline_critical": base_critical,
        }

    return delta


# ── Build system detection ──────────────────────────────────────────────────


def detect_build_system(repo_path: str) -> dict:
    """Auto-detect project type from build files in the repo."""
    p = Path(repo_path)
    detected = {
        "languages": [],
        "build_systems": [],
        "package_managers": [],
    }

    # Python
    if (p / "pyproject.toml").exists() or (p / "setup.py").exists() or (p / "setup.cfg").exists():
        detected["languages"].append("python")
        if (p / "pyproject.toml").exists():
            detected["build_systems"].append("pyproject")
        if (p / "setup.py").exists():
            detected["build_systems"].append("setuptools")
        if (p / "Pipfile").exists():
            detected["package_managers"].append("pipenv")
        elif (p / "poetry.lock").exists():
            detected["package_managers"].append("poetry")
        elif (p / "requirements.txt").exists():
            detected["package_managers"].append("pip")

    # JavaScript / TypeScript
    if (p / "package.json").exists():
        lang = "typescript" if (p / "tsconfig.json").exists() else "javascript"
        detected["languages"].append(lang)
        if (p / "pnpm-lock.yaml").exists():
            detected["package_managers"].append("pnpm")
        elif (p / "yarn.lock").exists():
            detected["package_managers"].append("yarn")
        elif (p / "bun.lockb").exists():
            detected["package_managers"].append("bun")
        else:
            detected["package_managers"].append("npm")

    # Go
    if (p / "go.mod").exists():
        detected["languages"].append("go")
        detected["build_systems"].append("go-modules")

    # Rust
    if (p / "Cargo.toml").exists():
        detected["languages"].append("rust")
        detected["build_systems"].append("cargo")

    # Java / Kotlin
    if (p / "pom.xml").exists():
        detected["languages"].append("java")
        detected["build_systems"].append("maven")
    elif (p / "build.gradle").exists() or (p / "build.gradle.kts").exists():
        lang = "kotlin" if (p / "build.gradle.kts").exists() else "java"
        detected["languages"].append(lang)
        detected["build_systems"].append("gradle")

    # PHP
    if (p / "composer.json").exists():
        detected["languages"].append("php")
        detected["package_managers"].append("composer")

    # Ruby
    if (p / "Gemfile").exists():
        detected["languages"].append("ruby")
        detected["package_managers"].append("bundler")

    # .NET
    for ext in ("*.csproj", "*.fsproj", "*.sln"):
        if list(p.glob(ext)):
            detected["languages"].append("dotnet")
            detected["build_systems"].append("dotnet")
            break

    # Docker
    if (p / "Dockerfile").exists() or (p / "docker-compose.yml").exists():
        detected["build_systems"].append("docker")

    return detected


# ── PR auto-commenting ──────────────────────────────────────────────────────


def _post_pr_comment(results: dict, delta: dict | None, build_info: dict, elapsed: float) -> bool:
    """Post scan results as a PR comment using gh CLI. Returns True on success."""
    token = os.environ.get("GITHUB_TOKEN", "")
    if not token:
        print("INFO: GITHUB_TOKEN not set — skipping PR comment")
        return False

    # Detect PR number from GITHUB_REF
    ref = os.environ.get("GITHUB_REF", "")
    pr_number = None
    if "/pull/" in ref:
        try:
            parts = ref.split("/")
            idx = parts.index("pull")
            pr_number = int(parts[idx + 1])
        except (ValueError, IndexError):
            pass

    if pr_number is None:
        print("INFO: Not a PR context — skipping PR comment")
        return False

    repo = os.environ.get("GITHUB_REPOSITORY", "")
    sha = os.environ.get("GITHUB_SHA", "")[:8]
    run_id = os.environ.get("GITHUB_RUN_ID", "?")

    # Count totals
    total_findings = 0
    total_critical = 0
    scanners_ok = 0
    for data in results.values():
        if data.get("status") == "ok":
            scanners_ok += 1
            r = data["result"]
            total_findings += r.get("total_findings", r.get("findings_count", 0))
            total_critical += r.get("critical", 0)

    risk = _risk_level(total_critical, total_findings)
    risk_icon = {"critical": "🔴", "high": "🟠", "medium": "🟡", "low": "🟢"}.get(risk, "⚪")

    # Build comment body
    lines = [
        "<!-- agenticqa-ci-results -->",
        "## 🛡️ AgenticQA Security Scan",
        "",
        f"**Commit**: `{sha}` | **Run**: `{run_id}` | **Risk**: {risk_icon} **{risk.upper()}**",
        "",
        "| Metric | Value |",
        "|--------|-------|",
        f"| Scanners passed | **{scanners_ok}/{len(results)}** |",
        f"| Total findings | **{total_findings}** |",
        f"| Critical findings | **{total_critical}** |",
        f"| Scan time | {elapsed}s |",
    ]

    # Build system info
    if build_info.get("languages"):
        lines.append(f"| Detected languages | {', '.join(build_info['languages'])} |")

    lines.append("")

    # Delta section (if baseline available)
    if delta:
        new_total = sum(d.get("new_findings", 0) for d in delta.values())
        new_crit = sum(d.get("new_critical", 0) for d in delta.values())
        if new_total == 0 and new_crit == 0:
            lines += ["### ✅ No new findings introduced by this PR", ""]
        else:
            lines += [
                f"### ⚠️ New findings introduced: **{new_total}** ({new_crit} critical)",
                "",
                "| Scanner | New Findings | New Critical |",
                "|---------|-------------|-------------|",
            ]
            for name, d in delta.items():
                nf = d.get("new_findings", 0)
                nc = d.get("new_critical", 0)
                if nf > 0 or nc > 0:
                    lines.append(f"| {name} | +{nf} | +{nc} |")
            lines.append("")

    # Scanner breakdown
    lines += [
        "<details>",
        "<summary>Scanner breakdown</summary>",
        "",
        "| Scanner | Findings | Critical | Time |",
        "|---------|----------|----------|------|",
    ]
    for name, data in results.items():
        if data["status"] == "ok":
            r = data["result"]
            findings = r.get("total_findings", r.get("findings_count", 0))
            crit = r.get("critical", 0)
            icon = "🔴" if crit else "✅"
            lines.append(f"| {icon} {name} | {findings} | {crit} | {data['elapsed_s']}s |")
        else:
            lines.append(f"| ❌ {name} | ERROR | - | {data['elapsed_s']}s |")

    lines += ["", "</details>", ""]
    lines.append("*Posted by [AgenticQA](https://github.com/nhomyk/AgenticQA) — AI-powered security scanning*")

    body = "\n".join(lines)

    # Post via gh CLI
    env = dict(os.environ)
    env["GH_TOKEN"] = token

    base_args = ["gh", "pr", "comment", str(pr_number), "--body", body]
    if repo:
        base_args += ["--repo", repo]

    # Try update first, then create
    edit_proc = subprocess.run(
        base_args + ["--edit-last"],
        capture_output=True, text=True, timeout=30, env=env,
    )
    if edit_proc.returncode == 0:
        print(f"Updated AgenticQA comment on PR #{pr_number}")
        return True

    create_proc = subprocess.run(
        base_args,
        capture_output=True, text=True, timeout=30, env=env,
    )
    if create_proc.returncode == 0:
        print(f"Posted new AgenticQA comment on PR #{pr_number}")
        return True

    print(f"WARN: Failed to post PR comment: {create_proc.stderr[:300]}")
    return False


# ── Main ────────────────────────────────────────────────────────────────────


def main() -> int:
    scan_path = os.environ.get("AGENTICQA_SCAN_PATH", ".")
    output_file = os.environ.get("AGENTICQA_OUTPUT_FILE", "agenticqa-results.json")
    fail_on_critical = os.environ.get("AGENTICQA_FAIL_ON_CRITICAL", "true").lower() == "true"
    generate_sarif = os.environ.get("AGENTICQA_SARIF", "false").lower() == "true"
    sarif_file = os.environ.get("AGENTICQA_SARIF_FILE", "agenticqa.sarif")
    baseline_file = os.environ.get("AGENTICQA_BASELINE", "")
    pr_comment = os.environ.get("AGENTICQA_PR_COMMENT", "true").lower() == "true"

    # Resolve path
    repo_path = str(Path(scan_path).resolve())
    if not Path(repo_path).exists():
        print(f"::error::Scan path does not exist: {repo_path}")
        return 2

    # Detect build system
    build_info = detect_build_system(repo_path)
    lang_str = ", ".join(build_info["languages"]) if build_info["languages"] else "unknown"

    print(f"{'='*60}")
    print(f"  AgenticQA Security Scan")
    print(f"  Scanning: {repo_path}")
    print(f"  Detected: {lang_str}")
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
            "build_info": build_info,
        },
        "scanners": results,
    }

    # Delta scan
    baseline = _load_baseline(baseline_file)
    delta = None
    if baseline:
        delta = _compute_delta(output, baseline)
        output["summary"]["delta"] = delta
        new_findings = sum(d.get("new_findings", 0) for d in delta.values())
        new_critical = sum(d.get("new_critical", 0) for d in delta.values())
        output["summary"]["new_findings"] = new_findings
        output["summary"]["new_critical"] = new_critical
        print(f"\n  Delta vs baseline: +{new_findings} new findings, +{new_critical} new critical")

    # Write JSON results
    with open(output_file, "w") as f:
        json.dump(output, f, indent=2, default=str)

    # Set GitHub Action outputs
    _set_output("total_findings", str(total_findings))
    _set_output("critical_findings", str(total_critical))
    _set_output("scanners_ok", str(scanners_ok))
    _set_output("risk_level", risk)
    _set_output("result_file", output_file)
    _set_output("risk_color", _risk_color(risk))

    if build_info["languages"]:
        _set_output("detected_languages", ",".join(build_info["languages"]))

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
| Languages | {lang_str} |

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

    if delta:
        new_findings = sum(d.get("new_findings", 0) for d in delta.values())
        new_critical = sum(d.get("new_critical", 0) for d in delta.values())
        if new_findings == 0 and new_critical == 0:
            summary_md += "\n> **No new findings** introduced by this change.\n"
        else:
            summary_md += f"\n> **{new_findings} new findings** (+{new_critical} critical) vs baseline.\n"

    if total_critical > 0:
        summary_md += f"\n> **{total_critical} critical findings detected.** Review the full report in the artifacts.\n"

    _write_summary(summary_md)

    # Record scan for trend tracking
    try:
        from agenticqa.monitoring.scan_trend import ScanTrendAggregator
        repo_id = os.environ.get("GITHUB_REPOSITORY", repo_path)
        ScanTrendAggregator().record(output, repo_id=repo_id)
    except Exception:
        pass  # Non-blocking

    # Security benchmarking
    try:
        from agenticqa.scoring.security_benchmark import benchmark_scan
        bench = benchmark_scan(output)
        _set_output("security_grade", bench.grade)
        _set_output("security_percentile", str(bench.overall_percentile))
        print(f"\n  Benchmark: Grade {bench.grade} — {bench.comparison_text}")
    except Exception:
        pass

    # Post PR comment
    if pr_comment:
        try:
            _post_pr_comment(results, delta, build_info, elapsed)
        except Exception as e:
            print(f"WARN: PR comment failed: {e}")

    # Slack notification (if configured)
    try:
        from agenticqa.notifications.slack import SlackNotifier
        slack = SlackNotifier()
        if slack.configured:
            slack.notify_scan(output)
    except Exception:
        pass

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
