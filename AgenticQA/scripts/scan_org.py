#!/usr/bin/env python3
"""
Batch-scan a GitHub org's public repos with AgenticQA agents.

Runs per-repo: SRE (linting) + Legal Risk + HIPAA + AI Act compliance.
Produces a ranked summary table at the end.

Usage:
    python scripts/scan_org.py --org dominodatalab --api http://localhost:8000
    python scripts/scan_org.py --org dominodatalab --max-repos 10 --workdir /tmp/domino-scans
"""
from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import textwrap
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import requests as _req


# ---------------------------------------------------------------------------
# GitHub helpers
# ---------------------------------------------------------------------------

def list_org_repos(org: str, languages: tuple[str, ...]) -> list[dict]:
    """Return active, non-fork public repos for *org* in the given languages."""
    repos: list[dict] = []
    page = 1
    while True:
        resp = _req.get(
            f"https://api.github.com/orgs/{org}/repos",
            params={"type": "public", "per_page": 100, "page": page},
            timeout=15,
        )
        resp.raise_for_status()
        batch = resp.json()
        if not batch:
            break
        repos.extend(batch)
        page += 1
        if len(batch) < 100:
            break

    filtered = [
        r for r in repos
        if not r["archived"]
        and not r["fork"]
        and r.get("language") in languages
    ]
    filtered.sort(key=lambda r: r["stargazers_count"], reverse=True)
    return filtered


def clone_or_update(clone_url: str, workdir: Path) -> Optional[Path]:
    """Shallow-clone the repo; return the local path, or None on failure."""
    name = clone_url.rstrip("/").rsplit("/", 1)[-1].replace(".git", "")
    dest = workdir / name
    if dest.exists():
        print(f"  [git] Updating {name}…", flush=True)
        r = subprocess.run(
            ["git", "-C", str(dest), "pull", "--ff-only", "-q"],
            capture_output=True, text=True, timeout=120,
        )
    else:
        print(f"  [git] Cloning {name}…", flush=True)
        r = subprocess.run(
            ["git", "clone", "--depth=1", "-q", clone_url, str(dest)],
            capture_output=True, text=True, timeout=180,
        )
    if r.returncode != 0:
        print(f"  [git] FAILED: {r.stderr.strip()[:120]}", flush=True)
        return None
    return dest


# ---------------------------------------------------------------------------
# Linting helpers
# ---------------------------------------------------------------------------

def _run_flake8(repo_path: Path, max_errors: int) -> list[dict]:
    result = subprocess.run(
        [
            "flake8",
            "--format=%(path)s::%(row)d::%(col)d::%(code)s::%(text)s",
            "--max-line-length=100",
            "--exclude=.git,__pycache__,.venv,venv,build,dist,node_modules,*.egg-info",
            str(repo_path),
        ],
        capture_output=True, text=True, timeout=120,
    )
    errors = []
    for line in result.stdout.splitlines():
        parts = line.split("::", 4)
        if len(parts) < 5:
            continue
        file_path, row, col, code, text = parts
        try:
            rel = str(Path(file_path).relative_to(repo_path))
        except ValueError:
            rel = file_path
        errors.append({"file": rel, "line": int(row), "col": int(col),
                        "rule": code.strip(), "message": text.strip()})
    return errors[:max_errors]


def _run_eslint(repo_path: Path, max_errors: int) -> list[dict]:
    subprocess.run(["npm", "install", "--silent"], cwd=repo_path,
                   capture_output=True, timeout=120)
    result = subprocess.run(
        ["npx", "eslint", ".", "--format=json",
         "--ext", ".js,.jsx,.ts,.tsx,.mjs,.cjs",
         "--ignore-pattern", "node_modules/",
         "--ignore-pattern", "dist/", "--ignore-pattern", "build/"],
        capture_output=True, text=True, timeout=180, cwd=repo_path,
    )
    errors = []
    try:
        data = json.loads(result.stdout or "[]")
    except json.JSONDecodeError:
        return []
    for file_result in data:
        file_path = file_result.get("filePath", "")
        try:
            rel = str(Path(file_path).relative_to(repo_path))
        except ValueError:
            rel = file_path
        for msg in file_result.get("messages", []):
            if not msg.get("ruleId"):
                continue
            errors.append({
                "file": rel, "line": msg.get("line", 0),
                "col": msg.get("column", 0), "rule": msg.get("ruleId", "unknown"),
                "message": msg.get("message", ""),
                "severity": "error" if msg.get("severity") == 2 else "warning",
            })
    return errors[:max_errors]


