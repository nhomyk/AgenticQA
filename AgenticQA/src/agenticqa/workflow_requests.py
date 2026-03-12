"""Prompt-driven workflow request store and state transitions for AgenticQA control plane."""

from __future__ import annotations

import json
import logging
import sqlite3
import threading
import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


TERMINAL_STATUSES = {"COMPLETED", "FAILED", "CANCELLED"}


class PromptWorkflowStore:
    """SQLite-backed store for prompt intake and workflow lifecycle state."""

    VALID_STATUSES = {
        "RECEIVED",
        "PLANNED",
        "AWAITING_APPROVAL",
        "APPROVED",
        "QUEUED",
        "IN_PROGRESS",
        "COMPLETED",
        "FAILED",
        "CANCELLED",
    }

    def __init__(self, db_path: Optional[str] = None):
        if not db_path:
            db_dir = Path.home() / ".agenticqa"
            db_dir.mkdir(exist_ok=True)
            db_path = str(db_dir / "workflow_requests.db")

        self.conn = sqlite3.connect(db_path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self._lock = threading.Lock()
        self._init_schema()
        self._migrate_schema()

    def _init_schema(self) -> None:
        c = self.conn.cursor()
        c.execute(
            """
            CREATE TABLE IF NOT EXISTS workflow_requests (
                id TEXT PRIMARY KEY,
                prompt TEXT NOT NULL,
                repo TEXT NOT NULL,
                requester TEXT NOT NULL,
                status TEXT NOT NULL,
                plan_json TEXT,
                branch_name TEXT,
                commit_sha TEXT,
                pr_url TEXT,
                next_action TEXT,
                error_message TEXT,
                metadata TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """
        )
        c.execute(
            """
            CREATE TABLE IF NOT EXISTS workflow_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                request_id TEXT NOT NULL,
                from_status TEXT,
                to_status TEXT NOT NULL,
                note TEXT,
                timestamp TEXT NOT NULL
            )
            """
        )
        c.execute(
            """
            CREATE TABLE IF NOT EXISTS chat_sessions (
                id TEXT PRIMARY KEY,
                repo TEXT NOT NULL,
                requester TEXT NOT NULL,
                metadata TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """
        )
        c.execute(
            """
            CREATE TABLE IF NOT EXISTS chat_messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT NOT NULL,
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                metadata TEXT,
                request_id TEXT,
                created_at TEXT NOT NULL
            )
            """
        )
        c.execute("CREATE INDEX IF NOT EXISTS idx_workflow_status ON workflow_requests(status)")
        c.execute("CREATE INDEX IF NOT EXISTS idx_workflow_created ON workflow_requests(created_at DESC)")
        c.execute("CREATE INDEX IF NOT EXISTS idx_chat_sessions_created ON chat_sessions(created_at DESC)")
        c.execute("CREATE INDEX IF NOT EXISTS idx_chat_messages_session_created ON chat_messages(session_id, created_at)")
        self.conn.commit()

    def _migrate_schema(self) -> None:
        """Add columns needed for concurrent worker support."""
        c = self.conn.cursor()
        existing = {row[1] for row in c.execute("PRAGMA table_info(workflow_requests)").fetchall()}
        migrations = [
            ("worker_id", "TEXT"),
            ("worktree_path", "TEXT"),
        ]
        for col, col_type in migrations:
            if col not in existing:
                c.execute(f"ALTER TABLE workflow_requests ADD COLUMN {col} {col_type}")
                logger.info("migrated workflow_requests: added column %s", col)
        self.conn.commit()

    # ── Concurrent worker methods ────────────────────────────────────────────

    def atomic_pickup(self, worker_id: str) -> Optional[Dict[str, Any]]:
        """Atomically claim the oldest QUEUED request for a worker.

        Uses BEGIN IMMEDIATE to acquire a reserved lock before the SELECT,
        preventing TOCTOU races between concurrent workers.
        """
        with self._lock:
            now = datetime.now(UTC).isoformat()
            c = self.conn.cursor()
            try:
                c.execute("BEGIN IMMEDIATE")
                row = c.execute(
                    "SELECT id, status FROM workflow_requests "
                    "WHERE status = 'QUEUED' ORDER BY created_at ASC LIMIT 1"
                ).fetchone()
                if not row:
                    self.conn.commit()
                    return None

                request_id = row["id"]
                c.execute(
                    "UPDATE workflow_requests SET status = 'IN_PROGRESS', "
                    "next_action = 'execute_changes', worker_id = ?, updated_at = ? "
                    "WHERE id = ? AND status = 'QUEUED'",
                    (worker_id, now, request_id),
                )
                if c.rowcount == 0:
                    self.conn.commit()
                    return None

                c.execute(
                    "INSERT INTO workflow_events "
                    "(request_id, from_status, to_status, note, timestamp) "
                    "VALUES (?, ?, ?, ?, ?)",
                    (request_id, "QUEUED", "IN_PROGRESS",
                     f"Picked up by worker {worker_id}", now),
                )
                self.conn.commit()
            except Exception:
                self.conn.rollback()
                raise

        return self.get_request(request_id)

    def create_and_queue_request(
        self,
        prompt: str,
        repo: str,
        requester: str = "dashboard",
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Create a request directly in QUEUED state for auto-execution.

        Skips the AWAITING_APPROVAL → APPROVED manual steps and logs
        fast-path transitions for audit trail.
        """
        now = datetime.now(UTC).isoformat()
        request_id = f"wr_{uuid.uuid4().hex[:12]}"
        plan = self._build_plan(prompt=prompt, repo=repo)

        meta = dict(metadata or {})
        meta["auto_queued"] = True

        c = self.conn.cursor()
        c.execute(
            """
            INSERT INTO workflow_requests (
                id, prompt, repo, requester, status, plan_json,
                next_action, metadata, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                request_id, prompt, repo, requester, "QUEUED",
                json.dumps(plan), "worker_pickup", json.dumps(meta), now, now,
            ),
        )
        # Log the fast-path transitions for the audit trail
        for from_s, to_s, note in [
            ("RECEIVED", "PLANNED", "Prompt ingested and plan generated"),
            ("PLANNED", "AWAITING_APPROVAL", "Auto-queue: skipped approval"),
            ("AWAITING_APPROVAL", "APPROVED", "Auto-queue: auto-approved"),
            ("APPROVED", "QUEUED", "Auto-queue: queued for worker pickup"),
        ]:
            c.execute(
                "INSERT INTO workflow_events "
                "(request_id, from_status, to_status, note, timestamp) "
                "VALUES (?, ?, ?, ?, ?)",
                (request_id, from_s, to_s, note, now),
            )
        self.conn.commit()
        logger.info("auto-queued request %s for repo %s", request_id, repo)
        return self.get_request(request_id)

    def reclaim_stale_requests(self, timeout_minutes: int = 30) -> List[str]:
        """Move stale IN_PROGRESS requests back to QUEUED.

        Called on startup to recover from worker crashes. Returns list
        of reclaimed request IDs.
        """
        cutoff = (datetime.now(UTC) - timedelta(minutes=timeout_minutes)).isoformat()
        now = datetime.now(UTC).isoformat()
        reclaimed: list[str] = []

        with self._lock:
            c = self.conn.cursor()
            rows = c.execute(
                "SELECT id FROM workflow_requests "
                "WHERE status = 'IN_PROGRESS' AND updated_at < ?",
                (cutoff,),
            ).fetchall()

            for row in rows:
                rid = row["id"]
                c.execute(
                    "UPDATE workflow_requests SET status = 'QUEUED', "
                    "next_action = 'worker_pickup', worker_id = NULL, "
                    "worktree_path = NULL, updated_at = ? "
                    "WHERE id = ?",
                    (now, rid),
                )
                c.execute(
                    "INSERT INTO workflow_events "
                    "(request_id, from_status, to_status, note, timestamp) "
                    "VALUES (?, ?, ?, ?, ?)",
                    (rid, "IN_PROGRESS", "QUEUED",
                     f"Reclaimed after {timeout_minutes}min timeout", now),
                )
                reclaimed.append(rid)
                logger.warning("reclaimed stale request %s", rid)

            if reclaimed:
                self.conn.commit()

        return reclaimed

    def set_worktree_path(self, request_id: str, path: str) -> None:
        """Record which git worktree is handling this request."""
        with self._lock:
            now = datetime.now(UTC).isoformat()
            c = self.conn.cursor()
            c.execute(
                "UPDATE workflow_requests SET worktree_path = ?, updated_at = ? WHERE id = ?",
                (path, now, request_id),
            )
            self.conn.commit()

    def get_queue_status(self) -> Dict[str, Any]:
        """Return a snapshot of the queue for dashboard display."""
        with self._lock:
            c = self.conn.cursor()
            queued = c.execute(
                "SELECT COUNT(*) FROM workflow_requests WHERE status = 'QUEUED'"
            ).fetchone()[0]
            in_progress = c.execute(
                "SELECT COUNT(*) FROM workflow_requests WHERE status = 'IN_PROGRESS'"
            ).fetchone()[0]
            recent_completed = c.execute(
                "SELECT id, prompt, repo, updated_at FROM workflow_requests "
                "WHERE status IN ('COMPLETED', 'FAILED') "
                "ORDER BY updated_at DESC LIMIT 10"
            ).fetchall()
            active_workers = c.execute(
                "SELECT id, prompt, repo, worker_id, worktree_path, updated_at "
                "FROM workflow_requests WHERE status = 'IN_PROGRESS' "
                "ORDER BY updated_at ASC"
            ).fetchall()

            return {
                "queued": queued,
                "in_progress": in_progress,
                "active_jobs": [dict(r) for r in active_workers],
                "recent_completed": [dict(r) for r in recent_completed],
            }

    # ── Chat methods ─────────────────────────────────────────────────────────

    def create_chat_session(
        self,
        repo: str,
        requester: str = "dashboard",
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        now = datetime.now(UTC).isoformat()
        session_id = f"cs_{uuid.uuid4().hex[:12]}"
        c = self.conn.cursor()
        c.execute(
            """
            INSERT INTO chat_sessions (id, repo, requester, metadata, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                session_id,
                repo,
                requester,
                json.dumps(metadata or {}),
                now,
                now,
            ),
        )
        self.conn.commit()
        return self.get_chat_session(session_id) or {}

    def list_chat_sessions(self, limit: int = 25) -> List[Dict[str, Any]]:
        capped = min(max(limit, 1), 200)
        c = self.conn.cursor()
        rows = c.execute(
            "SELECT * FROM chat_sessions ORDER BY created_at DESC LIMIT ?",
            (capped,),
        ).fetchall()
        return [self._row_to_chat_session(r) for r in rows]

    def get_chat_session(self, session_id: str, message_limit: int = 200) -> Optional[Dict[str, Any]]:
        c = self.conn.cursor()
        row = c.execute("SELECT * FROM chat_sessions WHERE id = ?", (session_id,)).fetchone()
        if not row:
            return None
        session = self._row_to_chat_session(row)
        msg_rows = c.execute(
            """
            SELECT id, session_id, role, content, metadata, request_id, created_at
            FROM chat_messages
            WHERE session_id = ?
            ORDER BY id ASC
            LIMIT ?
            """,
            (session_id, min(max(message_limit, 1), 500)),
        ).fetchall()
        session["messages"] = [self._row_to_chat_message(m) for m in msg_rows]
        return session

    def add_chat_message(
        self,
        session_id: str,
        role: str,
        content: str,
        metadata: Optional[Dict[str, Any]] = None,
        request_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        role_normalized = (role or "").strip().lower()
        if role_normalized not in {"system", "user", "assistant", "tool"}:
            raise ValueError("invalid_chat_role")

        c = self.conn.cursor()
        existing = c.execute("SELECT id FROM chat_sessions WHERE id = ?", (session_id,)).fetchone()
        if not existing:
            raise ValueError("chat_session_not_found")

        now = datetime.now(UTC).isoformat()
        c.execute(
            """
            INSERT INTO chat_messages (session_id, role, content, metadata, request_id, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                session_id,
                role_normalized,
                content,
                json.dumps(metadata or {}),
                request_id,
                now,
            ),
        )
        message_id = c.lastrowid
        c.execute("UPDATE chat_sessions SET updated_at = ? WHERE id = ?", (now, session_id))
        self.conn.commit()

        row = c.execute(
            """
            SELECT id, session_id, role, content, metadata, request_id, created_at
            FROM chat_messages
            WHERE id = ?
            """,
            (message_id,),
        ).fetchone()
        return self._row_to_chat_message(row)

    def create_request(
        self,
        prompt: str,
        repo: str,
        requester: str = "dashboard",
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        now = datetime.now(UTC).isoformat()
        request_id = f"wr_{uuid.uuid4().hex[:12]}"

        plan = self._build_plan(prompt=prompt, repo=repo)
        status = "AWAITING_APPROVAL"

        c = self.conn.cursor()
        c.execute(
            """
            INSERT INTO workflow_requests (
                id, prompt, repo, requester, status, plan_json,
                next_action, metadata, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                request_id,
                prompt,
                repo,
                requester,
                status,
                json.dumps(plan),
                "approve_to_queue",
                json.dumps(metadata or {}),
                now,
                now,
            ),
        )
        c.execute(
            "INSERT INTO workflow_events (request_id, from_status, to_status, note, timestamp) VALUES (?, ?, ?, ?, ?)",
            (request_id, "RECEIVED", "PLANNED", "Prompt ingested and plan generated", now),
        )
        c.execute(
            "INSERT INTO workflow_events (request_id, from_status, to_status, note, timestamp) VALUES (?, ?, ?, ?, ?)",
            (request_id, "PLANNED", status, "Waiting for execution approval", now),
        )
        self.conn.commit()
        return self.get_request(request_id)

    def list_requests(self, limit: int = 50) -> List[Dict[str, Any]]:
        with self._lock:
            c = self.conn.cursor()
            rows = c.execute(
                "SELECT * FROM workflow_requests ORDER BY created_at DESC LIMIT ?",
                (limit,),
            ).fetchall()
            return [self._row_to_request(r) for r in rows]

    def get_request(self, request_id: str) -> Optional[Dict[str, Any]]:
        with self._lock:
            c = self.conn.cursor()
            row = c.execute("SELECT * FROM workflow_requests WHERE id = ?", (request_id,)).fetchone()
            if not row:
                return None

            req = self._row_to_request(row)
            events = c.execute(
                "SELECT from_status, to_status, note, timestamp FROM workflow_events WHERE request_id = ? ORDER BY id ASC",
                (request_id,),
            ).fetchall()
            req["events"] = [dict(ev) for ev in events]
            return req

    def approve_request(self, request_id: str) -> Dict[str, Any]:
        req = self.get_request(request_id)
        if not req:
            raise ValueError("request_not_found")
        if req["status"] in TERMINAL_STATUSES:
            return req

        self._transition(
            request_id,
            expected_statuses={"AWAITING_APPROVAL", "PLANNED"},
            to_status="APPROVED",
            next_action="queue_for_execution",
            note="Approved for execution",
        )
        return self.get_request(request_id) or req

    def queue_request(self, request_id: str) -> Dict[str, Any]:
        req = self.get_request(request_id)
        if not req:
            raise ValueError("request_not_found")
        if req["status"] in TERMINAL_STATUSES:
            return req

        self._transition(
            request_id,
            expected_statuses={"APPROVED"},
            to_status="QUEUED",
            next_action="worker_pickup",
            note="Request queued for worker execution",
        )
        return self.get_request(request_id) or req

    def get_next_queued_request(self) -> Optional[Dict[str, Any]]:
        with self._lock:
            c = self.conn.cursor()
            row = c.execute(
                "SELECT id FROM workflow_requests WHERE status = 'QUEUED' ORDER BY created_at ASC LIMIT 1"
            ).fetchone()
        if not row:
            return None
        return self.get_request(row["id"])

    def start_request(self, request_id: str, note: str = "Worker execution started") -> Dict[str, Any]:
        req = self.get_request(request_id)
        if not req:
            raise ValueError("request_not_found")
        if req["status"] in TERMINAL_STATUSES:
            return req

        self._transition(
            request_id,
            expected_statuses={"QUEUED"},
            to_status="IN_PROGRESS",
            next_action="execute_changes",
            note=note,
        )
        return self.get_request(request_id) or req

    def complete_request(
        self,
        request_id: str,
        branch_name: Optional[str] = None,
        commit_sha: Optional[str] = None,
        pr_url: Optional[str] = None,
        note: str = "Execution completed",
    ) -> Dict[str, Any]:
        req = self.get_request(request_id)
        if not req:
            raise ValueError("request_not_found")

        self._transition(
            request_id,
            expected_statuses={"IN_PROGRESS", "QUEUED"},
            to_status="COMPLETED",
            next_action="none",
            note=note,
            extra_updates={
                "branch_name": branch_name,
                "commit_sha": commit_sha,
                "pr_url": pr_url,
                "error_message": None,
            },
        )
        return self.get_request(request_id) or req

    def fail_request(
        self,
        request_id: str,
        error_message: str,
        branch_name: Optional[str] = None,
        commit_sha: Optional[str] = None,
        pr_url: Optional[str] = None,
        note: str = "Execution failed",
    ) -> Dict[str, Any]:
        req = self.get_request(request_id)
        if not req:
            raise ValueError("request_not_found")
        if req["status"] in TERMINAL_STATUSES:
            return req

        self._transition(
            request_id,
            expected_statuses=self.VALID_STATUSES - TERMINAL_STATUSES,
            to_status="FAILED",
            next_action="manual_review",
            note=note,
            extra_updates={
                "branch_name": branch_name,
                "commit_sha": commit_sha,
                "pr_url": pr_url,
                "error_message": error_message[:2000],
            },
        )
        return self.get_request(request_id) or req

    def cancel_request(self, request_id: str, reason: str = "cancelled_by_user") -> Dict[str, Any]:
        req = self.get_request(request_id)
        if not req:
            raise ValueError("request_not_found")
        if req["status"] in TERMINAL_STATUSES:
            return req

        self._transition(
            request_id,
            expected_statuses=self.VALID_STATUSES - TERMINAL_STATUSES,
            to_status="CANCELLED",
            next_action="none",
            note=reason,
        )
        return self.get_request(request_id) or req

    def replay_request(self, request_id: str, requester: str = "replay") -> Dict[str, Any]:
        """Create a replay request from a prior workflow item and queue it immediately."""
        req = self.get_request(request_id)
        if not req:
            raise ValueError("request_not_found")

        metadata = dict(req.get("metadata") or {})
        metadata["replay_of"] = request_id
        metadata["source"] = "workflow_replay"
        metadata["self_heal"] = True

        replay = self.create_request(
            prompt=req.get("prompt", ""),
            repo=req.get("repo", "."),
            requester=requester,
            metadata=metadata,
        )
        replay_id = replay["id"]
        self.approve_request(replay_id)
        return self.queue_request(replay_id)

    def get_metrics(self, lookback_limit: int = 200) -> Dict[str, Any]:
        """Compute operational outcomes for Prompt Ops workflows."""
        items = self.list_requests(limit=min(max(lookback_limit, 10), 1000))
        if not items:
            return {
                "total_requests": 0,
                "completed": 0,
                "failed": 0,
                "mttr_minutes": None,
                "pass_rate": 0.0,
                "pass_rate_uplift_pct": 0.0,
                "flaky_reduction_pct": 0.0,
            }

        completed = [r for r in items if r.get("status") == "COMPLETED"]
        failed = [r for r in items if r.get("status") == "FAILED"]
        terminal = [r for r in items if r.get("status") in {"COMPLETED", "FAILED", "CANCELLED"}]

        mttr_values = []
        for r in terminal:
            try:
                created = datetime.fromisoformat(r["created_at"])
                updated = datetime.fromisoformat(r["updated_at"])
                delta_min = max(0.0, (updated - created).total_seconds() / 60.0)
                mttr_values.append(delta_min)
            except Exception:
                continue

        pass_rate = (len(completed) / max(1, len(completed) + len(failed)))

        recent = items[: min(20, len(items))]
        older = items[min(20, len(items)) : min(40, len(items))]
        recent_pass = self._pass_rate_for(recent)
        older_pass = self._pass_rate_for(older)
        uplift = (recent_pass - older_pass) * 100.0 if older else 0.0

        recent_flaky = self._flaky_rate_for(recent)
        older_flaky = self._flaky_rate_for(older)
        flaky_reduction = max(0.0, (older_flaky - recent_flaky) * 100.0)

        return {
            "total_requests": len(items),
            "completed": len(completed),
            "failed": len(failed),
            "mttr_minutes": round(sum(mttr_values) / len(mttr_values), 2) if mttr_values else None,
            "pass_rate": round(pass_rate, 4),
            "pass_rate_uplift_pct": round(uplift, 2),
            "flaky_reduction_pct": round(flaky_reduction, 2),
        }

    def _transition(
        self,
        request_id: str,
        expected_statuses: set,
        to_status: str,
        next_action: str,
        note: str,
        extra_updates: Optional[Dict[str, Any]] = None,
    ) -> None:
        with self._lock:
            now = datetime.now(UTC).isoformat()
            c = self.conn.cursor()
            row = c.execute("SELECT status FROM workflow_requests WHERE id = ?", (request_id,)).fetchone()
            if not row:
                raise ValueError("request_not_found")

            current = row["status"]
            if current not in expected_statuses:
                raise ValueError(f"invalid_transition:{current}->{to_status}")

            update_pairs = {
                "status": to_status,
                "next_action": next_action,
                "updated_at": now,
            }
            if extra_updates:
                update_pairs.update(extra_updates)

            # Whitelist allowed column names to prevent SQL column injection
            _ALLOWED_COLUMNS = frozenset({
                "status", "next_action", "updated_at",
                "branch_name", "commit_sha", "pr_url", "error_message",
            })
            invalid = set(update_pairs.keys()) - _ALLOWED_COLUMNS
            if invalid:
                raise ValueError(f"Attempt to update disallowed columns: {invalid}")
            assignments = ", ".join([f"{k} = ?" for k in update_pairs.keys()])
            values = list(update_pairs.values()) + [request_id]
            c.execute(f"UPDATE workflow_requests SET {assignments} WHERE id = ?", values)
            c.execute(
                "INSERT INTO workflow_events (request_id, from_status, to_status, note, timestamp) VALUES (?, ?, ?, ?, ?)",
                (request_id, current, to_status, note, now),
            )
            self.conn.commit()

    def _build_plan(self, prompt: str, repo: str) -> Dict[str, Any]:
        normalized = prompt.lower()

        scope = []
        if any(k in normalized for k in ["test", "coverage", "pytest"]):
            scope.append("tests")
        if any(k in normalized for k in ["api", "endpoint", "route"]):
            scope.append("api")
        if any(k in normalized for k in ["ui", "dashboard", "streamlit"]):
            scope.append("dashboard")
        if not scope:
            scope.append("general")

        return {
            "repo": repo,
            "intent_summary": prompt[:280],
            "work_items": [
                "Analyze request and impacted files",
                "Implement code changes",
                "Run focused tests",
                "Prepare commit + PR metadata",
            ],
            "scope_tags": scope,
            "risk_tier": "medium" if "delete" in normalized or "migration" in normalized else "low",
            "acceptance": [
                "No syntax errors",
                "Relevant tests pass",
                "No policy violations",
            ],
        }

    def _pass_rate_for(self, items: List[Dict[str, Any]]) -> float:
        completed = len([r for r in items if r.get("status") == "COMPLETED"])
        failed = len([r for r in items if r.get("status") == "FAILED"])
        if completed + failed == 0:
            return 0.0
        return completed / (completed + failed)

    def _flaky_rate_for(self, items: List[Dict[str, Any]]) -> float:
        # Proxy for instability: queued/in-progress/cancelled/failed over total
        unstable = len(
            [
                r
                for r in items
                if r.get("status") in {"FAILED", "CANCELLED", "QUEUED", "IN_PROGRESS"}
            ]
        )
        if not items:
            return 0.0
        return unstable / len(items)

    def _row_to_request(self, row: sqlite3.Row) -> Dict[str, Any]:
        plan = json.loads(row["plan_json"]) if row["plan_json"] else None
        metadata = json.loads(row["metadata"]) if row["metadata"] else {}
        # worker_id / worktree_path may not exist on old DBs before migration
        keys = row.keys() if hasattr(row, "keys") else []
        return {
            "id": row["id"],
            "prompt": row["prompt"],
            "repo": row["repo"],
            "requester": row["requester"],
            "status": row["status"],
            "plan": plan,
            "branch_name": row["branch_name"],
            "commit_sha": row["commit_sha"],
            "pr_url": row["pr_url"],
            "next_action": row["next_action"],
            "error_message": row["error_message"],
            "metadata": metadata,
            "worker_id": row["worker_id"] if "worker_id" in keys else None,
            "worktree_path": row["worktree_path"] if "worktree_path" in keys else None,
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
        }

    def _row_to_chat_session(self, row: sqlite3.Row) -> Dict[str, Any]:
        metadata = json.loads(row["metadata"]) if row["metadata"] else {}
        return {
            "id": row["id"],
            "repo": row["repo"],
            "requester": row["requester"],
            "metadata": metadata,
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
        }

    def _row_to_chat_message(self, row: sqlite3.Row) -> Dict[str, Any]:
        metadata = json.loads(row["metadata"]) if row["metadata"] else {}
        return {
            "id": row["id"],
            "session_id": row["session_id"],
            "role": row["role"],
            "content": row["content"],
            "metadata": metadata,
            "request_id": row["request_id"],
            "created_at": row["created_at"],
        }

    def close(self) -> None:
        if self.conn:
            self.conn.close()
