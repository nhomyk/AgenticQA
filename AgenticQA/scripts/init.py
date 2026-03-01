#!/usr/bin/env python3
"""AgenticQA onboarding CLI — one-command setup for any repository.

Usage:
    python -m agenticqa.init          # Run from inside a repo
    python scripts/init.py            # Direct execution
    curl -sL <url> | python3 -        # Remote one-liner (future)

What it does:
    1. Detects project language and build system
    2. Creates .github/workflows/agenticqa-scan.yml
    3. Adds a scan status badge to README.md
    4. Runs a first scan and shows results
    5. Optionally creates a PR with the setup
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import textwrap
from pathlib import Path

# Ensure src/ is importable when running directly
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))
sys.path.insert(0, str(Path(__file__).parent.parent))


def _detect_languages(repo_path: Path) -> list[str]:
    """Quick language detection from project files."""
    langs = []
    if (repo_path / "pyproject.toml").exists() or (repo_path / "setup.py").exists() or (repo_path / "requirements.txt").exists():
        langs.append("Python")
    if (repo_path / "package.json").exists():
        langs.append("TypeScript" if (repo_path / "tsconfig.json").exists() else "JavaScript")
    if (repo_path / "go.mod").exists():
        langs.append("Go")
    if (repo_path / "Cargo.toml").exists():
        langs.append("Rust")
    if (repo_path / "composer.json").exists():
        langs.append("PHP")
    if (repo_path / "Gemfile").exists():
        langs.append("Ruby")
    if (repo_path / "pom.xml").exists() or (repo_path / "build.gradle").exists():
        langs.append("Java")
    if list(repo_path.glob("*.csproj")) or list(repo_path.glob("*.sln")):
        langs.append(".NET")
    return langs or ["Unknown"]


def _get_repo_slug() -> str:
    """Get owner/repo from git remote."""
    try:
        result = subprocess.run(
            ["git", "remote", "get-url", "origin"],
            capture_output=True, text=True, timeout=5,
        )
        url = result.stdout.strip()
        # Parse github.com/owner/repo from various URL formats
        for prefix in ("https://github.com/", "git@github.com:"):
            if prefix in url:
                slug = url.split(prefix)[-1].removesuffix(".git")
                return slug
    except Exception:
        pass
    return ""


def _create_workflow(repo_path: Path, fail_on_critical: bool = False) -> Path:
    """Create the GitHub Actions workflow file."""
    workflow_dir = repo_path / ".github" / "workflows"
    workflow_dir.mkdir(parents=True, exist_ok=True)
    workflow_file = workflow_dir / "agenticqa-scan.yml"

    fail_str = "true" if fail_on_critical else "false"

    content = textwrap.dedent(f"""\
        name: AgenticQA Security Scan

        on:
          push:
            branches: [main, master]
          pull_request:
            branches: [main, master]

        permissions:
          contents: read
          pull-requests: write
          security-events: write

        jobs:
          security-scan:
            runs-on: ubuntu-latest
            steps:
              - uses: actions/checkout@v4

              # Restore baseline for delta scanning on PRs
              - name: Restore scan baseline
                if: github.event_name == 'pull_request'
                uses: actions/cache/restore@v4
                with:
                  path: agenticqa-baseline.json
                  key: agenticqa-baseline-${{{{ github.event.pull_request.base.sha }}}}
                  restore-keys: agenticqa-baseline-
                continue-on-error: true

              - name: Run AgenticQA scan
                uses: nhomyk/AgenticQA@main
                with:
                  fail-on-critical: '{fail_str}'
                  sarif: 'true'
                  pr-comment: 'true'
                  baseline: agenticqa-baseline.json
    """)

    workflow_file.write_text(content)
    return workflow_file


def _add_badge_to_readme(repo_path: Path) -> bool:
    """Add AgenticQA badge to the top of README.md if not already present."""
    readme = None
    for name in ("README.md", "readme.md", "Readme.md"):
        candidate = repo_path / name
        if candidate.exists():
            readme = candidate
            break

    if readme is None:
        return False

    content = readme.read_text()
    if "agenticqa" in content.lower() and "badge" in content.lower():
        return False  # Badge already present

    repo_slug = _get_repo_slug()
    if repo_slug:
        badge_line = (
            f"[![AgenticQA Security Scan]"
            f"(https://github.com/{repo_slug}/actions/workflows/agenticqa-scan.yml/badge.svg)]"
            f"(https://github.com/{repo_slug}/actions/workflows/agenticqa-scan.yml)"
        )
    else:
        badge_line = "![AgenticQA](https://img.shields.io/badge/AgenticQA-scanned-brightgreen)"

    # Insert badge after the first heading, or at the top
    lines = content.split("\n")
    insert_idx = 0
    for i, line in enumerate(lines):
        if line.startswith("# "):
            insert_idx = i + 1
            break

    # Skip any existing badge lines right after the heading
    while insert_idx < len(lines) and (
        lines[insert_idx].startswith("[![") or lines[insert_idx].startswith("![") or lines[insert_idx].strip() == ""
    ):
        insert_idx += 1

    lines.insert(insert_idx, "")
    lines.insert(insert_idx, badge_line)

    readme.write_text("\n".join(lines))
    return True


def _run_first_scan(repo_path: Path) -> dict | None:
    """Run the initial scan and return results."""
    try:
        scan_script = Path(__file__).parent / "run_client_scan.py"
        if not scan_script.exists():
            # Try installed package
            from agenticqa.scripts import run_client_scan
            scan_script = Path(run_client_scan.__file__)

        result = subprocess.run(
            [sys.executable, str(scan_script), str(repo_path), "--json"],
            capture_output=True, text=True, timeout=120,
        )
        if result.returncode <= 1 and result.stdout.strip():
            return json.loads(result.stdout)
    except Exception:
        pass
    return None


def main() -> int:
    import argparse
    parser = argparse.ArgumentParser(
        description="Initialize AgenticQA security scanning for your repository"
    )
    parser.add_argument("path", nargs="?", default=".", help="Repository path (default: current dir)")
    parser.add_argument("--fail-on-critical", action="store_true",
                        help="Configure workflow to fail on critical findings")
    parser.add_argument("--no-badge", action="store_true", help="Skip adding badge to README")
    parser.add_argument("--no-scan", action="store_true", help="Skip initial scan")
    parser.add_argument("--no-workflow", action="store_true", help="Skip workflow creation")
    args = parser.parse_args()

    repo_path = Path(args.path).resolve()
    if not repo_path.exists():
        print(f"Error: {repo_path} does not exist")
        return 1

    print()
    print("=" * 60)
    print("  AgenticQA — Setup Wizard")
    print("=" * 60)
    print()

    # 1. Detect project
    languages = _detect_languages(repo_path)
    print(f"  Detected languages: {', '.join(languages)}")
    repo_slug = _get_repo_slug()
    if repo_slug:
        print(f"  GitHub repo: {repo_slug}")
    print()

    steps_done = []

    # 2. Create workflow
    if not args.no_workflow:
        workflow_file = _create_workflow(repo_path, args.fail_on_critical)
        rel = workflow_file.relative_to(repo_path)
        print(f"  [+] Created {rel}")
        steps_done.append("workflow")
    else:
        print("  [~] Skipped workflow creation")

    # 3. Add badge
    if not args.no_badge:
        if _add_badge_to_readme(repo_path):
            print("  [+] Added scan badge to README.md")
            steps_done.append("badge")
        else:
            print("  [~] Badge already present or no README found")
    else:
        print("  [~] Skipped badge")

    # 4. Run first scan
    if not args.no_scan:
        print()
        print("  Running initial scan...")
        scan_result = _run_first_scan(repo_path)
        if scan_result:
            summary = scan_result.get("summary", {})
            ok = summary.get("scanners_ok", 0)
            total = ok + summary.get("scanners_failed", 0)
            findings = summary.get("total_findings", 0)
            critical = summary.get("total_critical", 0)
            print(f"  [+] Scan complete: {ok}/{total} scanners OK, {findings} findings, {critical} critical")
            steps_done.append("scan")

            # Save results for reference
            results_file = repo_path / "agenticqa-results.json"
            with open(results_file, "w") as f:
                json.dump(scan_result, f, indent=2, default=str)
            print(f"  [+] Results saved to agenticqa-results.json")
        else:
            print("  [!] Initial scan failed — you can run it manually later")
    else:
        print("  [~] Skipped initial scan")

    # Summary
    print()
    print("=" * 60)
    print("  Setup complete!")
    print()
    if "workflow" in steps_done:
        print("  Next steps:")
        print("    1. git add .github/workflows/agenticqa-scan.yml")
        if "badge" in steps_done:
            print("    2. git add README.md")
        print(f"    {'3' if 'badge' in steps_done else '2'}. git commit -m 'chore: add AgenticQA security scanning'")
        print(f"    {'4' if 'badge' in steps_done else '3'}. git push")
        print()
        print("  AgenticQA will automatically scan every push and PR!")
    print("=" * 60)
    print()

    return 0


if __name__ == "__main__":
    sys.exit(main())
