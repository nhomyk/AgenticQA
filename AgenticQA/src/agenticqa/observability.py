"""Lightweight observability event store for agent actions."""

from __future__ import annotations

import json
import sqlite3
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Dict, List, Optional


class ObservabilityStore:
    """SQLite-backed store for trace and action events."""

    def __init__(self, db_path: Optional[str] = None):
        if not db_path:
            db_dir = Path.home() / ".agenticqa"
            db_dir.mkdir(exist_ok=True)
            db_path = str(db_dir / "observability.db")

        self.conn = sqlite3.connect(db_path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self._init_schema()

    def _init_schema(self) -> None:
        c = self.conn.cursor()
        c.execute(
            """
            CREATE TABLE IF NOT EXISTS agent_action_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                trace_id TEXT NOT NULL,
                request_id TEXT,
                agent TEXT NOT NULL,
                action TEXT NOT NULL,
                status TEXT NOT NULL,
                started_at TEXT,
                ended_at TEXT,
                latency_ms REAL,
                error TEXT,
                metadata_json TEXT,
                created_at TEXT NOT NULL
            )
            """
        )
        c.execute("CREATE INDEX IF NOT EXISTS idx_obs_trace ON agent_action_events(trace_id)")
        c.execute("CREATE INDEX IF NOT EXISTS idx_obs_request ON agent_action_events(request_id)")
        c.execute("CREATE INDEX IF NOT EXISTS idx_obs_agent_action ON agent_action_events(agent, action)")
        c.execute("CREATE INDEX IF NOT EXISTS idx_obs_created ON agent_action_events(created_at)")
        self.conn.commit()

    def log_event(
        self,
        trace_id: str,
        request_id: Optional[str],
        agent: str,
        action: str,
        status: str,
        started_at: Optional[str] = None,
        ended_at: Optional[str] = None,
        latency_ms: Optional[float] = None,
        error: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> int:
        now = datetime.now(UTC).isoformat()
        c = self.conn.cursor()
        c.execute(
            """
            INSERT INTO agent_action_events (
                trace_id, request_id, agent, action, status,
                started_at, ended_at, latency_ms, error, metadata_json, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                trace_id,
                request_id,
                agent,
                action,
                status,
                started_at,
                ended_at,
                latency_ms,
                error,
                json.dumps(metadata or {}),
                now,
            ),
        )
        self.conn.commit()
        return int(c.lastrowid)

    def list_events(
        self,
        limit: int = 100,
        trace_id: Optional[str] = None,
        request_id: Optional[str] = None,
        agent: Optional[str] = None,
        action: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        limit = min(max(limit, 1), 1000)
        where: List[str] = []
        params: List[Any] = []

        if trace_id:
            where.append("trace_id = ?")
            params.append(trace_id)
        if request_id:
            where.append("request_id = ?")
            params.append(request_id)
        if agent:
            where.append("agent = ?")
            params.append(agent)
        if action:
            where.append("action = ?")
            params.append(action)

        clause = f"WHERE {' AND '.join(where)}" if where else ""
        c = self.conn.cursor()
        c.execute(
            f"""
            SELECT *
            FROM agent_action_events
            {clause}
            ORDER BY id DESC
            LIMIT ?
            """,
            [*params, limit],
        )

        return [self._row_to_event(dict(r)) for r in c.fetchall()]

    def list_traces(self, limit: int = 100) -> List[Dict[str, Any]]:
        limit = min(max(limit, 1), 1000)
        c = self.conn.cursor()
        c.execute(
            """
            SELECT
                trace_id,
                MAX(request_id) AS request_id,
                COUNT(*) AS event_count,
                MIN(COALESCE(started_at, created_at)) AS started_at,
                MAX(COALESCE(ended_at, created_at)) AS ended_at,
                MAX(id) AS last_event_id
            FROM agent_action_events
            GROUP BY trace_id
            ORDER BY last_event_id DESC
            LIMIT ?
            """,
            (limit,),
        )

        rows = [dict(r) for r in c.fetchall()]
        for row in rows:
            c.execute(
                "SELECT status, agent, action FROM agent_action_events WHERE id = ?",
                (row["last_event_id"],),
            )
            last = c.fetchone()
            row["last_status"] = (dict(last).get("status") if last else None)
            row["last_agent"] = (dict(last).get("agent") if last else None)
            row["last_action"] = (dict(last).get("action") if last else None)
            row.pop("last_event_id", None)
        return rows

    def get_trace(self, trace_id: str, limit: int = 500) -> Dict[str, Any]:
        events = self.list_events(limit=limit, trace_id=trace_id)
        return {
            "trace_id": trace_id,
            "event_count": len(events),
            "events": events,
        }

    def _row_to_event(self, row: Dict[str, Any]) -> Dict[str, Any]:
        try:
            row["metadata"] = json.loads(row.pop("metadata_json") or "{}")
        except Exception:
            row["metadata"] = {}
            row.pop("metadata_json", None)
        return row

    def close(self) -> None:
        self.conn.close()
