"""Execution worker for prompt workflow requests.

Processes queued workflow requests by creating a branch, committing a workflow artifact,
and optionally opening a GitHub pull request.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Dict, List, Optional
from urllib import error as url_error
from urllib import request as url_request

from .prompt_ops_orchestrator import PromptOpsOrchestrator
from .workflow_requests import PromptWorkflowStore


class WorkflowExecutionWorker:
    """Worker that executes queued prompt workflow requests."""

    def __init__(self, store: PromptWorkflowStore):
        self.store = store
        self.orchestrator = PromptOpsOrchestrator()

    def run_next(self, dry_run: bool = True, open_pr: bool = True) -> Optional[Dict[str, Any]]:
        queued = self.store.get_next_queued_request()
        if not queued:
            return None
        return self.run_request(queued["id"], dry_run=dry_run, open_pr=open_pr)

    def run_request(self, request_id: str, dry_run: bool = True, open_pr: bool = True) -> Dict[str, Any]:
        req = self.store.get_request(request_id)
        if not req:
            raise ValueError("request_not_found")
        if req["status"] != "QUEUED":
            raise ValueError(f"request_not_queued:{req['status']}")

        repo_path = Path(req["repo"]).expanduser().resolve()
        if not repo_path.exists() or not repo_path.is_dir():
            return self.store.fail_request(request_id, f"repo_not_found:{repo_path}")

        base_branch = ""
        branch_name = ""
        commit_sha = None
        pr_url = None
        pushed = False

        try:
            self.store.start_request(request_id)

            base_branch = self._git(repo_path, ["rev-parse", "--abbrev-ref", "HEAD"]).strip()
            branch_name = self._build_branch_name(req)
            branch_name = self._ensure_unique_branch_name(repo_path, branch_name)

            self._git(repo_path, ["checkout", "-B", branch_name])

            generated_paths, orchestration = self._generate_and_apply_code(repo_path=repo_path, req=req)
            artifact_path = self._write_execution_artifact(
                repo_path=repo_path,
                req=req,
                orchestration=orchestration,
            )
            self._git(repo_path, ["add", str(artifact_path)])
            for generated_path in generated_paths:
                self._git(repo_path, ["add", str(generated_path)])

            commit_message = f"chore(workflow): execute {request_id}"
            commit_body = f"Prompt: {req['prompt'][:220]}"
            self._git(repo_path, ["commit", "-m", commit_message, "-m", commit_body])
            commit_sha = self._git(repo_path, ["rev-parse", "HEAD"]).strip()

            self._enforce_policy_gates(
                req=req,
                dry_run=dry_run,
                open_pr=open_pr,
                orchestration=orchestration,
            )

            if not dry_run:
                self._git(repo_path, ["push", "-u", "origin", branch_name])
                pushed = True
                if open_pr:
                    pr_url = self._open_github_pr(
                        req=req,
                        repo_path=repo_path,
                        branch_name=branch_name,
                        base_branch=base_branch,
                    )

            note = "Execution completed in dry-run mode" if dry_run else "Execution completed"
            return self.store.complete_request(
                request_id,
                branch_name=branch_name,
                commit_sha=commit_sha,
                pr_url=pr_url,
                note=note,
            )
        except Exception as exc:
            self._attempt_rollback(
                repo_path=repo_path,
                base_branch=base_branch,
                branch_name=branch_name,
                dry_run=dry_run,
                pushed=pushed,
                req=req,
            )
            return self.store.fail_request(
                request_id,
                error_message=str(exc),
                branch_name=branch_name or None,
                commit_sha=commit_sha,
                pr_url=pr_url,
            )
        finally:
            if base_branch:
                try:
                    self._git(repo_path, ["checkout", base_branch])
                except Exception:
                    pass

    def _enforce_policy_gates(
        self,
        req: Dict[str, Any],
        dry_run: bool,
        open_pr: bool,
        orchestration: Dict[str, Any],
    ) -> None:
        """Apply strict policy gates for push/PR automation."""
        metadata = req.get("metadata") or {}
        gate = (orchestration or {}).get("quality_gate") or {}

        if dry_run:
            return

        if not gate.get("passed", True):
            blockers = gate.get("blockers") or ["quality_gate_failed"]
            raise RuntimeError(f"policy_gate_failed:{','.join(blockers)}")

        approved_by = str(metadata.get("approved_by") or "").strip()
        if not approved_by:
            raise RuntimeError("policy_gate_failed:approved_by_required_for_push")

        lowered_prompt = (req.get("prompt") or "").lower()
        is_high_risk = any(k in lowered_prompt for k in ["delete", "drop", "force", "truncate", "rollback"])
        if is_high_risk and not bool(metadata.get("allow_high_risk", False)):
            raise RuntimeError("policy_gate_failed:high_risk_requires_allow_high_risk")

        if open_pr and not str(metadata.get("policy_ticket") or "").strip():
            raise RuntimeError("policy_gate_failed:policy_ticket_required_for_pr")

    def _attempt_rollback(
        self,
        repo_path: Path,
        base_branch: str,
        branch_name: str,
        dry_run: bool,
        pushed: bool,
        req: Dict[str, Any],
    ) -> None:
        """Best-effort rollback for failed executions (cleanup + optional remote branch delete)."""
        if not base_branch:
            return
        try:
            self._git(repo_path, ["checkout", base_branch])
        except Exception:
            return

        if branch_name:
            try:
                self._git(repo_path, ["branch", "-D", branch_name])
            except Exception:
                pass

        metadata = req.get("metadata") or {}
        if (not dry_run) and pushed and bool(metadata.get("auto_rollback", True)) and branch_name:
            try:
                self._git(repo_path, ["push", "origin", "--delete", branch_name])
            except Exception:
                pass

    def _write_execution_artifact(
        self,
        repo_path: Path,
        req: Dict[str, Any],
        orchestration: Optional[Dict[str, Any]] = None,
    ) -> Path:
        out_dir = repo_path / ".agenticqa" / "workflows"
        out_dir.mkdir(parents=True, exist_ok=True)

        artifact = out_dir / f"{req['id']}.md"
        now = datetime.now(UTC).isoformat()
        plan = req.get("plan") or {}

        body = [
            f"# Workflow Execution: {req['id']}",
            "",
            f"- Timestamp: {now}",
            f"- Requester: {req.get('requester')}",
            f"- Repo: {req.get('repo')}",
            f"- Status: IN_PROGRESS",
            "",
            "## Prompt",
            "",
            req.get("prompt", ""),
            "",
            "## Plan",
            "",
            "```json",
            json.dumps(plan, indent=2),
            "```",
            "",
            "## Worker Notes",
            "",
            "This artifact was generated by the AgenticQA workflow worker.",
            "",
        ]

        if orchestration:
            body.extend(
                [
                    "## Collaborative Orchestration",
                    "",
                    "```json",
                    json.dumps(orchestration, indent=2),
                    "```",
                    "",
                ]
            )
        artifact.write_text("\n".join(body), encoding="utf-8")
        return artifact

    def _generate_and_apply_code(self, repo_path: Path, req: Dict[str, Any]) -> tuple[List[Path], Dict[str, Any]]:
        feature_request = self._derive_feature_request(req)
        orchestration = self._run_orchestration(req=req, feature_request=feature_request)
        generated = (orchestration.get("generation") or {})
        if not generated.get("code"):
            generated = self._run_fullstack_generation(feature_request)
            orchestration["generation_fallback"] = True
            orchestration["generation"] = generated

        code = generated.get("code")
        if not code:
            return [], orchestration

        metadata = req.get("metadata") or {}
        explicit_target = metadata.get("target_file")
        suggested_files = generated.get("files_created") or []

        targets: List[Path] = []
        if explicit_target:
            targets.append(repo_path / explicit_target)
        elif suggested_files:
            # Persist primary generated artifact into first suggested file
            targets.append(repo_path / suggested_files[0])
        else:
            targets.append(repo_path / "src" / "generated" / f"{req['id']}.js")

        written: List[Path] = []
        for target in targets:
            target.parent.mkdir(parents=True, exist_ok=True)
            body = self._render_generated_file(
                req=req,
                feature_request=feature_request,
                generated=generated,
                orchestration=orchestration,
            )
            target.write_text(body, encoding="utf-8")
            written.append(target)
        return written, orchestration

    def _run_orchestration(self, req: Dict[str, Any], feature_request: Dict[str, str]) -> Dict[str, Any]:
        try:
            return self.orchestrator.run(request=req, feature_request=feature_request)
        except Exception:
            generated = self._run_fullstack_generation(feature_request)
            return {
                "feature_request": feature_request,
                "generation": generated,
                "collaboration": {},
                "quality_gate": {
                    "passed": True,
                    "blockers": [],
                },
                "ontology": {
                    "author_agent": "Fullstack_Agent",
                    "review_agents": [],
                    "delegation_mode": "fallback",
                    "learning_mode": "base_agent_rag",
                },
                "delegation_summary": {},
                "generation_fallback": True,
            }

    def _run_fullstack_generation(self, feature_request: Dict[str, str]) -> Dict[str, Any]:
        try:
            try:
                from src.agents import FullstackAgent  # type: ignore
            except Exception:
                from agents import FullstackAgent  # type: ignore

            agent = FullstackAgent()
            result = agent.execute(feature_request)
            if isinstance(result, dict) and result.get("code"):
                return result
        except Exception:
            pass

        return self._fallback_generation(feature_request)

    def _fallback_generation(self, feature_request: Dict[str, str]) -> Dict[str, Any]:
        title = feature_request.get("title", "workflow_feature")
        category = feature_request.get("category", "general")
        description = feature_request.get("description", "")
        fn = re.sub(r"[^a-z0-9_]+", "_", title.lower().replace("-", "_")).strip("_") or "generated_feature"

        code = (
            f"# Auto-generated fallback implementation\n"
            f"# Title: {title}\n"
            f"# Category: {category}\n"
            f"# Description: {description[:500]}\n\n"
            f"def {fn}():\n"
            f"    return {{\"status\": \"ok\", \"feature\": \"{title}\"}}\n"
        )

        return {
            "feature_title": title,
            "category": category,
            "code_generated": True,
            "code": code,
            "files_created": [f"src/generated/{fn}.py"],
            "status": "success",
            "rag_insights_used": 0,
        }

    def _derive_feature_request(self, req: Dict[str, Any]) -> Dict[str, str]:
        prompt = (req.get("prompt") or "").strip()
        metadata = req.get("metadata") or {}

        category = str(metadata.get("category") or "").strip().lower()
        if not category:
            lowered = prompt.lower()
            if any(k in lowered for k in ["endpoint", "route", "api", "http"]):
                category = "api"
            elif any(k in lowered for k in ["ui", "component", "dashboard", "streamlit", "frontend"]):
                category = "ui"
            else:
                category = "general"

        title = str(metadata.get("title") or prompt[:80] or "Workflow Request").strip()
        if len(title) > 80:
            title = title[:80]

        return {
            "title": title,
            "category": category,
            "description": prompt,
        }

    def _render_generated_file(
        self,
        req: Dict[str, Any],
        feature_request: Dict[str, str],
        generated: Dict[str, Any],
        orchestration: Optional[Dict[str, Any]] = None,
    ) -> str:
        code = generated.get("code", "")
        if not isinstance(code, str):
            code = str(code)

        header = [
            "// -----------------------------------------------------------------------------",
            "// Auto-generated by AgenticQA WorkflowExecutionWorker",
            f"// Request ID: {req.get('id')}",
            f"// Feature: {feature_request.get('title')}",
            f"// Category: {feature_request.get('category')}",
            f"// Author Agent: {(orchestration or {}).get('ontology', {}).get('author_agent', 'Fullstack_Agent')}",
            "// -----------------------------------------------------------------------------",
            "",
        ]
        if orchestration:
            gate = orchestration.get("quality_gate") or {}
            header.extend(
                [
                    f"// Quality Gate Passed: {gate.get('passed', True)}",
                    f"// Review Agents: {', '.join((orchestration.get('ontology') or {}).get('review_agents', []))}",
                    "",
                ]
            )
        return "\n".join(header) + code + "\n"

    def _build_branch_name(self, req: Dict[str, Any]) -> str:
        slug = re.sub(r"[^a-z0-9]+", "-", (req.get("prompt") or "task").lower()).strip("-")
        slug = slug[:32] or "task"
        return f"agenticqa/{req['id']}-{slug}"

    def _ensure_unique_branch_name(self, repo_path: Path, desired: str) -> str:
        try:
            self._git(repo_path, ["rev-parse", "--verify", "--quiet", desired])
            suffix = datetime.now(UTC).strftime("%Y%m%d%H%M%S")
            return f"{desired[:70]}-{suffix}"
        except Exception:
            return desired

    def _git(self, cwd: Path, args: List[str]) -> str:
        completed = subprocess.run(
            ["git", *args],
            cwd=str(cwd),
            text=True,
            capture_output=True,
            timeout=60,
        )
        if completed.returncode != 0:
            stderr = (completed.stderr or "").strip()
            stdout = (completed.stdout or "").strip()
            details = stderr or stdout or "git command failed"
            raise RuntimeError(f"git {' '.join(args)} -> {details}")
        return completed.stdout

    def _open_github_pr(
        self,
        req: Dict[str, Any],
        repo_path: Path,
        branch_name: str,
        base_branch: str,
    ) -> Optional[str]:
        token = os.getenv("GITHUB_TOKEN")
        if not token:
            return None

        metadata = req.get("metadata") or {}
        repo_slug = metadata.get("github_repo") or os.getenv("AGENTICQA_GITHUB_REPO")
        if not repo_slug:
            origin = self._git(repo_path, ["remote", "get-url", "origin"]).strip()
            repo_slug = self._parse_repo_slug(origin)

        if not repo_slug:
            return None

        title = f"AgenticQA workflow: {req['id']}"
        body = (
            "Automated workflow execution generated by AgenticQA.\n\n"
            f"- Request ID: {req['id']}\n"
            f"- Requester: {req.get('requester')}\n"
            f"- Prompt: {req.get('prompt', '')[:400]}\n"
        )

        payload = {
            "title": title,
            "head": branch_name,
            "base": os.getenv("AGENTICQA_BASE_BRANCH", base_branch or "main"),
            "body": body,
            "maintainer_can_modify": True,
        }

        req_obj = url_request.Request(
            f"https://api.github.com/repos/{repo_slug}/pulls",
            data=json.dumps(payload).encode("utf-8"),
            method="POST",
            headers={
                "Authorization": f"Bearer {token}",
                "Accept": "application/vnd.github+json",
                "Content-Type": "application/json",
                "X-GitHub-Api-Version": "2022-11-28",
            },
        )

        try:
            with url_request.urlopen(req_obj, timeout=20) as response:
                data = json.loads(response.read().decode("utf-8"))
                return data.get("html_url")
        except url_error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="ignore")
            raise RuntimeError(f"github_pr_create_failed:{exc.code}:{detail[:300]}")

    def _parse_repo_slug(self, origin_url: str) -> Optional[str]:
        if origin_url.startswith("git@github.com:"):
            return self._strip_git_suffix(origin_url.split(":", 1)[1])
        if "github.com/" in origin_url:
            return self._strip_git_suffix(origin_url.split("github.com/", 1)[1])
        return None

    def _strip_git_suffix(self, value: str) -> str:
        if value.endswith(".git"):
            return value[:-4]
        return value
