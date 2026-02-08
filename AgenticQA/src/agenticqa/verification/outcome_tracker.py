"""
Delegation Outcome Tracker

Records predicted confidence vs actual outcome for every delegation,
enabling measurement of whether agent recommendations are accurate.
"""

import sqlite3
import json
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime
from pathlib import Path
from dataclasses import dataclass


@dataclass
class DelegationOutcome:
    id: Optional[int]
    delegation_id: str
    from_agent: str
    to_agent: str
    task_type: str
    predicted_confidence: float
    actual_success: bool
    duration_ms: Optional[float]
    recommendation_source: str  # 'graphrag', 'manual', 'fallback'
    metadata: Dict[str, Any]
    timestamp: str


class OutcomeTracker:
    """Tracks predicted vs actual outcomes for delegation decisions."""

    def __init__(self, db_path: Optional[str] = None):
        if db_path is None:
            db_dir = Path.home() / ".agenticqa"
            db_dir.mkdir(exist_ok=True)
            db_path = str(db_dir / "outcomes.db")

        self.db_path = db_path
        self.conn = sqlite3.connect(db_path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self._init_schema()

    def _init_schema(self):
        cursor = self.conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS delegation_outcomes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                delegation_id TEXT NOT NULL UNIQUE,
                from_agent TEXT NOT NULL,
                to_agent TEXT NOT NULL,
                task_type TEXT NOT NULL,
                predicted_confidence REAL NOT NULL,
                actual_success BOOLEAN,
                duration_ms REAL,
                recommendation_source TEXT NOT NULL DEFAULT 'graphrag',
                metadata TEXT,
                timestamp TEXT NOT NULL,
                outcome_recorded_at TEXT,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_outcome_agents ON delegation_outcomes(from_agent, to_agent)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_outcome_task ON delegation_outcomes(task_type)")
        self.conn.commit()

    def record_prediction(
        self,
        delegation_id: str,
        from_agent: str,
        to_agent: str,
        task_type: str,
        predicted_confidence: float,
        recommendation_source: str = "graphrag",
        metadata: Optional[Dict] = None,
    ):
        """Record a delegation prediction before execution."""
        cursor = self.conn.cursor()
        cursor.execute(
            """INSERT OR REPLACE INTO delegation_outcomes
               (delegation_id, from_agent, to_agent, task_type,
                predicted_confidence, recommendation_source, metadata, timestamp)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (delegation_id, from_agent, to_agent, task_type,
             predicted_confidence, recommendation_source,
             json.dumps(metadata or {}), datetime.utcnow().isoformat()),
        )
        self.conn.commit()

    def record_outcome(
        self,
        delegation_id: str,
        actual_success: bool,
        duration_ms: Optional[float] = None,
    ):
        """Record the actual outcome after delegation completes."""
        cursor = self.conn.cursor()
        cursor.execute(
            """UPDATE delegation_outcomes
               SET actual_success = ?, duration_ms = ?, outcome_recorded_at = ?
               WHERE delegation_id = ?""",
            (actual_success, duration_ms, datetime.utcnow().isoformat(), delegation_id),
        )
        self.conn.commit()

    def get_calibration(self, bucket_size: float = 0.1) -> List[Dict[str, Any]]:
        """
        Get prediction calibration: for each confidence bucket,
        what's the actual success rate?

        A well-calibrated system has actual_rate ~= predicted_confidence.
        """
        cursor = self.conn.cursor()
        cursor.execute(
            """SELECT
                 ROUND(predicted_confidence / ? ) * ? as bucket,
                 COUNT(*) as total,
                 SUM(CASE WHEN actual_success = 1 THEN 1 ELSE 0 END) as successes,
                 AVG(predicted_confidence) as avg_predicted
               FROM delegation_outcomes
               WHERE actual_success IS NOT NULL
               GROUP BY bucket
               ORDER BY bucket""",
            (bucket_size, bucket_size),
        )
        return [
            {
                "bucket": row["bucket"],
                "total": row["total"],
                "actual_rate": row["successes"] / row["total"] if row["total"] > 0 else 0,
                "avg_predicted": row["avg_predicted"],
            }
            for row in cursor.fetchall()
        ]

    def get_accuracy(self, confidence_threshold: float = 0.5) -> Dict[str, Any]:
        """Get overall prediction accuracy metrics."""
        cursor = self.conn.cursor()
        cursor.execute(
            """SELECT
                 COUNT(*) as total,
                 SUM(CASE WHEN (predicted_confidence >= ? AND actual_success = 1)
                           OR (predicted_confidence < ? AND actual_success = 0)
                      THEN 1 ELSE 0 END) as correct,
                 AVG(ABS(predicted_confidence - actual_success)) as avg_error
               FROM delegation_outcomes
               WHERE actual_success IS NOT NULL""",
            (confidence_threshold, confidence_threshold),
        )
        row = cursor.fetchone()
        total = row["total"] or 0
        correct = row["correct"] or 0
        return {
            "total_predictions": total,
            "correct_predictions": correct,
            "accuracy": correct / total if total > 0 else 0.0,
            "mean_absolute_error": row["avg_error"] or 0.0,
        }

    def get_agent_pair_accuracy(self) -> List[Dict[str, Any]]:
        """Get accuracy broken down by agent pair."""
        cursor = self.conn.cursor()
        cursor.execute(
            """SELECT from_agent, to_agent,
                 COUNT(*) as total,
                 AVG(predicted_confidence) as avg_confidence,
                 AVG(CASE WHEN actual_success = 1 THEN 1.0 ELSE 0.0 END) as actual_rate
               FROM delegation_outcomes
               WHERE actual_success IS NOT NULL
               GROUP BY from_agent, to_agent
               ORDER BY total DESC"""
        )
        return [dict(row) for row in cursor.fetchall()]

    def close(self):
        if self.conn:
            self.conn.close()
