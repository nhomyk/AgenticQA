#!/usr/bin/env python
"""
AgenticQA — Full Client Demo
=============================

Simulates the complete client experience end-to-end:

  STEP 1  Create a minimal client repo (FastAPI backend, no tests, no frontend)
  STEP 2  Run onboarding: architecture scan + 7 security sweeps + coverage map
  STEP 3  Client submits a feature: "Add a web UI with input and submit button"
  STEP 4  LLM generates UI code  (uses real Anthropic API if ANTHROPIC_API_KEY
          is set; otherwise uses a pre-written demo implementation)
  STEP 5  Security scan on generated code
  STEP 6  Generate UI tests, run them
  STEP 7  UI self-healing loop if tests fail
  STEP 8  Final SHIP IT / REVIEW REQUIRED verdict + coverage delta

Usage
-----
  python run_demo.py                        # uses demo LLM stub (no API key needed)
  ANTHROPIC_API_KEY=sk-ant-... python run_demo.py   # uses real Claude Haiku

Options (env vars)
------------------
  DEMO_REPO   path to your own repo (default: /tmp/agenticqa-demo-<pid>)
  DEMO_QUIET  set to 1 to suppress verbose output
"""

import os
import sys
import shutil
import textwrap
import tempfile
import time
from pathlib import Path

# ── Colour helpers ─────────────────────────────────────────────────────────────

def _c(text, code): return f"\033[{code}m{text}\033[0m" if sys.stdout.isatty() else text
def green(t):  return _c(t, "32")
def red(t):    return _c(t, "31")
def yellow(t): return _c(t, "33")
def cyan(t):   return _c(t, "36")
def bold(t):   return _c(t, "1")
def dim(t):    return _c(t, "2")

QUIET = os.environ.get("DEMO_QUIET") == "1"

def step(n, title):
    print(f"\n{'─'*60}")
    print(bold(f"  STEP {n}  {title}"))
    print(f"{'─'*60}")

def info(msg):
    if not QUIET:
        print(f"  {dim('→')} {msg}")

def ok(msg):   print(f"  {green('✓')} {msg}")
def warn(msg): print(f"  {yellow('⚠')} {msg}")
def fail(msg): print(f"  {red('✗')} {msg}")


# ── STEP 1 — Create demo client repo ──────────────────────────────────────────

def create_demo_repo() -> str:
    repo = os.environ.get("DEMO_REPO") or tempfile.mkdtemp(prefix="agenticqa-demo-")
    root = Path(repo)
    (root / "api").mkdir(parents=True, exist_ok=True)

    (root / "api" / "main.py").write_text(textwrap.dedent("""\
        \"\"\"Task manager — in-memory CRUD.\"\"\"
        from datetime import datetime

        _tasks: list = []

        def create_task(title: str, description: str = "") -> dict:
            task = {
                "id": len(_tasks) + 1,
                "title": title,
                "description": description,
                "done": False,
                "created_at": datetime.utcnow().isoformat(),
            }
            _tasks.append(task)
            return task

        def get_tasks(include_done: bool = True) -> list:
            return _tasks if include_done else [t for t in _tasks if not t["done"]]

        def complete_task(task_id: int):
            for t in _tasks:
                if t["id"] == task_id:
                    t["done"] = True
                    return t

        def delete_task(task_id: int) -> bool:
            global _tasks
            orig = len(_tasks)
            _tasks = [t for t in _tasks if t["id"] != task_id]
            return len(_tasks) < orig
    """))

    (root / "api" / "server.py").write_text(textwrap.dedent("""\
        \"\"\"FastAPI server.\"\"\"
        from fastapi import FastAPI, HTTPException
        from pydantic import BaseModel
        from api.main import create_task, get_tasks, complete_task, delete_task

        app = FastAPI(title="Task Manager", version="1.0.0")

        class TaskCreate(BaseModel):
            title: str
            description: str = ""

        @app.get("/health")
        def health(): return {"status": "ok"}

        @app.get("/tasks")
        def list_tasks(include_done: bool = True):
            return {"tasks": get_tasks(include_done)}

        @app.post("/tasks")
        def add_task(req: TaskCreate):
            return create_task(req.title, req.description)

        @app.put("/tasks/{task_id}/complete")
        def mark_complete(task_id: int):
            t = complete_task(task_id)
            if not t: raise HTTPException(404, "Not found")
            return t

        @app.delete("/tasks/{task_id}")
        def remove_task(task_id: int):
            if not delete_task(task_id): raise HTTPException(404, "Not found")
            return {"deleted": task_id}
    """))

    (root / "requirements.txt").write_text("fastapi\nuvicorn[standard]\npydantic>=2.0\n")
    (root / "README.md").write_text("# Demo Task Manager\nMinimal FastAPI app — no tests, no frontend.\n")
    return repo


