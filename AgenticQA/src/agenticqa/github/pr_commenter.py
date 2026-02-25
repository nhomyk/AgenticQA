"""
PR comment poster for AgenticQA CI results.

Posts or updates a single structured comment on a GitHub PR with results from all agents.
Uses GITHUB_TOKEN + gh CLI to post — no GitHub App registration required.

Key behaviour:
- Uses `gh pr comment --edit-last` to upsert: one comment per pipeline, updated on reruns
- Falls back to creating a new comment if no previous AgenticQA comment exists
- Gracefully skips if GITHUB_TOKEN is absent or the trigger is not a PR event
- `permissions: pull-requests: write` required in the CI job that calls this
"""
from __future__ import annotations

import json
import os
import subprocess
from dataclasses import dataclass, field
from typing import Optional

# Embedded in every comment body — gh uses this to find the comment to edit
_COMMENT_MARKER = "<!-- agenticqa-ci-results -->"


@dataclass
class CIResultBundle:
    """Aggregated CI results from all agents for one pipeline run."""

    run_id: str
    commit_sha: str

    # QA / test results
    total_tests: Optional[int] = None
    tests_passed: Optional[int] = None
    tests_failed: Optional[int] = None

    # Coverage (SDET)
    coverage_percent: Optional[float] = None
    coverage_status: Optional[str] = None    # "adequate" | "insufficient"
    tests_generated: Optional[int] = None   # LLM-generated tests added this run

    # SRE / linting
    sre_total_errors: Optional[int] = None
    sre_fix_rate: Optional[float] = None
    sre_fixes_applied: Optional[int] = None

    # Red Team
    scanner_strength: Optional[float] = None
    gate_strength: Optional[float] = None
    successful_bypasses: Optional[int] = None

    # Compliance
    compliance_violations: Optional[int] = None
    data_encryption: Optional[bool] = None
    reachable_cves: Optional[int] = None
    cve_risk_score: Optional[float] = None


