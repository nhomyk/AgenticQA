"""Run a repeatable SDET benchmark and persist trend reports.

This script runs two cohorts in an isolated temporary git repository:
1) SDET loop with auto-fix disabled
2) SDET loop with auto-fix enabled

It emits:
- benchmark_summary.json
- benchmark_report.md
- history JSONL at ~/.agenticqa/benchmarks/sdet_trend_history.jsonl
"""

from __future__ import annotations

import argparse
import json
import subprocess
import tempfile
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Dict, List

try:
    from src.agenticqa.workflow_requests import PromptWorkflowStore
    from src.agenticqa.workflow_worker import WorkflowExecutionWorker
except Exception:  # pragma: no cover - fallback for installed-package execution
    from agenticqa.workflow_requests import PromptWorkflowStore
    from agenticqa.workflow_worker import WorkflowExecutionWorker


@dataclass
class RunResult:
    request_id: str
    autofix_enabled: bool
    status: str
    error_message: str


def _git(cwd: Path, args: List[str]) -> None:
    subprocess.run(["git", *args], cwd=str(cwd), check=True, capture_output=True, text=True)


def _init_temp_repo(root: Path) -> Path:
    repo = root / "repo"
    repo.mkdir(parents=True, exist_ok=True)
    _git(repo, ["init"])
    _git(repo, ["config", "user.email", "agenticqa@example.com"])
    _git(repo, ["config", "user.name", "AgenticQA Bot"])
    (repo / "README.md").write_text("# SDET benchmark temp repo\n", encoding="utf-8")
    _git(repo, ["add", "README.md"])
    _git(repo, ["commit", "-m", "init"])
    return repo


def _run_case(
    store: PromptWorkflowStore,
    worker: WorkflowExecutionWorker,
    repo: Path,
    idx: int,
    autofix_enabled: bool,
) -> RunResult:
    item = store.create_request(
        prompt=f"SDET trend benchmark run {idx}",
        repo=str(repo),
        requester="sdet_trend_benchmark",
        metadata={
            "target_file": f"src/generated/sdet_benchmark_{idx}.py",
            "require_sdet_loop": True,
            "max_sdet_iterations": 2,
            "enable_sdet_autofix": autofix_enabled,
            "max_sdet_fix_attempts": 2,
            "inject_python_syntax_error": True,
        },
    )
    store.approve_request(item["id"])
    store.queue_request(item["id"])
    out = worker.run_request(item["id"], dry_run=True, open_pr=False)
    return RunResult(
        request_id=item["id"],
        autofix_enabled=autofix_enabled,
        status=str(out.get("status") or "UNKNOWN"),
        error_message=str(out.get("error_message") or ""),
    )


def _summarize(results: List[RunResult]) -> Dict[str, Any]:
    baseline = [r for r in results if not r.autofix_enabled]
    treatment = [r for r in results if r.autofix_enabled]

    def _cohort(items: List[RunResult]) -> Dict[str, Any]:
        total = len(items)
        completed = sum(1 for r in items if r.status == "COMPLETED")
        failed = sum(1 for r in items if r.status == "FAILED")
        pass_rate = round(completed / total, 4) if total else 0.0
        return {
            "total": total,
            "completed": completed,
            "failed": failed,
            "pass_rate": pass_rate,
        }

    b = _cohort(baseline)
    t = _cohort(treatment)
    pass_rate_uplift = round(t["pass_rate"] - b["pass_rate"], 4)
    completed_delta = t["completed"] - b["completed"]

    return {
        "baseline_no_autofix": b,
        "treatment_autofix": t,
        "pass_rate_uplift": pass_rate_uplift,
        "completed_delta": completed_delta,
        "results": [asdict(r) for r in results],
    }


def _read_history(history_path: Path) -> List[Dict[str, Any]]:
    if not history_path.exists():
        return []
    entries: List[Dict[str, Any]] = []
    for line in history_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            entries.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return entries


def _write_report(summary: Dict[str, Any], output_dir: Path, history: List[Dict[str, Any]]) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(UTC).isoformat()

    report = [
        "# SDET Learning Trend Benchmark",
        "",
        f"- Timestamp: {ts}",
        f"- Baseline pass rate: {summary['baseline_no_autofix']['pass_rate']:.2%}",
        f"- Treatment pass rate: {summary['treatment_autofix']['pass_rate']:.2%}",
        f"- Pass-rate uplift: {summary['pass_rate_uplift']:.2%}",
        f"- Completed delta: {summary['completed_delta']}",
        "",
        "## Latest Cohort Results",
        "",
        "```json",
        json.dumps(summary, indent=2),
        "```",
    ]

    if len(history) >= 2:
        prev = history[-2]
        curr = history[-1]
        report.extend(
            [
                "",
                "## Trend vs Previous Run",
                "",
                f"- Previous uplift: {prev.get('pass_rate_uplift', 0.0):.2%}",
                f"- Current uplift: {curr.get('pass_rate_uplift', 0.0):.2%}",
                f"- Delta uplift: {(curr.get('pass_rate_uplift', 0.0) - prev.get('pass_rate_uplift', 0.0)):.2%}",
            ]
        )

    (output_dir / "benchmark_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    (output_dir / "benchmark_report.md").write_text("\n".join(report) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Run SDET auto-fix trend benchmark")
    parser.add_argument("--runs-per-cohort", type=int, default=3, help="Number of runs for each cohort")
    parser.add_argument("--output-dir", type=str, default=".agenticqa/benchmarks/latest", help="Where to write report files")
    args = parser.parse_args()

    runs = max(1, min(args.runs_per_cohort, 10))
    output_dir = Path(args.output_dir).expanduser().resolve()
    history_path = Path.home() / ".agenticqa" / "benchmarks" / "sdet_trend_history.jsonl"
    history_path.parent.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory(prefix="agenticqa_sdet_trend_") as td:
        root = Path(td)
        repo = _init_temp_repo(root)
        db_path = root / "workflow.db"
        store = PromptWorkflowStore(db_path=str(db_path))
        worker = WorkflowExecutionWorker(store)

        results: List[RunResult] = []
        i = 1
        for _ in range(runs):
            results.append(_run_case(store=store, worker=worker, repo=repo, idx=i, autofix_enabled=False))
            i += 1
        for _ in range(runs):
            results.append(_run_case(store=store, worker=worker, repo=repo, idx=i, autofix_enabled=True))
            i += 1

        summary = _summarize(results)
        summary["timestamp"] = datetime.now(UTC).isoformat()
        summary["runs_per_cohort"] = runs

        with history_path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(summary) + "\n")

        history = _read_history(history_path)
        _write_report(summary=summary, output_dir=output_dir, history=history)
        store.close()

        print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
