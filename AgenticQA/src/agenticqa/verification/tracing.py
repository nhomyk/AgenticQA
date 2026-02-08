"""
End-to-End Pipeline Tracing

Assigns a trace ID to every request that follows it through:
input validation -> agent decision -> RAG retrieval -> delegation -> outcome.
Enables full pipeline debugging and latency attribution.
"""

import uuid
import time
import sqlite3
import json
from typing import Dict, List, Optional, Any
from datetime import datetime
from pathlib import Path
from dataclasses import dataclass, field
from contextlib import contextmanager


@dataclass
class SpanRecord:
    trace_id: str
    span_id: str
    parent_span_id: Optional[str]
    operation: str  # 'agent_execute', 'rag_retrieve', 'delegation', 'validation'
    agent: Optional[str]
    start_time: float
    end_time: Optional[float] = None
    status: str = "in_progress"
    metadata: Dict[str, Any] = field(default_factory=dict)

    @property
    def duration_ms(self) -> Optional[float]:
        if self.end_time is not None:
            return (self.end_time - self.start_time) * 1000
        return None


class Tracer:
    """Lightweight tracing for the AgenticQA pipeline."""

    def __init__(self, db_path: Optional[str] = None):
        if db_path is None:
            db_dir = Path.home() / ".agenticqa"
            db_dir.mkdir(exist_ok=True)
            db_path = str(db_dir / "traces.db")

        self.db_path = db_path
        self.conn = sqlite3.connect(db_path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self._init_schema()

    def _init_schema(self):
        cursor = self.conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS spans (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                trace_id TEXT NOT NULL,
                span_id TEXT NOT NULL UNIQUE,
                parent_span_id TEXT,
                operation TEXT NOT NULL,
                agent TEXT,
                start_time REAL NOT NULL,
                end_time REAL,
                duration_ms REAL,
                status TEXT NOT NULL DEFAULT 'in_progress',
                metadata TEXT,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_trace ON spans(trace_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_span ON spans(span_id)")
        self.conn.commit()

    def new_trace(self) -> str:
        """Create a new trace ID."""
        return str(uuid.uuid4())

    @contextmanager
    def span(
        self,
        trace_id: str,
        operation: str,
        agent: Optional[str] = None,
        parent_span_id: Optional[str] = None,
        metadata: Optional[Dict] = None,
    ):
        """
        Context manager that records a span.

        Usage:
            with tracer.span(trace_id, "rag_retrieve", agent="qa") as span_id:
                results = retriever.search(...)
        """
        span_id = str(uuid.uuid4())
        start = time.time()
        status = "success"

        try:
            yield span_id
        except Exception:
            status = "error"
            raise
        finally:
            end = time.time()
            duration = (end - start) * 1000
            cursor = self.conn.cursor()
            cursor.execute(
                """INSERT INTO spans
                   (trace_id, span_id, parent_span_id, operation, agent,
                    start_time, end_time, duration_ms, status, metadata)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (trace_id, span_id, parent_span_id, operation, agent,
                 start, end, duration, status, json.dumps(metadata or {})),
            )
            self.conn.commit()

    def get_trace(self, trace_id: str) -> List[Dict[str, Any]]:
        """Get all spans for a trace, ordered by start time."""
        cursor = self.conn.cursor()
        cursor.execute(
            "SELECT * FROM spans WHERE trace_id = ? ORDER BY start_time",
            (trace_id,),
        )
        return [dict(r) for r in cursor.fetchall()]

    def get_trace_summary(self, trace_id: str) -> Dict[str, Any]:
        """Get a summary of a trace including total duration and span count."""
        spans = self.get_trace(trace_id)
        if not spans:
            return {"trace_id": trace_id, "spans": 0}

        total_duration = sum(s.get("duration_ms", 0) or 0 for s in spans)
        operations = {}
        for s in spans:
            op = s["operation"]
            operations[op] = operations.get(op, 0) + (s.get("duration_ms", 0) or 0)

        return {
            "trace_id": trace_id,
            "spans": len(spans),
            "total_duration_ms": total_duration,
            "by_operation": operations,
            "status": "error" if any(s["status"] == "error" for s in spans) else "success",
        }

    def get_slow_traces(self, min_duration_ms: float = 5000, limit: int = 20) -> List[Dict]:
        """Find traces that exceeded a duration threshold."""
        cursor = self.conn.cursor()
        cursor.execute(
            """SELECT trace_id, COUNT(*) as span_count,
                      SUM(duration_ms) as total_ms,
                      MIN(start_time) as first_span
               FROM spans
               GROUP BY trace_id
               HAVING total_ms >= ?
               ORDER BY total_ms DESC
               LIMIT ?""",
            (min_duration_ms, limit),
        )
        return [dict(r) for r in cursor.fetchall()]

    def close(self):
        if self.conn:
            self.conn.close()
