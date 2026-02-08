"""
RAGAS Score Persistence

Stores RAGAS evaluation scores per CI run in SQLite so quality trends
can be tracked over time. Detects regressions when scores drop below
historical baselines.
"""

import sqlite3
import json
from typing import Dict, List, Optional, Any
from datetime import datetime
from pathlib import Path
from dataclasses import dataclass


@dataclass
class RagasScore:
    id: Optional[int]
    run_id: str
    commit_sha: str
    branch: str
    metric_name: str  # faithfulness, answer_relevancy, context_precision, context_recall
    score: float
    agent_type: Optional[str]
    metadata: Dict[str, Any]
    timestamp: str


class RagasTracker:
    """Persists RAGAS evaluation metrics across CI runs."""

    METRICS = ("faithfulness", "answer_relevancy", "context_precision", "context_recall")

    def __init__(self, db_path: Optional[str] = None):
        if db_path is None:
            db_dir = Path.home() / ".agenticqa"
            db_dir.mkdir(exist_ok=True)
            db_path = str(db_dir / "ragas_scores.db")

        self.db_path = db_path
        self.conn = sqlite3.connect(db_path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self._init_schema()

    def _init_schema(self):
        cursor = self.conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS ragas_scores (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                run_id TEXT NOT NULL,
                commit_sha TEXT NOT NULL,
                branch TEXT NOT NULL DEFAULT 'main',
                metric_name TEXT NOT NULL,
                score REAL NOT NULL,
                agent_type TEXT,
                metadata TEXT,
                timestamp TEXT NOT NULL,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_ragas_run ON ragas_scores(run_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_ragas_metric ON ragas_scores(metric_name)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_ragas_ts ON ragas_scores(timestamp DESC)")
        self.conn.commit()

    def record_scores(
        self,
        run_id: str,
        commit_sha: str,
        scores: Dict[str, float],
        branch: str = "main",
        agent_type: Optional[str] = None,
        metadata: Optional[Dict] = None,
    ):
        """Record a set of RAGAS scores for a CI run."""
        cursor = self.conn.cursor()
        ts = datetime.utcnow().isoformat()
        meta_json = json.dumps(metadata or {})

        for metric_name, score in scores.items():
            cursor.execute(
                """INSERT INTO ragas_scores
                   (run_id, commit_sha, branch, metric_name, score, agent_type, metadata, timestamp)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (run_id, commit_sha, branch, metric_name, score, agent_type, meta_json, ts),
            )
        self.conn.commit()

    def get_trend(self, metric_name: str, limit: int = 20) -> List[RagasScore]:
        """Get recent score trend for a metric."""
        cursor = self.conn.cursor()
        cursor.execute(
            """SELECT * FROM ragas_scores
               WHERE metric_name = ? ORDER BY timestamp DESC LIMIT ?""",
            (metric_name, limit),
        )
        return [self._row_to_score(r) for r in cursor.fetchall()]

    def get_baseline(self, metric_name: str, window: int = 10) -> Optional[float]:
        """Get average score over the last N runs as the baseline."""
        cursor = self.conn.cursor()
        cursor.execute(
            """SELECT AVG(score) as avg_score FROM (
                 SELECT score FROM ragas_scores
                 WHERE metric_name = ? ORDER BY timestamp DESC LIMIT ?
               )""",
            (metric_name, window),
        )
        row = cursor.fetchone()
        return row["avg_score"] if row and row["avg_score"] is not None else None

    def check_regression(
        self, current_scores: Dict[str, float], threshold: float = 0.05
    ) -> Dict[str, Dict]:
        """
        Check if current scores regressed below baseline.

        Returns dict of regressed metrics with details.
        """
        regressions = {}
        for metric, score in current_scores.items():
            baseline = self.get_baseline(metric)
            if baseline is not None and score < baseline - threshold:
                regressions[metric] = {
                    "current": score,
                    "baseline": baseline,
                    "delta": score - baseline,
                }
        return regressions

    def get_run_summary(self, run_id: str) -> Dict[str, float]:
        """Get all scores for a specific run."""
        cursor = self.conn.cursor()
        cursor.execute(
            "SELECT metric_name, score FROM ragas_scores WHERE run_id = ?", (run_id,)
        )
        return {r["metric_name"]: r["score"] for r in cursor.fetchall()}

    def _row_to_score(self, row) -> RagasScore:
        return RagasScore(
            id=row["id"],
            run_id=row["run_id"],
            commit_sha=row["commit_sha"],
            branch=row["branch"],
            metric_name=row["metric_name"],
            score=row["score"],
            agent_type=row["agent_type"],
            metadata=json.loads(row["metadata"]) if row["metadata"] else {},
            timestamp=row["timestamp"],
        )

    def close(self):
        if self.conn:
            self.conn.close()
