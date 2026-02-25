#!/usr/bin/env python3
"""
CI step: run semantic diff between base and head, post high-risk findings
as inline PR review comments via GitHub REST API.
"""
import argparse
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from agenticqa.diff.semantic_diff import SemanticDiffAnalyzer
from agenticqa.github.pr_commenter import PRCommenter


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base", default="HEAD~1")
    parser.add_argument("--head", default="HEAD")
    parser.add_argument("--pr-number", type=int, default=0)
    parser.add_argument("--repo", default="")
    parser.add_argument("--cwd", default=".")
    args = parser.parse_args()

    result = SemanticDiffAnalyzer().analyze_git_range(
        base=args.base, head=args.head, cwd=args.cwd
    )

    summary = result.summary()
    print(json.dumps({
        "risk_score": summary["risk_score"],
        "high_risk_count": summary["high_risk_count"],
        "medium_risk_count": summary["medium_risk_count"],
        "files_analyzed": summary["files_analyzed"],
    }, indent=2))

    if result.error:
        print(f"WARNING: {result.error}", file=sys.stderr)
        return 0

    # Only post inline comments for high-risk changes on real PRs
    if not args.pr_number or not os.getenv("GITHUB_TOKEN"):
        return 0

    high_risk = [c for c in result.changes if c.risk == "high"]
    if not high_risk:
        print("No high-risk changes — skipping inline comments.")
        return 0

    findings = [
        {
            "path": c.file,
            "line": c.line or 1,
            "body": f"**{c.detail}** (`{c.change_type}`)\n\nRemoved: `{c.removed_line}`",
            "severity": "error",
        }
        for c in high_risk
    ]

    commenter = PRCommenter(repo=args.repo)
    posted = commenter.post_inline_comments(
        args.pr_number,
        findings,
        commit_sha=args.head,
    )
    print(f"Posted {posted} inline semantic-diff comment(s).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
