"""
Relevance Feedback Loop

When a retrieved document leads to a successful agent decision, its
relevance score is boosted. When it leads to failure, the score is
penalized. Over time, better documents float to the top.
"""

import sqlite3
import json
from typing import Dict, List, Optional, Any
from datetime import datetime
from pathlib import Path


class RelevanceFeedback:
    """Tracks which retrieved documents contributed to good/bad outcomes."""

    DEFAULT_BOOST = 0.05
    DEFAULT_PENALTY = 0.03

    def __init__(self, db_path: Optional[str] = None):
        if db_path is None:
            db_dir = Path.home() / ".agenticqa"
            db_dir.mkdir(exist_ok=True)
            db_path = str(db_dir / "feedback.db")

        self.db_path = db_path
        self.conn = sqlite3.connect(db_path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self._init_schema()

    def _init_schema(self):
        cursor = self.conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS document_scores (
                doc_id TEXT PRIMARY KEY,
                doc_type TEXT NOT NULL,
                base_score REAL NOT NULL DEFAULT 1.0,
                adjustment REAL NOT NULL DEFAULT 0.0,
                times_retrieved INTEGER NOT NULL DEFAULT 0,
                times_helpful INTEGER NOT NULL DEFAULT 0,
                times_unhelpful INTEGER NOT NULL DEFAULT 0,
                last_updated TEXT NOT NULL
            )
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS feedback_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                doc_id TEXT NOT NULL,
                delegation_id TEXT,
                outcome TEXT NOT NULL,
                adjustment REAL NOT NULL,
                timestamp TEXT NOT NULL
            )
        """)
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_fb_doc ON feedback_events(doc_id)")
        self.conn.commit()

    def record_retrieval(self, doc_id: str, doc_type: str, delegation_id: Optional[str] = None):
        """Record that a document was retrieved for a decision."""
        cursor = self.conn.cursor()
        ts = datetime.utcnow().isoformat()
        cursor.execute(
            """INSERT INTO document_scores (doc_id, doc_type, times_retrieved, last_updated)
               VALUES (?, ?, 1, ?)
               ON CONFLICT(doc_id) DO UPDATE SET
                 times_retrieved = times_retrieved + 1,
                 last_updated = ?""",
            (doc_id, doc_type, ts, ts),
        )
        self.conn.commit()

    def record_feedback(
        self,
        doc_id: str,
        success: bool,
        delegation_id: Optional[str] = None,
        boost: Optional[float] = None,
        penalty: Optional[float] = None,
    ):
        """Record whether using this document led to success or failure."""
        adj = (boost or self.DEFAULT_BOOST) if success else -(penalty or self.DEFAULT_PENALTY)
        outcome = "helpful" if success else "unhelpful"
        ts = datetime.utcnow().isoformat()

        cursor = self.conn.cursor()
        # Update running score
        helpful_incr = 1 if success else 0
        unhelpful_incr = 0 if success else 1
        cursor.execute(
            """UPDATE document_scores
               SET adjustment = MIN(0.5, MAX(-0.5, adjustment + ?)),
                   times_helpful = times_helpful + ?,
                   times_unhelpful = times_unhelpful + ?,
                   last_updated = ?
               WHERE doc_id = ?""",
            (adj, helpful_incr, unhelpful_incr, ts, doc_id),
        )
        # Log event
        cursor.execute(
            """INSERT INTO feedback_events (doc_id, delegation_id, outcome, adjustment, timestamp)
               VALUES (?, ?, ?, ?, ?)""",
            (doc_id, delegation_id, outcome, adj, ts),
        )
        self.conn.commit()

    def get_effective_score(self, doc_id: str) -> float:
        """Get the adjusted relevance score for a document."""
        cursor = self.conn.cursor()
        cursor.execute(
            "SELECT base_score, adjustment FROM document_scores WHERE doc_id = ?",
            (doc_id,),
        )
        row = cursor.fetchone()
        if row is None:
            return 1.0
        return row["base_score"] + row["adjustment"]

    def rerank_results(
        self, search_results: List[Dict[str, Any]], doc_id_key: str = "doc_id"
    ) -> List[Dict[str, Any]]:
        """
        Re-rank search results using feedback scores.

        Each result's similarity is multiplied by its feedback-adjusted score.
        """
        reranked = []
        for result in search_results:
            doc_id = result.get(doc_id_key, "")
            feedback_score = self.get_effective_score(doc_id)
            original_sim = result.get("similarity", 1.0)
            adjusted_sim = original_sim * feedback_score
            reranked.append({**result, "adjusted_similarity": adjusted_sim})

        reranked.sort(key=lambda r: r["adjusted_similarity"], reverse=True)
        return reranked

    def get_document_stats(self, doc_id: str) -> Optional[Dict[str, Any]]:
        """Get feedback stats for a document."""
        cursor = self.conn.cursor()
        cursor.execute("SELECT * FROM document_scores WHERE doc_id = ?", (doc_id,))
        row = cursor.fetchone()
        return dict(row) if row else None

    def get_top_documents(self, limit: int = 20) -> List[Dict[str, Any]]:
        """Get the highest-rated documents by feedback."""
        cursor = self.conn.cursor()
        cursor.execute(
            """SELECT *, (base_score + adjustment) as effective_score
               FROM document_scores
               ORDER BY effective_score DESC LIMIT ?""",
            (limit,),
        )
        return [dict(r) for r in cursor.fetchall()]

    def close(self):
        if self.conn:
            self.conn.close()