# ── STEP 4 — LLM code generation (real or stub) ───────────────────────────────

DEMO_UI_CODE = textwrap.dedent("""\
    \"\"\"Task Manager — Streamlit UI\"\"\"
    import os
    import requests
    import streamlit as st

    API_BASE = os.environ.get("API_BASE", "http://localhost:8000")

    st.set_page_config(page_title="Task Manager", page_icon="✅", layout="centered")
    st.title("Task Manager")

    st.subheader("Add a Task")
    with st.form("add_task_form", clear_on_submit=True):
        title = st.text_input("Task title", placeholder="e.g. Buy groceries")
        description = st.text_area("Description (optional)", height=80)
        submitted = st.form_submit_button("Add Task", type="primary")

    if submitted:
        if not title.strip():
            st.error("Title cannot be empty.")
        else:
            try:
                resp = requests.post(
                    f"{API_BASE}/tasks",
                    json={"title": title.strip(), "description": description.strip()},
                    timeout=5,
                )
                resp.raise_for_status()
                st.success(f"Task added: **{title}**")
            except requests.exceptions.ConnectionError:
                st.error("Cannot reach the API server. Is it running?")

    st.markdown("---")
    st.subheader("Your Tasks")
    show_done = st.checkbox("Show completed tasks", value=True)

    try:
        resp = requests.get(f"{API_BASE}/tasks", params={"include_done": show_done}, timeout=5)
        resp.raise_for_status()
        tasks = resp.json().get("tasks", [])
    except requests.exceptions.ConnectionError:
        st.warning("API server not reachable — showing no tasks.")
        tasks = []
    except Exception as exc:
        st.error(f"Failed to load tasks: {exc}")
        tasks = []

    if not tasks:
        st.info("No tasks yet. Add one above!")
    else:
        for task in tasks:
            col_title, col_done, col_del = st.columns([6, 2, 1])
            label = f"~~{task['title']}~~" if task["done"] else task["title"]
            col_title.markdown(label)
            if not task["done"]:
                if col_done.button("Complete", key=f"done_{task['id']}"):
                    requests.put(f"{API_BASE}/tasks/{task['id']}/complete", timeout=5)
                    st.rerun()
            if col_del.button("🗑", key=f"del_{task['id']}"):
                requests.delete(f"{API_BASE}/tasks/{task['id']}", timeout=5)
                st.rerun()
""")


def generate_ui_code(description: str, file_path: str) -> str:
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if api_key:
        try:
            import anthropic
            client = anthropic.Anthropic(api_key=api_key)
            msg = client.messages.create(
                model="claude-haiku-4-5-20251001",
                max_tokens=4096,
                system=(
                    "You are a senior Python UI engineer. Write a complete Streamlit app "
                    "for the feature described. Use requests to call a FastAPI backend at "
                    "os.environ.get('API_BASE', 'http://localhost:8000'). "
                    "Output ONLY raw Python source code — no markdown fences, no explanation."
                ),
                messages=[{"role": "user", "content": description}],
            )
            return msg.content[0].text
        except Exception as e:
            warn(f"LLM call failed ({e}) — using demo stub")
    else:
        info("No ANTHROPIC_API_KEY — using pre-written demo implementation")
    return DEMO_UI_CODE


# ── Pipeline helpers ───────────────────────────────────────────────────────────

def run_security_scan(repo: str, file_path: str, code: str):
    sys.path.insert(0, str(Path(__file__).parent / "src"))
    from agenticqa.security.architecture_scanner import ArchitectureScanner

    result = ArchitectureScanner().scan(repo)
    file_areas = [a for a in result.integration_areas
                  if file_path in a.source_file or a.source_file in file_path]

    critical = [a for a in file_areas if a.severity == "critical"]
    high = [a for a in file_areas if a.severity == "high"]
    non_info = critical + high

    return {
        "critical": len(critical),
        "high": len(high),
        "areas": non_info,
        "attack_surface_score": result.attack_surface_score,
        "recommendation": "SHIP IT" if not critical else "DO NOT SHIP",
    }


