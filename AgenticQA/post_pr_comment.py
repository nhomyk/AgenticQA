#!/usr/bin/env python3
"""
Aggregate CI agent outputs into a structured GitHub PR comment.

Reads JSON result files written by individual agent jobs, assembles a
CIResultBundle, and calls PRCommenter.post_results().

Designed to be the final step in the CI pipeline on pull_request events.
All input files are optional — absent/malformed files are silently skipped.

Usage:
    python post_pr_comment.py --run-id $GITHUB_RUN_ID --commit-sha $GITHUB_SHA
    python post_pr_comment.py --pr-number 42 --redteam-json redteam-output.json
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "src"))


def load_json(path: str) -> dict:
    """Load a JSON file, returning an empty dict if the file is absent or malformed."""
    try:
        p = Path(path)
        if p.exists():
            return json.loads(p.read_text())
    except Exception:
        pass
    return {}


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Post AgenticQA CI results as a PR comment"
    )
    parser.add_argument("--pr-number", type=int, default=None)
    parser.add_argument("--run-id", default=os.getenv("GITHUB_RUN_ID", "unknown"))
    parser.add_argument("--commit-sha", default=os.getenv("GITHUB_SHA", "unknown"))
    # Per-agent result files (all optional)
    parser.add_argument("--redteam-json", default="redteam-output.json")
    parser.add_argument("--sdet-json", default="sdet-output.json")
    parser.add_argument("--compliance-json", default="compliance-output.json")
    parser.add_argument("--sre-json", default="sre-output.json")
    parser.add_argument("--qa-json", default="qa-output.json")
    args = parser.parse_args()

    redteam = load_json(args.redteam_json)
    sdet = load_json(args.sdet_json)
    compliance = load_json(args.compliance_json)
    sre = load_json(args.sre_json)
    qa = load_json(args.qa_json)

    from agenticqa.github.pr_commenter import CIResultBundle, PRCommenter

    bundle = CIResultBundle(
        run_id=args.run_id,
        commit_sha=args.commit_sha,
        # QA
        total_tests=qa.get("total_tests"),
        tests_passed=qa.get("passed"),
        tests_failed=qa.get("failed"),
        # SDET / Coverage
        coverage_percent=sdet.get("current_coverage"),
        coverage_status=sdet.get("coverage_status"),
        tests_generated=sdet.get("tests_generated"),
        # SRE
        sre_total_errors=sre.get("total_errors"),
        sre_fix_rate=sre.get("fix_rate"),
        sre_fixes_applied=sre.get("fixes_applied"),
        # Red Team
        scanner_strength=redteam.get("scanner_strength"),
        gate_strength=redteam.get("gate_strength"),
        successful_bypasses=redteam.get("successful_bypasses"),
        # Compliance
        compliance_violations=len(compliance.get("violations", [])) if compliance else None,
        data_encryption=compliance.get("data_encryption"),
        reachable_cves=compliance.get("reachable_cves"),
        cve_risk_score=compliance.get("cve_risk_score"),
    )

    commenter = PRCommenter()
    success = commenter.post_results(bundle, pr_number=args.pr_number)
    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(main())