class PRCommenter:
    """Posts or updates a structured AgenticQA CI results comment on a GitHub PR."""

    def __init__(
        self,
        github_token: Optional[str] = None,
        repo: Optional[str] = None,
    ):
        self._token = github_token or os.getenv("GITHUB_TOKEN", "")
        self._repo = repo or os.getenv("GITHUB_REPOSITORY", "")

    # ── Public API ────────────────────────────────────────────────────────────

    def post_results(
        self,
        bundle: CIResultBundle,
        pr_number: Optional[int] = None,
    ) -> bool:
        """
        Post or update the CI results comment on a PR.

        If pr_number is None, auto-detects from GITHUB_REF or gh CLI.
        Returns True if the comment was posted/updated successfully.
        """
        if not self._token:
            print("WARN: GITHUB_TOKEN not set — skipping PR comment")
            return False

        pr = pr_number or self._detect_pr_number()
        if pr is None:
            print("INFO: Not a PR context — skipping comment")
            return False

        body = self._format_comment(bundle)
        return self._upsert_comment(pr, body)

    # ── Comment formatting ────────────────────────────────────────────────────

    def _format_comment(self, bundle: CIResultBundle) -> str:
        """Render a structured markdown comment body for the PR."""
        lines = [
            _COMMENT_MARKER,
            "## AgenticQA CI Results",
            "",
            f"**Run**: `{bundle.run_id}` | **Commit**: `{bundle.commit_sha[:8]}`",
            "",
        ]

        # Tests & Coverage
        if bundle.total_tests is not None:
            failed = bundle.tests_failed or 0
            test_icon = ":green_circle:" if failed == 0 else ":red_circle:"
            lines += [
                "### Tests",
                "| Metric | Value |",
                "|---|---|",
                f"| Total | {bundle.total_tests} |",
                f"| Passed | {bundle.tests_passed or 0} |",
                f"| Failed | {test_icon} {failed} |",
            ]
            if bundle.coverage_percent is not None:
                cov_icon = (
                    ":white_check_mark:"
                    if bundle.coverage_status == "adequate"
                    else ":warning:"
                )
                lines.append(f"| Coverage | {cov_icon} {bundle.coverage_percent:.1f}% |")
            if bundle.tests_generated:
                lines.append(f"| Tests Auto-Generated | :sparkles: {bundle.tests_generated} |")
            lines.append("")

        # SRE / Linting
        if bundle.sre_total_errors is not None:
            lines += [
                "### SRE / Linting",
                "| Metric | Value |",
                "|---|---|",
                f"| Errors Found | {bundle.sre_total_errors} |",
                f"| Fixes Applied | {bundle.sre_fixes_applied or 0} |",
            ]
            if bundle.sre_fix_rate is not None:
                lines.append(f"| Fix Rate | {bundle.sre_fix_rate:.1%} |")
            lines.append("")

        # Red Team Security
        if bundle.scanner_strength is not None:
            bypasses = bundle.successful_bypasses or 0
            bypass_icon = ":white_check_mark:" if bypasses == 0 else ":warning:"
            lines += [
                "### Red Team Security",
                "| Metric | Value |",
                "|---|---|",
                f"| Scanner Strength | {bundle.scanner_strength:.1%} |",
                f"| Gate Strength | {bundle.gate_strength:.1%} |",
                f"| Bypasses | {bypass_icon} {bypasses} |",
                "",
            ]

        # Compliance
        if bundle.compliance_violations is not None:
            comp_icon = (
                ":white_check_mark:"
                if bundle.compliance_violations == 0
                else ":warning:"
            )
            lines += [
                "### Compliance",
                "| Metric | Value |",
                "|---|---|",
                f"| Violations | {comp_icon} {bundle.compliance_violations} |",
            ]
            if bundle.reachable_cves is not None:
                cve_icon = (
                    ":white_check_mark:"
                    if bundle.reachable_cves == 0
                    else ":red_circle:"
                )
                cve_line = f"| Reachable CVEs | {cve_icon} {bundle.reachable_cves}"
                if bundle.cve_risk_score is not None:
                    cve_line += f" (risk: {bundle.cve_risk_score:.2f})"
                cve_line += " |"
                lines.append(cve_line)
            lines.append("")

        lines.append("*Posted by [AgenticQA](https://github.com/nickhomyk/AgenticQA)*")
        return "\n".join(lines)

    # ── PR number detection ───────────────────────────────────────────────────

    def _detect_pr_number(self) -> Optional[int]:
        """
        Detect the current PR number.

        Priority:
        1. GITHUB_REF env var (e.g. refs/pull/42/merge → 42)
        2. gh pr view --json number (works when branch has an open PR)
        """
        ref = os.getenv("GITHUB_REF", "")
        if "/pull/" in ref:
            try:
                parts = ref.split("/")
                idx = parts.index("pull")
                return int(parts[idx + 1])
            except (ValueError, IndexError):
                pass

        # Try gh CLI auto-detection from current branch
        try:
            proc = subprocess.run(
                ["gh", "pr", "view", "--json", "number", "-q", ".number"],
                capture_output=True,
                text=True,
                timeout=10,
            )
            if proc.returncode == 0 and proc.stdout.strip():
                return int(proc.stdout.strip())
        except Exception:
            pass

        return None

    # ── Inline PR review comments ─────────────────────────────────────────────

    def post_inline_comments(
        self,
        pr_number: int,
        findings: list,
        commit_sha: Optional[str] = None,
    ) -> int:
        """
        Post inline review comments on specific diff lines.

        Each finding dict must have:
          path      — file path relative to repo root
          line      — line number in the file (right side of diff)
          body      — comment markdown text
          severity  — optional: "error"|"warning"|"info"

        Uses the GitHub REST API directly (gh CLI doesn't support inline comments).
        Returns number of comments successfully posted.
        """
        if not self._token:
            return 0
        sha = commit_sha or os.getenv("GITHUB_SHA", "")
        if not sha or not self._repo:
            return 0

        import urllib.request, urllib.error
        posted = 0
        for f in findings:
            path = f.get("path", "")
            line = f.get("line")
            body = f.get("body", "")
            if not path or not line or not body:
                continue
            severity = f.get("severity", "warning")
            icon = {"error": "🔴", "warning": "🟡", "info": "🔵"}.get(severity, "🟡")
            payload = json.dumps({
                "body": f"{icon} **AgenticQA**: {body}",
                "commit_id": sha,
                "path": path,
                "line": line,
                "side": "RIGHT",
            }).encode()
            req = urllib.request.Request(
                f"https://api.github.com/repos/{self._repo}/pulls/{pr_number}/comments",
                data=payload,
                headers={
                    "Authorization": f"token {self._token}",
                    "Accept": "application/vnd.github+json",
                    "Content-Type": "application/json",
                },
                method="POST",
            )
            try:
                with urllib.request.urlopen(req, timeout=10):
                    posted += 1
            except urllib.error.HTTPError as e:
                if e.code == 422:
                    pass  # line not in diff — skip silently
                else:
                    print(f"WARN: inline comment failed ({e.code}): {path}:{line}")
            except Exception:
                pass
        return posted

    # ── Comment posting ───────────────────────────────────────────────────────

    def _upsert_comment(self, pr_number: int, body: str) -> bool:
        """
        Post or update the AgenticQA comment on a PR.

        Strategy:
        1. Try `gh pr comment --edit-last` to update the most recent comment by the bot.
        2. If no prior comment exists (non-zero return), create a new one.
        """
        env = dict(os.environ)
        if self._token:
            env["GH_TOKEN"] = self._token

        base_args = ["gh", "pr", "comment", str(pr_number), "--body", body]
        if self._repo:
            base_args += ["--repo", self._repo]

        # Attempt update first
        edit_proc = subprocess.run(
            base_args + ["--edit-last"],
            capture_output=True,
            text=True,
            timeout=30,
            env=env,
        )
        if edit_proc.returncode == 0:
            print(f"Updated AgenticQA comment on PR #{pr_number}")
            return True

        # No previous comment — create new
        create_proc = subprocess.run(
            base_args,
            capture_output=True,
            text=True,
            timeout=30,
            env=env,
        )
        if create_proc.returncode == 0:
            print(f"Posted new AgenticQA comment on PR #{pr_number}")
            return True

        print(f"WARN: Failed to post PR comment: {create_proc.stderr[:300]}")
        return False
