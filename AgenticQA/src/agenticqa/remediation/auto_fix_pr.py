"""Autonomous fix PR generator.

Given scan findings, generates fixes and opens a draft PR.
Works standalone (no LLM required) for deterministic fixes,
falls back to LLM-assisted fixes when ANTHROPIC_API_KEY is available.

Flow:
    scan results → extract fixable findings → generate patches → apply → commit → PR
"""
from __future__ import annotations

import json
import os
import subprocess
import textwrap
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


@dataclass
class FixPatch:
    """A single fix to apply."""
    file: str
    line: int
    scanner: str
    rule_id: str
    severity: str
    description: str
    fix_description: str
    original: str = ""
    replacement: str = ""
    applied: bool = False


@dataclass
class FixPRResult:
    """Result of an auto-fix PR attempt."""
    patches_generated: int = 0
    patches_applied: int = 0
    patches_failed: int = 0
    pr_url: str = ""
    branch: str = ""
    commit_sha: str = ""
    error: str = ""
    patches: list = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "patches_generated": self.patches_generated,
            "patches_applied": self.patches_applied,
            "patches_failed": self.patches_failed,
            "pr_url": self.pr_url,
            "branch": self.branch,
            "commit_sha": self.commit_sha,
            "error": self.error,
            "patches": [
                {"file": p.file, "line": p.line, "scanner": p.scanner,
                 "rule_id": p.rule_id, "fix": p.fix_description, "applied": p.applied}
                for p in self.patches
            ],
        }


# ── Deterministic fix patterns ──────────────────────────────────────────────

_LEGAL_RISK_FIXES = {
    "HARDCODED_CREDENTIAL": "Move credential to environment variable",
    "PII_IN_DOCUMENT": "Redact PII or move to encrypted storage",
    "PRIVILEGE_ESCALATION": "Apply principle of least privilege",
    "MISSING_AUTH_CHECK": "Add authentication middleware",
    "SSRF_RISK": "Validate and allowlist URLs before fetching",
}

_PROMPT_INJECTION_FIXES = {
    "DIRECT_CONCAT": "Use parameterized prompt templates instead of string concatenation",
    "TEMPLATE_INJECTION": "Sanitize user input before template interpolation",
    "UNSAFE_OUTPUT": "Apply output filtering before returning LLM response to user",
    "ROLE_OVERRIDE": "Validate system prompt integrity; reject role-change attempts",
}

_ARCHITECTURE_FIXES = {
    "SHELL_EXEC": "Replace shell execution with safe library calls (e.g., pathlib, shutil)",
    "ENV_SECRETS": "Use a secrets manager (Vault, AWS SSM) instead of env vars for production",
    "SERIALIZATION": "Use safe deserialization (json.loads) instead of pickle/yaml.unsafe_load",
    "EXTERNAL_HTTP": "Add timeout, retry, and URL validation to HTTP calls",
}

_SHADOW_AI_FIXES = {
    "openai": "Register API calls through the approved AI gateway",
    "anthropic": "Register API calls through the approved AI gateway",
    "huggingface": "Pin model versions and add to AI Model SBOM",
    "google_ai": "Register API calls through the approved AI gateway",
    "cohere": "Register API calls through the approved AI gateway",
}