def collect_linting_errors(repo_path: Path, max_errors: int) -> tuple[list[dict], str]:
    is_js = (repo_path / "package.json").exists()
    if is_js:
        return _run_eslint(repo_path, max_errors), "eslint"
    return _run_flake8(repo_path, max_errors), "flake8"


# ---------------------------------------------------------------------------
# AgenticQA API calls
# ---------------------------------------------------------------------------

def call_sre(errors: list[dict], repo_path: Path, api: str) -> dict:
    payload = {
        "linting_data": {
            "errors": errors,
            "repo_path": str(repo_path),
            "source": "flake8",
        }
    }
    resp = _req.post(f"{api}/api/agents/execute", json=payload, timeout=120)
    resp.raise_for_status()
    data = resp.json()
    return data.get("results", {}).get("sre", data.get("results", {}))


def call_compliance(endpoint: str, repo_path: Path, api: str) -> dict:
    resp = _req.get(
        f"{api}/api/compliance/{endpoint}",
        params={"repo_path": str(repo_path)},
        timeout=60,
    )
    if resp.status_code == 200:
        return resp.json()
    return {"error": f"HTTP {resp.status_code}", "status": "failed"}


def call_redteam(api: str, mode: str = "fast") -> dict:
    resp = _req.post(
        f"{api}/api/red-team/scan",
        json={"mode": mode, "target": "both", "auto_patch": False},
        timeout=120,
    )
    if resp.status_code == 200:
        return resp.json()
    return {"error": f"HTTP {resp.status_code}", "status": "failed"}


# ---------------------------------------------------------------------------
# Result container
# ---------------------------------------------------------------------------

@dataclass
class RepoScanResult:
    name: str
    language: str
    stars: int
    total_errors: int = 0
    fixes_applied: int = 0
    fix_rate: float = 0.0
    arch_violations: int = 0
    legal_issues: int = 0
    hipaa_violations: int = 0
    ai_act_score: float = -1.0
    ai_act_risk: str = "unknown"
    error: str = ""
    top_rules: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Printing helpers
# ---------------------------------------------------------------------------

def _fmt_score(score: float) -> str:
    if score < 0:
        return "N/A"
    bar = "█" * int(score * 10) + "░" * (10 - int(score * 10))
    return f"{bar} {score:.2f}"