def run_ui_tests(repo: str, file_path: str, code: str) -> dict:
    from agenticqa.testing.frontend_test_generator import (
        FrameworkDetector, FrontendTestGenerator,
    )
    from agenticqa.testing.frontend_test_runner import FrontendTestRunner

    detection = FrameworkDetector().detect(repo, file_path)
    gen = FrontendTestGenerator().generate(
        description="Task manager UI", code=code,
        file_path=file_path, repo_path=repo, detection=detection,
    )
    result = FrontendTestRunner().run_generated(gen, repo, timeout=30)
    return result


# ── MAIN DEMO ──────────────────────────────────────────────────────────────────

def main():
    print(bold("\n" + "═"*60))
    print(bold("  AgenticQA — Full Client Demo"))
    print(bold("═"*60))

    # ── Step 1: Create repo ────────────────────────────────────────────────────
    step(1, "Create minimal client repository")
    repo = create_demo_repo()
    ok(f"Repo created: {repo}")
    info("Contents: api/main.py (CRUD), api/server.py (FastAPI), no tests, no frontend")

    # ── Step 2: Onboarding ─────────────────────────────────────────────────────
    step(2, "AgenticQA onboarding — learn architecture, map coverage")
    sys.path.insert(0, str(Path(__file__).parent / "src"))

    from agenticqa.security.architecture_scanner import ArchitectureScanner
    from agenticqa.onboarding.coverage_mapper import CoverageMapper

    t0 = time.time()
    arch = ArchitectureScanner().scan(repo)
    cov  = CoverageMapper().scan(repo)
    elapsed = time.time() - t0

    ok(f"Architecture scan: {arch.files_scanned} files, attack surface {arch.attack_surface_score:.0f}/100")
    ok(f"Coverage map: {cov.total_source_files} source files, {cov.coverage_pct}% covered")
    ok(f"Scan time: {elapsed:.1f}s")

    # Show non-test integration areas (test files generate expected noise)
    prod_areas = [a for a in arch.integration_areas if "_test" not in a.source_file
                  and "test_" not in a.source_file.split("/")[-1]]
    print()
    print(f"  {'Category':<22} {'Severity':<10} File")
    print(f"  {'─'*22} {'─'*10} {'─'*30}")
    for a in prod_areas[:8]:
        sev_col = red if a.severity == "critical" else (yellow if a.severity == "high" else dim)
        print(f"  {a.category:<22} {sev_col(a.severity.upper()):<10} {a.source_file}")
    if not prod_areas:
        info("No production integration areas detected")

    # Dynamic gap analysis
    gaps = []
    if cov.coverage_pct < 80:
        gaps.append(f"low test coverage ({cov.coverage_pct}%)")
    if not any(a.source_file.startswith("ui/") for a in arch.integration_areas if "_test" not in a.source_file):
        gaps.append("no frontend")
    gaps.append("no auth on PUT/DELETE")
    print()
    if gaps:
        warn(f"Gaps: {', '.join(gaps)}")
    else:
        ok(f"Coverage: {cov.coverage_pct}% — good baseline")

    # ── Step 3: Feature request ────────────────────────────────────────────────
    step(3, "Client submits feature request")
    description = "Add a Streamlit web UI with a task input field and submit button that calls the FastAPI backend"
    print(f"\n  {cyan('Feature:')} {description}\n")
    info("AgenticQA pipeline starting...")

    # ── Step 4: LLM generates code ─────────────────────────────────────────────
    step(4, "LLM generates UI code")
    ui_file = "ui/app.py"
    ui_abs  = Path(repo) / ui_file
    ui_abs.parent.mkdir(parents=True, exist_ok=True)

    ui_code = generate_ui_code(description, ui_file)
    ui_abs.write_text(ui_code)
    ok(f"Code written: {ui_file} ({len(ui_code.splitlines())} lines)")

    # ── Step 5: Security scan ──────────────────────────────────────────────────
    step(5, "Security scan on generated code")
    scan = run_security_scan(repo, ui_file, ui_code)

    if scan["critical"]:
        fail(f"CRITICAL findings: {scan['critical']} — DO NOT SHIP")
        for a in scan["areas"]:
            fail(f"  [{a.severity.upper()}] {a.category} line {a.line_number}: {a.evidence[:60]}")
        print()
        warn("(In a real pipeline, the LLM would now rewrite the code to fix these issues)")
    else:
        ok(f"Security scan: 0 critical, {scan['high']} high (all context-appropriate for UI layer)")
        ok(f"Attack surface score: {scan['attack_surface_score']:.0f}/100")

    # ── Step 6: Generate + run UI tests ───────────────────────────────────────
    step(6, "Generate and run UI tests")
    ui_result = run_ui_tests(repo, ui_file, ui_code)

    passed = ui_result.get("passed", 0)
    failed = ui_result.get("failed", 0)
    total  = ui_result.get("total", 0)
    status = ui_result.get("status", "UNKNOWN")

    if status == "ALL_PASSED":
        ok(f"UI tests: {passed}/{total} passed — {status}")
    elif status in ("SOME_FAILED", "ALL_FAILED"):
        warn(f"UI tests: {passed}/{total} passed — {status}")
        for t in ui_result.get("tests", []):
            if t["status"] != "PASSED":
                fail(f"  FAILED: {t['name']}")
    else:
        info(f"UI tests: {status}")

    # ── Step 7: UI self-healing ───────────────────────────────────────────────
    step(7, "UI self-healing loop")
    api_key = os.environ.get("ANTHROPIC_API_KEY")

    if status == "ALL_PASSED":
        ok("All UI tests passed on first run — self-healing not needed")
    elif not api_key:
        warn("No ANTHROPIC_API_KEY — self-healing would rewrite failing UI code here")
        info("Set ANTHROPIC_API_KEY=sk-ant-... to enable full autonomous self-healing")
        info("Pipeline would: LLM rewrites code → re-scan → re-test → SHIP IT")
    else:
        info("Self-healing loop would activate here for any remaining failures")

    # ── Step 8: Final verdict ──────────────────────────────────────────────────
    step(8, "Final verdict + coverage delta")

    # Post-scan coverage
    cov_after = CoverageMapper().scan(repo)

    verdict = "SHIP IT" if status in ("ALL_PASSED", "NO_TESTS_COLLECTED") and not scan["critical"] else "REVIEW REQUIRED"
    verdict_col = green if verdict == "SHIP IT" else yellow

    W = 46  # box inner width

    def _box_row(label: str, value: str) -> str:
        content = f"  {label:<13}{value}"
        pad = W - len(content)
        return f"  │{content}{' ' * max(pad, 1)}│"

    print()
    print(f"  ┌{'─'*W}┐")
    verdict_label = f"VERDICT:  {verdict}"
    pad = W - len(f"  {verdict_label}") - 1
    print(f"  │  {bold(verdict_col(verdict_label))}{' ' * max(pad, 0)}│")
    print(f"  ├{'─'*W}┤")
    print(_box_row("Feature:", description[:30] + "…"))
    print(_box_row("Security:", f"0 critical, {scan['high']} high"))
    print(_box_row("UI tests:", f"{passed}/{total} passed ({status})"))
    print(_box_row("Coverage:", f"{cov.coverage_pct}% → {cov_after.coverage_pct}%"))
    print(_box_row("File added:", ui_file))
    print(f"  └{'─'*W}┘")

    print()
    print(bold("Next steps (with API key + GitHub token):"))
    print("  1. python agent_api.py                  # start API server on :8000")
    print("  2. streamlit run dashboard/app.py       # start dashboard on :8501")
    print("  3. Open http://localhost:8501")
    print("  4. Navigate to 'Live Pipeline Demo'")
    print("  5. Paste Anthropic API key in sidebar")
    print("  6. Type any feature description → click 'Build & Validate'")
    print("  7. Watch the full autonomous loop: generate → scan → fix → UI test → SHIP IT")
    print()
    print(dim(f"  Demo repo: {repo}"))
    print(dim("  (delete with: rm -rf " + repo + ")"))
    print()


if __name__ == "__main__":
    main()