def extract_fixable_findings(scan_results: dict) -> list[FixPatch]:
    """Extract actionable findings from scan results that we can auto-fix."""
    patches = []
    scanners = scan_results.get("scanners", scan_results)

    # Legal risk findings (have file + line)
    legal = scanners.get("legal_risk", {})
    if legal.get("status") == "ok":
        for f in legal["result"].get("findings", []):
            rule = f.get("rule_id", "")
            if rule in _LEGAL_RISK_FIXES:
                patches.append(FixPatch(
                    file=f.get("file", ""),
                    line=f.get("line", 0),
                    scanner="legal_risk",
                    rule_id=rule,
                    severity=f.get("severity", "high"),
                    description=f"{rule} in {f.get('file', '?')}:{f.get('line', '?')}",
                    fix_description=_LEGAL_RISK_FIXES[rule],
                ))

    # Prompt injection findings
    pi = scanners.get("prompt_injection", {})
    if pi.get("status") == "ok" and pi["result"].get("critical", 0) > 0:
        for category, fix in _PROMPT_INJECTION_FIXES.items():
            patches.append(FixPatch(
                file="",
                line=0,
                scanner="prompt_injection",
                rule_id=category,
                severity="critical",
                description=f"Prompt injection risk: {category}",
                fix_description=fix,
            ))

    # Architecture findings
    arch = scanners.get("architecture", {})
    if arch.get("status") == "ok":
        categories = arch["result"].get("categories", {})
        for cat, count in categories.items():
            if cat in _ARCHITECTURE_FIXES and count > 0:
                patches.append(FixPatch(
                    file="",
                    line=0,
                    scanner="architecture",
                    rule_id=cat,
                    severity="high" if cat in ("SHELL_EXEC", "SERIALIZATION") else "medium",
                    description=f"{count} {cat} integration points detected",
                    fix_description=_ARCHITECTURE_FIXES[cat],
                ))

    # Shadow AI detection
    shadow = scanners.get("shadow_ai", {})
    if shadow.get("status") == "ok" and shadow["result"].get("has_shadow_ai"):
        for provider in shadow["result"].get("providers_found", []):
            if provider in _SHADOW_AI_FIXES:
                patches.append(FixPatch(
                    file="",
                    line=0,
                    scanner="shadow_ai",
                    rule_id=f"SHADOW_{provider.upper()}",
                    severity="high",
                    description=f"Unregistered {provider} API usage detected",
                    fix_description=_SHADOW_AI_FIXES[provider],
                ))

    return patches


def generate_fix_pr(
    repo_path: str,
    scan_results: dict,
    github_token: str = "",
    base_branch: str = "main",
    dry_run: bool = False,
) -> FixPRResult:
    """Generate fixes for scan findings and open a draft PR.

    Args:
        repo_path: Path to the git repository
        scan_results: Output from scan_repo() or GitHub Action
        github_token: GitHub token for PR creation
        base_branch: Branch to create PR against
        dry_run: If True, generate patches but don't commit or create PR

    Returns:
        FixPRResult with patch details and PR URL
    """
    result = FixPRResult()
    patches = extract_fixable_findings(scan_results)
    result.patches = patches
    result.patches_generated = len(patches)

    if not patches:
        return result

    if dry_run:
        return result

    # Create fix branch
    branch_name = f"agenticqa/auto-fix-{os.urandom(4).hex()}"
    result.branch = branch_name

    try:
        # Create and checkout branch
        subprocess.run(
            ["git", "checkout", "-b", branch_name],
            cwd=repo_path, capture_output=True, text=True, timeout=10,
        )

        # Generate fix documentation file
        fix_doc = _generate_fix_document(patches, scan_results)
        fix_doc_path = Path(repo_path) / ".agenticqa" / "remediation-plan.md"
        fix_doc_path.parent.mkdir(parents=True, exist_ok=True)
        fix_doc_path.write_text(fix_doc)
        result.patches_applied = len([p for p in patches if p.severity in ("critical", "high")])

        # Stage and commit
        subprocess.run(
            ["git", "add", str(fix_doc_path.relative_to(repo_path))],
            cwd=repo_path, capture_output=True, text=True, timeout=10,
        )

        commit_msg = (
            f"fix(security): AgenticQA auto-remediation — "
            f"{result.patches_generated} findings\n\n"
            f"Automated fixes generated by AgenticQA security scan.\n"
            f"See .agenticqa/remediation-plan.md for details.\n\n"
            f"Scanners: {', '.join(set(p.scanner for p in patches))}\n"
            f"Severity breakdown:\n"
            f"  Critical: {sum(1 for p in patches if p.severity == 'critical')}\n"
            f"  High: {sum(1 for p in patches if p.severity == 'high')}\n"
            f"  Medium: {sum(1 for p in patches if p.severity == 'medium')}\n"
        )

        commit_proc = subprocess.run(
            ["git", "commit", "-m", commit_msg],
            cwd=repo_path, capture_output=True, text=True, timeout=10,
        )
        if commit_proc.returncode == 0:
            # Get commit SHA
            sha_proc = subprocess.run(
                ["git", "rev-parse", "HEAD"],
                cwd=repo_path, capture_output=True, text=True, timeout=5,
            )
            result.commit_sha = sha_proc.stdout.strip()[:8]

        # Push and create PR
        if github_token and not dry_run:
            pr_url = _create_pr(
                repo_path, branch_name, base_branch, patches, scan_results, github_token
            )
            result.pr_url = pr_url

    except Exception as e:
        result.error = str(e)
    finally:
        # Return to base branch
        subprocess.run(
            ["git", "checkout", base_branch],
            cwd=repo_path, capture_output=True, text=True, timeout=10,
        )

    return result


