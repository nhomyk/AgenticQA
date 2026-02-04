"""
Relational Database Store for Structured RAG Data

Complements Weaviate vector store with a relational database for:
- Structured metrics (coverage %, test counts, etc.)
- Exact match queries (run IDs, timestamps)
- Cost savings (relational DBs cheaper than vector DBs)
- Fallback when Weaviate unavailable
"""

import sqlite3
import json
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime
from pathlib import Path
from dataclasses import dataclass
import os


@dataclass
class StructuredMetric:
    """Structured metric from CI/CD pipeline"""

    id: Optional[int]
    run_id: str
    agent_type: str
    metric_type: str  # 'test_result', 'coverage', 'security', 'performance'
    metric_name: str
    metric_value: float
    metadata: Dict[str, Any]
    timestamp: str


class RelationalStore:
    """
    SQLite-based relational store for structured RAG data.

    Provides:
    - Fast exact match queries (O(log n) vs O(n) vector search)
    - Lower cost than vector DB for structured data
    - Fallback when vector DB unavailable
    - Zero configuration (file-based SQLite)
    """

    def __init__(self, db_path: Optional[str] = None):
        """
        Initialize relational store.

        Args:
            db_path: Path to SQLite database file (default: ~/.agenticqa/rag.db)
        """
        if db_path is None:
            # Default to user's home directory
            home = Path.home()
            db_dir = home / ".agenticqa"
            db_dir.mkdir(exist_ok=True)
            db_path = str(db_dir / "rag.db")

        self.db_path = db_path
        self.conn = sqlite3.connect(db_path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row  # Enable column access by name
        self._init_schema()

    def _init_schema(self):
        """Initialize database schema"""
        cursor = self.conn.cursor()

        # Metrics table - structured numerical data
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS metrics (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                run_id TEXT NOT NULL,
                agent_type TEXT NOT NULL,
                metric_type TEXT NOT NULL,
                metric_name TEXT NOT NULL,
                metric_value REAL NOT NULL,
                metadata TEXT,
                timestamp TEXT NOT NULL,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Indexes for common queries
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_run_id ON metrics(run_id)
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_agent_type ON metrics(agent_type)
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_metric_type ON metrics(metric_type)
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_timestamp ON metrics(timestamp DESC)
        """)

        # Execution history table - agent decisions and outcomes
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS executions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                run_id TEXT NOT NULL,
                agent_type TEXT NOT NULL,
                action TEXT NOT NULL,
                outcome TEXT NOT NULL,
                success BOOLEAN NOT NULL,
                duration_ms INTEGER,
                metadata TEXT,
                timestamp TEXT NOT NULL,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)

        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_executions_agent ON executions(agent_type)
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_executions_success ON executions(success)
        """)

        self.conn.commit()

    def store_metric(
        self,
        run_id: str,
        agent_type: str,
        metric_type: str,
        metric_name: str,
        metric_value: float,
        metadata: Optional[Dict] = None,
        timestamp: Optional[str] = None
    ) -> int:
        """
        Store a structured metric.

        Args:
            run_id: CI run identifier
            agent_type: Agent type (qa, compliance, sdet, etc.)
            metric_type: Type of metric (test_result, coverage, etc.)
            metric_name: Name of metric (e.g., 'pass_rate', 'line_coverage')
            metric_value: Numerical value
            metadata: Additional context
            timestamp: ISO timestamp (defaults to now)

        Returns:
            ID of inserted metric
        """
        cursor = self.conn.cursor()

        if timestamp is None:
            timestamp = datetime.utcnow().isoformat()

        metadata_json = json.dumps(metadata or {})

        cursor.execute("""
            INSERT INTO metrics (
                run_id, agent_type, metric_type, metric_name,
                metric_value, metadata, timestamp
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            run_id, agent_type, metric_type, metric_name,
            metric_value, metadata_json, timestamp
        ))

        self.conn.commit()
        return cursor.lastrowid

    def store_execution(
        self,
        run_id: str,
        agent_type: str,
        action: str,
        outcome: str,
        success: bool,
        duration_ms: Optional[int] = None,
        metadata: Optional[Dict] = None,
        timestamp: Optional[str] = None
    ) -> int:
        """Store agent execution result"""
        cursor = self.conn.cursor()

        if timestamp is None:
            timestamp = datetime.utcnow().isoformat()

        metadata_json = json.dumps(metadata or {})

        cursor.execute("""
            INSERT INTO executions (
                run_id, agent_type, action, outcome, success,
                duration_ms, metadata, timestamp
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            run_id, agent_type, action, outcome, success,
            duration_ms, metadata_json, timestamp
        ))

        self.conn.commit()
        return cursor.lastrowid

    def query_metrics(
        self,
        agent_type: Optional[str] = None,
        metric_type: Optional[str] = None,
        metric_name: Optional[str] = None,
        min_value: Optional[float] = None,
        max_value: Optional[float] = None,
        limit: int = 100
    ) -> List[StructuredMetric]:
        """
        Query metrics with filters.

        Returns:
            List of matching metrics
        """
        cursor = self.conn.cursor()

        query = "SELECT * FROM metrics WHERE 1=1"
        params = []

        if agent_type:
            query += " AND agent_type = ?"
            params.append(agent_type)

        if metric_type:
            query += " AND metric_type = ?"
            params.append(metric_type)

        if metric_name:
            query += " AND metric_name = ?"
            params.append(metric_name)

        if min_value is not None:
            query += " AND metric_value >= ?"
            params.append(min_value)

        if max_value is not None:
            query += " AND metric_value <= ?"
            params.append(max_value)

        query += " ORDER BY timestamp DESC LIMIT ?"
        params.append(limit)

        cursor.execute(query, params)
        rows = cursor.fetchall()

        return [
            StructuredMetric(
                id=row['id'],
                run_id=row['run_id'],
                agent_type=row['agent_type'],
                metric_type=row['metric_type'],
                metric_name=row['metric_name'],
                metric_value=row['metric_value'],
                metadata=json.loads(row['metadata']),
                timestamp=row['timestamp']
            )
            for row in rows
        ]

    def get_metric_stats(
        self,
        agent_type: str,
        metric_name: str,
        limit: int = 10
    ) -> Dict[str, Any]:
        """
        Get statistics for a metric.

        Returns:
            Dictionary with avg, min, max, trend
        """
        cursor = self.conn.cursor()

        # Get aggregate stats
        cursor.execute("""
            SELECT
                AVG(metric_value) as avg_value,
                MIN(metric_value) as min_value,
                MAX(metric_value) as max_value,
                COUNT(*) as count
            FROM metrics
            WHERE agent_type = ? AND metric_name = ?
        """, (agent_type, metric_name))

        stats = cursor.fetchone()

        # Get recent trend
        cursor.execute("""
            SELECT metric_value, timestamp
            FROM metrics
            WHERE agent_type = ? AND metric_name = ?
            ORDER BY timestamp DESC
            LIMIT ?
        """, (agent_type, metric_name, limit))

        trend = [
            {'value': row['metric_value'], 'timestamp': row['timestamp']}
            for row in cursor.fetchall()
        ]

        return {
            'avg': stats['avg_value'],
            'min': stats['min_value'],
            'max': stats['max_value'],
            'count': stats['count'],
            'recent_trend': trend
        }

    def get_success_rate(
        self,
        agent_type: str,
        action: Optional[str] = None,
        limit: int = 100
    ) -> Tuple[float, int, int]:
        """
        Get success rate for agent actions.

        Returns:
            Tuple of (success_rate, successes, total)
        """
        cursor = self.conn.cursor()

        query = """
            SELECT
                SUM(CASE WHEN success = 1 THEN 1 ELSE 0 END) as successes,
                COUNT(*) as total
            FROM executions
            WHERE agent_type = ?
        """
        params = [agent_type]

        if action:
            query += " AND action = ?"
            params.append(action)

        query += " ORDER BY timestamp DESC LIMIT ?"
        params.append(limit)

        cursor.execute(query, params)
        row = cursor.fetchone()

        successes = row['successes'] or 0
        total = row['total'] or 0
        rate = (successes / total) if total > 0 else 0.0

        return (rate, successes, total)

    def close(self):
        """Close database connection"""
        if self.conn:
            self.conn.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()


# Production-ready: PostgreSQL adapter
class PostgreSQLStore(RelationalStore):
    """
    PostgreSQL adapter for production deployments.

    Same interface as SQLite store, but uses PostgreSQL for:
    - Multi-user concurrency
    - Larger datasets
    - Better performance at scale
    """

    def __init__(self, connection_string: Optional[str] = None):
        """
        Initialize PostgreSQL store.

        Args:
            connection_string: PostgreSQL connection string
                             (e.g., "postgresql://user:pass@localhost/agenticqa")
        """
        try:
            import psycopg2
            from psycopg2.extras import RealDictCursor

            if connection_string is None:
                connection_string = os.getenv(
                    "AGENTICQA_PG_CONNECTION",
                    "postgresql://localhost/agenticqa"
                )

            self.conn = psycopg2.connect(
                connection_string,
                cursor_factory=RealDictCursor
            )
            self._init_schema_pg()

        except ImportError:
            raise ImportError(
                "psycopg2 not installed. Install with: pip install psycopg2-binary"
            )

    def _init_schema_pg(self):
        """Initialize PostgreSQL schema"""
        cursor = self.conn.cursor()

        # Use BIGSERIAL for auto-increment, JSONB for better JSON performance
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS metrics (
                id BIGSERIAL PRIMARY KEY,
                run_id TEXT NOT NULL,
                agent_type TEXT NOT NULL,
                metric_type TEXT NOT NULL,
                metric_name TEXT NOT NULL,
                metric_value DOUBLE PRECISION NOT NULL,
                metadata JSONB,
                timestamp TIMESTAMP NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Create indexes
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_metrics_run_id ON metrics(run_id)
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_metrics_agent_type ON metrics(agent_type)
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_metrics_timestamp ON metrics(timestamp DESC)
        """)

        # Execution history table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS executions (
                id BIGSERIAL PRIMARY KEY,
                run_id TEXT NOT NULL,
                agent_type TEXT NOT NULL,
                action TEXT NOT NULL,
                outcome TEXT NOT NULL,
                success BOOLEAN NOT NULL,
                duration_ms INTEGER,
                metadata JSONB,
                timestamp TIMESTAMP NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_executions_agent ON executions(agent_type)
        """)

        self.conn.commit()