def print_summary(results: list[RepoScanResult]) -> None:
    SEP = "─" * 110
    print(f"\n\n{'═' * 110}")
    print("  AgenticQA Full Scan — dominodatalab org summary")
    print(f"{'═' * 110}\n")

    print(f"  {'Repo':<42}  {'Lang':<7}  {'★':>3}  {'Errors':>7}  {'Fixes':>6}  "
          f"{'Fix%':>5}  {'Arch':>4}  {'Legal':>5}  {'HIPAA':>5}  {'AI Act':<16}")
    print(f"  {SEP}")
    for r in sorted(results, key=lambda x: x.total_errors, reverse=True):
        if r.error:
            print(f"  {r.name:<42}  {'ERR':>7} — {r.error[:50]}")
            continue
        print(
            f"  {r.name:<42}  {r.language:<7}  {r.stars:>3}  "
            f"{r.total_errors:>7}  {r.fixes_applied:>6}  "
            f"{r.fix_rate:>5.1%}  {r.arch_violations:>4}  "
            f"{r.legal_issues:>5}  {r.hipaa_violations:>5}  "
            f"{r.ai_act_risk:<10} {r.ai_act_score:>5.2f}"
            if r.ai_act_score >= 0
            else f"  {r.name:<42}  {r.language:<7}  {r.stars:>3}  "
                 f"{r.total_errors:>7}  {r.fixes_applied:>6}  "
                 f"{r.fix_rate:>5.1%}  {r.arch_violations:>4}  "
                 f"{r.legal_issues:>5}  {r.hipaa_violations:>5}  "
                 f"{'N/A':<16}"
        )
        if r.top_rules:
            rules_str = ", ".join(r.top_rules[:5])
            print(f"  {'':42}  top rules: {rules_str}")

    print(f"\n  {SEP}")
    totals = RepoScanResult(name="TOTALS", language="", stars=0)
    for r in results:
        if not r.error:
            totals.total_errors += r.total_errors
            totals.fixes_applied += r.fixes_applied
            totals.arch_violations += r.arch_violations
            totals.legal_issues += r.legal_issues
            totals.hipaa_violations += r.hipaa_violations
    ok = [r for r in results if not r.error]
    totals.fix_rate = (totals.fixes_applied / max(totals.total_errors, 1))
    print(
        f"  {'TOTALS (' + str(len(ok)) + ' repos)':<42}  {'':>7}  {'':>3}  "
        f"{totals.total_errors:>7}  {totals.fixes_applied:>6}  "
        f"{totals.fix_rate:>5.1%}  {totals.arch_violations:>4}  "
        f"{totals.legal_issues:>5}  {totals.hipaa_violations:>5}"
    )
    print(f"{'═' * 110}\n")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

TARGET_LANGS = ("Python", "JavaScript", "TypeScript")

PRIORITY_REPOS = [
    "python-domino",
    "cucu",
    "domino-data",
    "domino-MLops-flows",
    "python-domino-environments",
    "domino_mcp_server",
    "domino-claude-plugin",
    "rag-agent-demo",
    "qa_mcp_server",
    "Workspace-File-Audit-Application",
    "dashboard-workshop",
]