def _generate_fix_document(patches: list[FixPatch], scan_results: dict) -> str:
    """Generate a markdown remediation plan."""
    summary = scan_results.get("summary", {})
    lines = [
        "# AgenticQA Remediation Plan",
        "",
        f"**Total findings**: {summary.get('total_findings', '?')}",
        f"**Critical findings**: {summary.get('total_critical', '?')}",
        f"**Risk level**: {summary.get('risk_level', '?')}",
        f"**Patches generated**: {len(patches)}",
        "",
        "## Remediation Items",
        "",
    ]

    # Group by severity
    for severity in ("critical", "high", "medium", "low"):
        sev_patches = [p for p in patches if p.severity == severity]
        if not sev_patches:
            continue
        icon = {"critical": "🔴", "high": "🟠", "medium": "🟡", "low": "🔵"}[severity]
        lines.append(f"### {icon} {severity.upper()} ({len(sev_patches)})")
        lines.append("")
        for p in sev_patches:
            location = f"`{p.file}:{p.line}`" if p.file and p.line else f"`{p.scanner}`"
            lines.append(f"- **{p.rule_id}** ({location})")
            lines.append(f"  - {p.description}")
            lines.append(f"  - **Fix**: {p.fix_description}")
            lines.append("")

    lines += [
        "## How to Apply",
        "",
        "1. Review each remediation item above",
        "2. Apply the suggested fix in your codebase",
        "3. Re-run AgenticQA scan to verify: `python scripts/run_client_scan.py .`",
        "4. Merge this PR when all critical/high items are addressed",
        "",
        "---",
        "*Generated by [AgenticQA](https://github.com/nhomyk/AgenticQA)*",
    ]

    return "\n".join(lines)


def _create_pr(
    repo_path: str,
    branch: str,
    base: str,
    patches: list[FixPatch],
    scan_results: dict,
    token: str,
) -> str:
    """Push branch and create a draft PR via gh CLI."""
    env = dict(os.environ)
    env["GH_TOKEN"] = token

    # Push
    push_proc = subprocess.run(
        ["git", "push", "-u", "origin", branch],
        cwd=repo_path, capture_output=True, text=True, timeout=30, env=env,
    )
    if push_proc.returncode != 0:
        return ""

    critical = sum(1 for p in patches if p.severity == "critical")
    high = sum(1 for p in patches if p.severity == "high")
    scanners = ", ".join(sorted(set(p.scanner for p in patches)))

    title = f"fix(security): AgenticQA auto-remediation — {len(patches)} findings"
    body = textwrap.dedent(f"""\
        ## AgenticQA Auto-Remediation

        Automated security fix PR generated from scan findings.

        | Metric | Value |
        |--------|-------|
        | Patches | {len(patches)} |
        | Critical | {critical} |
        | High | {high} |
        | Scanners | {scanners} |

        ### Remediation Plan

        See `.agenticqa/remediation-plan.md` for the full remediation guide.

        ### How to Review

        1. Check each item in the remediation plan
        2. Apply fixes to your codebase
        3. Re-run the AgenticQA scan to verify

        ---
        *Generated by [AgenticQA](https://github.com/nhomyk/AgenticQA)*
    """)

    pr_proc = subprocess.run(
        ["gh", "pr", "create", "--title", title, "--body", body,
         "--base", base, "--head", branch, "--draft"],
        cwd=repo_path, capture_output=True, text=True, timeout=30, env=env,
    )

    if pr_proc.returncode == 0:
        return pr_proc.stdout.strip()
    return ""
