#!/usr/bin/env python3
"""
Run the AgenticQA SRE agent on a local git repo.

Auto-detects language:
  - Python repos  → flake8
  - JS/TS repos   → npx eslint --format=json (ESLint already handled by normalize_linting_input)

Usage:
    python scripts/run_sre_on_repo.py /tmp/requests
    python scripts/run_sre_on_repo.py /tmp/express --api http://localhost:8000
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

import requests as _req


def _is_js_repo(repo_path: Path) -> bool:
    return (repo_path / "package.json").exists()


def run_flake8(repo_path: Path, max_errors: int = 200) -> list[dict]:
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
        errors.append({
            "file": str(Path(file_path).relative_to(repo_path)),
            "line": int(row), "col": int(col),
            "rule": code.strip(), "message": text.strip(),
        })
    print(f"  flake8 found {len(errors)} errors", flush=True)
    return errors[:max_errors]


def run_eslint(repo_path: Path, max_errors: int = 200) -> list[dict]:
    """Run ESLint with --format=json and normalise to SRE internal format."""
    # Install deps if needed (best-effort, silent)
    subprocess.run(["npm", "install", "--silent"], cwd=repo_path,
                   capture_output=True, timeout=120)
    result = subprocess.run(
        ["npx", "eslint", ".", "--format=json",
         "--ext", ".js,.jsx,.ts,.tsx,.mjs,.cjs",
         "--ignore-pattern", "node_modules/",
         "--ignore-pattern", "dist/",
         "--ignore-pattern", "build/"],
        capture_output=True, text=True, timeout=180, cwd=repo_path,
    )
    errors = []
    try:
        data = json.loads(result.stdout or "[]")
    except json.JSONDecodeError:
        print(f"  ESLint produced no JSON output (exit {result.returncode})", flush=True)
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
                "file": rel,
                "line": msg.get("line", 0),
                "col": msg.get("column", 0),
                "rule": msg.get("ruleId", "unknown"),
                "message": msg.get("message", ""),
                "severity": "error" if msg.get("severity") == 2 else "warning",
            })
    print(f"  ESLint found {len(errors)} errors/warnings", flush=True)
    return errors[:max_errors]


def post_to_sre(errors: list[dict], repo_path: Path, api_base: str) -> dict:
    """Submit errors to the SRE agent and return the result."""
    payload = {
        "linting_data": {
            "errors": errors,
            "repo_path": str(repo_path),
            "source": "flake8",
        }
    }
    resp = _req.post(
        f"{api_base}/api/agents/execute",
        json=payload,
        timeout=120,
    )
    resp.raise_for_status()
    data = resp.json()
    return data.get("results", {}).get("sre", data)


def fetch_profiles(api_base: str, repo_path: Path, top_n: int = 20) -> list[dict]:
    resp = _req.get(
        f"{api_base}/api/developer-profiles",
        params={"repo_path": str(repo_path), "top_n": top_n},
        timeout=15,
    )
    resp.raise_for_status()
    return resp.json().get("leaderboard", [])


def main() -> int:
    parser = argparse.ArgumentParser(description="Run SRE agent on a local git repo")
    parser.add_argument("repo_path", help="Path to the git repo root")
    parser.add_argument("--api", default="http://localhost:8000", help="API base URL")
    parser.add_argument("--max-errors", type=int, default=200)
    parser.add_argument("--top-n", type=int, default=15, help="Top-N developer profiles to show")
    args = parser.parse_args()

    repo_path = Path(args.repo_path).resolve()
    if not (repo_path / ".git").exists():
        print(f"ERROR: {repo_path} is not a git repository")
        return 1

    print(f"\n{'='*60}")
    js = _is_js_repo(repo_path)
    print(f"  Repo: {repo_path.name}  ({'JS/TS' if js else 'Python'})")
    print(f"{'='*60}")

    # 1. Lint
    if js:
        print("[ 1/3 ] Running ESLint...", flush=True)
        errors = run_eslint(repo_path, max_errors=args.max_errors)
    else:
        print("[ 1/3 ] Running flake8...", flush=True)
        errors = run_flake8(repo_path, max_errors=args.max_errors)
    if not errors:
        print("  No linting errors found — nothing to do.")
        return 0

    # 2. SRE agent
    print(f"[ 2/3 ] Submitting {len(errors)} errors to SRE agent...", flush=True)
    try:
        result = post_to_sre(errors, repo_path, args.api)
    except Exception as exc:
        print(f"  ERROR calling SRE agent: {exc}")
        return 1

    fixes_applied = result.get("fixes_applied", 0)
    fix_rate = result.get("fix_rate", 0.0)
    arch_violations = result.get("architectural_violations", 0)
    print(f"  fixes_applied={fixes_applied}  fix_rate={fix_rate:.1%}  arch_violations={arch_violations}")

    # 3. Developer profiles
    print("[ 3/3 ] Fetching developer risk profiles...", flush=True)
    try:
        profiles = fetch_profiles(args.api, repo_path, top_n=args.top_n)
    except Exception as exc:
        print(f"  Could not fetch profiles: {exc}")
        profiles = []

    if profiles:
        print(f"\n  Top {len(profiles)} developers by risk score:")
        print(f"  {'Dev Hash':<14}  {'Risk':>6}  {'Violations':>10}  {'Fixes':>6}")
        print(f"  {'-'*14}  {'-'*6}  {'-'*10}  {'-'*6}")
        for p in profiles:
            print(
                f"  {p['dev_hash']:<14}  {p['risk_score']:>6.3f}  "
                f"{p['total_violations']:>10}  {p['total_fixes']:>6}"
            )
    else:
        print("  No profiles found (git blame may not have matched any files).")

    print()
    return 0


if __name__ == "__main__":
    sys.exit(main())