def main() -> int:
    parser = argparse.ArgumentParser(description="Batch-scan a GitHub org with AgenticQA")
    parser.add_argument("--org", default="dominodatalab")
    parser.add_argument("--api", default="http://localhost:8000")
    parser.add_argument("--workdir", default="/tmp/domino-scans")
    parser.add_argument("--max-repos", type=int, default=15)
    parser.add_argument("--max-errors", type=int, default=300)
    parser.add_argument("--redteam", action="store_true", help="Run red-team scan at end")
    args = parser.parse_args()

    workdir = Path(args.workdir)
    workdir.mkdir(parents=True, exist_ok=True)

    # 1. Enumerate repos
    print(f"[1/4] Fetching public repos for {args.org}…", flush=True)
    try:
        all_repos = list_org_repos(args.org, TARGET_LANGS)
    except Exception as exc:
        print(f"ERROR fetching repos: {exc}")
        return 1

    # Prioritize known interesting repos, then fill by stars
    priority_set = set(PRIORITY_REPOS)
    priority = [r for r in all_repos if r["name"] in priority_set]
    rest = [r for r in all_repos if r["name"] not in priority_set]
    repos_to_scan = (priority + rest)[: args.max_repos]
    print(f"  Scanning {len(repos_to_scan)} repos (out of {len(all_repos)} {'/'.join(TARGET_LANGS)})", flush=True)

    # 2. Clone
    print(f"\n[2/4] Cloning repos to {workdir}…", flush=True)
    local_repos: list[tuple[dict, Path]] = []
    for repo in repos_to_scan:
        local = clone_or_update(repo["clone_url"], workdir)
        if local:
            local_repos.append((repo, local))

    # 3. Scan
    print(f"\n[3/4] Running AgenticQA agents on {len(local_repos)} repos…", flush=True)
    results: list[RepoScanResult] = []

    for repo_meta, repo_path in local_repos:
        name = repo_meta["name"]
        lang = repo_meta.get("language") or "Python"
        stars = repo_meta["stargazers_count"]
        result = RepoScanResult(name=name, language=lang, stars=stars)

        print(f"\n  ── {name} ({lang}, {stars}★) ──", flush=True)

        # --- SRE ---
        print("    SRE linting…", flush=True)
        try:
            errors, linter = collect_linting_errors(repo_path, args.max_errors)
            print(f"      {linter}: {len(errors)} issues", flush=True)
            if errors:
                sre = call_sre(errors, repo_path, args.api)
                result.total_errors = sre.get("total_errors", len(errors))
                result.fixes_applied = sre.get("fixes_applied", 0)
                result.fix_rate = sre.get("fix_rate", 0.0)
                result.arch_violations = sre.get("architectural_violations", 0)
                # top rules
                rule_counts: dict[str, int] = {}
                for e in errors:
                    rule_counts[e.get("rule", "?")] = rule_counts.get(e.get("rule", "?"), 0) + 1
                result.top_rules = [r for r, _ in sorted(rule_counts.items(), key=lambda x: -x[1])[:5]]
                print(f"      fixes={result.fixes_applied} fix_rate={result.fix_rate:.1%} arch={result.arch_violations}", flush=True)
            else:
                print("      clean — no linting issues", flush=True)
        except Exception as exc:
            print(f"      SRE error: {exc}", flush=True)

        # --- Legal Risk ---
        print("    Compliance: legal-risk…", flush=True)
        try:
            lr = call_compliance("legal-risk", repo_path, args.api)
            findings = lr.get("findings", []) or lr.get("violations", []) or lr.get("risks", [])
            result.legal_issues = len(findings)
            print(f"      legal findings: {result.legal_issues}", flush=True)
        except Exception as exc:
            print(f"      legal-risk error: {exc}", flush=True)

        # --- HIPAA ---
        print("    Compliance: HIPAA…", flush=True)
        try:
            hipaa = call_compliance("hipaa", repo_path, args.api)
            violations = hipaa.get("violations", []) or hipaa.get("findings", [])
            result.hipaa_violations = len(violations)
            print(f"      HIPAA violations: {result.hipaa_violations}", flush=True)
        except Exception as exc:
            print(f"      HIPAA error: {exc}", flush=True)

        # --- AI Act ---
        print("    Compliance: AI Act…", flush=True)
        try:
            ai_act = call_compliance("ai-act", repo_path, args.api)
            result.ai_act_score = ai_act.get("conformity_score", -1.0)
            result.ai_act_risk = ai_act.get("risk_level", ai_act.get("risk_category", "unknown"))
            print(f"      AI Act conformity={result.ai_act_score:.2f} risk={result.ai_act_risk}", flush=True)
        except Exception as exc:
            print(f"      AI Act error: {exc}", flush=True)

        results.append(result)

    # 4. Optional red-team
    if args.redteam:
        print("\n[4/4] Running red-team adversarial scan…", flush=True)
        try:
            rt = call_redteam(args.api, mode="thorough")
            bypasses = rt.get("successful_bypasses", 0)
            scanner_str = rt.get("scanner_strength", 0)
            gate_str = rt.get("gate_strength", 0)
            print(f"  Red Team: bypasses={bypasses} scanner={scanner_str:.0%} gate={gate_str:.0%}")
        except Exception as exc:
            print(f"  Red Team error: {exc}")
    else:
        print("\n[4/4] Skipping red-team (pass --redteam to enable)", flush=True)

    # 5. Summary
    print_summary(results)

    # Write JSON report
    report_path = Path(args.workdir) / "scan_report.json"
    report_data = [
        {k: v for k, v in r.__dict__.items()}
        for r in results
    ]
    report_path.write_text(json.dumps(report_data, indent=2))
    print(f"  Full JSON report: {report_path}\n")

    return 0


if __name__ == "__main__":
    sys.exit(main())
