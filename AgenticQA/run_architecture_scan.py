#!/usr/bin/env python3
"""
Architecture Scanner CLI

Walks a repository and maps all integration points, attack surfaces,
and test coverage — in plain English anyone can understand.

Usage:
    python run_architecture_scan.py /path/to/repo
    python run_architecture_scan.py . --json
    python run_architecture_scan.py . --category SHELL_EXEC
    python run_architecture_scan.py . --untested-only
    python run_architecture_scan.py . --min-severity high
    python run_architecture_scan.py . --save
"""

import argparse
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "src"))

# ANSI colours
_RED    = "\033[91m"
_YELLOW = "\033[93m"
_CYAN   = "\033[96m"
_GREEN  = "\033[92m"
_BOLD   = "\033[1m"
_RESET  = "\033[0m"
_DIM    = "\033[2m"

_SEV_COLOUR = {
    "critical": _RED + _BOLD,
    "high":     _RED,
    "medium":   _YELLOW,
    "low":      _CYAN,
}

_SEV_ORDER = {"critical": 0, "high": 1, "medium": 2, "low": 3}


def _colour(sev: str, text: str) -> str:
    return f"{_SEV_COLOUR.get(sev, '')}{text}{_RESET}"


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Architecture Scanner — map integration areas and attack surface in any repo",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python run_architecture_scan.py /tmp/XcodeBuildMCP
  python run_architecture_scan.py . --json
  python run_architecture_scan.py . --category SHELL_EXEC --untested-only
  python run_architecture_scan.py . --min-severity high
""",
    )
    parser.add_argument("repo_path", nargs="?", default=".", help="Path to repository (default: .)")
    parser.add_argument("--json", action="store_true", help="Output raw JSON instead of table")
    parser.add_argument("--category", metavar="CAT", help="Filter to a single category (e.g. SHELL_EXEC)")
    parser.add_argument("--untested-only", action="store_true", help="Show only areas with no test coverage")
    parser.add_argument("--min-severity", metavar="SEV", default="low",
                        choices=["critical", "high", "medium", "low"],
                        help="Minimum severity to display (default: low)")
    parser.add_argument("--save", action="store_true", help="Save results to artifact store")
    args = parser.parse_args()

    from agenticqa.security.architecture_scanner import ArchitectureScanner

    repo = args.repo_path
    print(f"{_BOLD}Scanning {repo} …{_RESET}", flush=True)

    result = ArchitectureScanner().scan(repo)

    if args.json:
        print(json.dumps(result.to_dict(), indent=2))
        return

    if result.scan_error:
        print(f"{_RED}Scan error: {result.scan_error}{_RESET}")
        sys.exit(1)

    # ── Filter ────────────────────────────────────────────────────────────────
    areas = result.integration_areas
    if args.category:
        areas = [a for a in areas if a.category == args.category.upper()]
    if args.untested_only:
        areas = [a for a in areas if not a.test_files]
    min_sev_order = _SEV_ORDER.get(args.min_severity, 3)
    areas = [a for a in areas if _SEV_ORDER.get(a.severity, 3) <= min_sev_order]

    # Sort: critical → high → medium → low, then by file
    areas = sorted(areas, key=lambda a: (_SEV_ORDER.get(a.severity, 3), a.source_file, a.line_number))

    # ── Header ────────────────────────────────────────────────────────────────
    print()
    print(f"{_BOLD}{'=' * 70}{_RESET}")
    print(f"{_BOLD}  ARCHITECTURE SCAN — {result.repo_path}{_RESET}")
    print(f"{'=' * 70}")
    print(f"  Files scanned:              {result.files_scanned}")
    print(f"  Integration areas found:    {len(result.integration_areas)}")
    print(f"  Attack surface score:       {_colour('critical' if result.attack_surface_score > 60 else 'medium', f'{result.attack_surface_score:.0f}/100')}")
    print(f"  Test coverage confidence:   {_colour('low' if result.test_coverage_confidence < 40 else 'medium', f'{result.test_coverage_confidence:.0f}%')}")
    print(f"  Untested areas:             {len(result.untested_areas)}")
    print()

    if not areas:
        print(f"  {_GREEN}No integration areas match the selected filters.{_RESET}")
        return

    # ── Category summary ──────────────────────────────────────────────────────
    print(f"{_BOLD}  CATEGORY SUMMARY{_RESET}")
    print(f"  {'-' * 66}")
    cats = result.by_category()
    for cat, cat_areas in sorted(cats.items(), key=lambda x: (_SEV_ORDER.get(x[1][0].severity, 3), -len(x[1]))):
        sev = cat_areas[0].severity
        tested = sum(1 for a in cat_areas if a.test_files)
        bar = f"{tested}/{len(cat_areas)} tested"
        print(f"  {_colour(sev, f'[{sev.upper():8s}]')} {cat:20s}  {len(cat_areas):3d} area(s)   {bar}")
    print()

    # ── Detail table ──────────────────────────────────────────────────────────
    print(f"{_BOLD}  INTEGRATION AREAS{_RESET}")
    print(f"  {'-' * 66}")
    prev_cat = None
    for a in areas:
        if a.category != prev_cat:
            print()
            print(f"  {_colour(a.severity, _BOLD + a.category + _RESET)}")
            print(f"  {_DIM}{a.plain_english}{_RESET}")
            print(f"  {_DIM}Vectors: {', '.join(a.attack_vectors[:3])}  |  {a.cwe}{_RESET}")
            print()
            prev_cat = a.category

        tested_str = (f"{_GREEN}[tested]{_RESET}" if a.test_files
                      else f"{_RED}[no tests]{_RESET}")
        print(f"    {_colour(a.severity, f'●')}"
              f" {a.source_file}:{a.line_number}  {tested_str}")
        print(f"      {_DIM}{a.evidence[:100]}{_RESET}")
        if a.test_files:
            for tf in a.test_files[:2]:
                print(f"      {_GREEN}↳ {tf}{_RESET}")

    print()
    print(f"{'=' * 70}")

    # ── Untested high-risk summary ─────────────────────────────────────────────
    untested_critical = [a for a in result.untested_areas if a.severity in ("critical", "high")]
    if untested_critical:
        print(f"\n{_RED}{_BOLD}  ⚠  {len(untested_critical)} CRITICAL/HIGH INTEGRATION AREAS HAVE NO TESTS{_RESET}")
        for a in untested_critical[:10]:
            print(f"     • [{a.severity.upper()}] {a.category} — {a.source_file}:{a.line_number}")
        print()

    # ── Save ──────────────────────────────────────────────────────────────────
    if args.save:
        try:
            from data_store.artifact_store import TestArtifactStore
            store = TestArtifactStore(os.getenv("AGENTICQA_ARTIFACT_STORE", ".test-artifact-store"))
            store.store_artifact(
                artifact_data={
                    "artifact_type": "architecture_scan",
                    **result.to_dict(),
                },
                artifact_type="architecture_scan",
                source=repo,
                tags=["architecture", "security"],
            )
            print(f"  {_GREEN}Results saved to artifact store.{_RESET}")
        except Exception as exc:
            print(f"  {_YELLOW}Could not save to artifact store: {exc}{_RESET}")


if __name__ == "__main__":
    main()
