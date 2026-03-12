"""
Temporal violation graphs in Neo4j.

Stores timestamped :ViolationSnapshot nodes after each agent run so the
dashboard can render time-series charts of violation trends, fix rates, and
rule frequency without reading every artifact from the SQLite store.

Schema
------
(:ViolationSnapshot {
    run_id, repo_id, agent, recorded_at,    -- identity / time
    total_errors, fix_rate, fixes_applied,  -- summary metrics
})
-[:HAS_RULE {count}]->
(:ViolationRule {name})

Graceful degradation: every public method returns an empty result / False when
Neo4j is unreachable.  Callers must never crash because of this module.
"""

from __future__ import annotations

import logging
import os
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

try:
    from neo4j import GraphDatabase
    from neo4j.exceptions import AuthError, ServiceUnavailable
    _NEO4J_OK = True
except ImportError:
    _NEO4J_OK = False

logger = logging.getLogger(__name__)


class TemporalViolationStore:
    """Records and queries timestamped violation snapshots in Neo4j."""

    def __init__(
        self,
        uri: Optional[str] = None,
        user: Optional[str] = None,
        password: Optional[str] = None,
        database: str = "neo4j",
    ):
        self._uri = uri or os.getenv("NEO4J_URI", "bolt://localhost:7687")
        self._user = user or os.getenv("NEO4J_USER", "neo4j")
        _pw = password or os.getenv("NEO4J_PASSWORD")
        if not _pw:
            logger.warning(
                "NEO4J_PASSWORD is not set. Using insecure default — "
                "set NEO4J_PASSWORD in production environments."
            )
            _pw = "agenticqa123"
        self._password = _pw
        self._database = database
        self._driver = None

    # ──────────────────────────────────────────────────────────────────────
    # Connection helpers
    # ──────────────────────────────────────────────────────────────────────

    def _connect(self) -> bool:
        if not _NEO4J_OK:
            return False
        try:
            self._driver = GraphDatabase.driver(
                self._uri, auth=(self._user, self._password)
            )
            with self._driver.session(database=self._database) as s:
                s.run("RETURN 1")
            return True
        except Exception as exc:
            logger.debug("TemporalViolationStore: Neo4j unavailable — %s", exc)
            self._driver = None
            return False

    @contextmanager
    def _session(self):
        if self._driver is None:
            connected = self._connect()
            if not connected:
                yield None
                return
        session = self._driver.session(database=self._database)
        try:
            yield session
        finally:
            session.close()

    def _ensure_schema(self, session) -> None:
        """Idempotent constraint / index creation."""
        try:
            session.run(
                "CREATE CONSTRAINT snapshot_run IF NOT EXISTS "
                "FOR (s:ViolationSnapshot) REQUIRE s.run_id IS UNIQUE"
            )
            session.run(
                "CREATE CONSTRAINT rule_name IF NOT EXISTS "
                "FOR (r:ViolationRule) REQUIRE r.name IS UNIQUE"
            )
        except Exception:
            pass  # older Neo4j — constraints may already exist under a different syntax

    # ──────────────────────────────────────────────────────────────────────
    # Write
    # ──────────────────────────────────────────────────────────────────────

    def record_run(
        self,
        *,
        run_id: str,
        repo_id: str,
        agent: str,
        violations_by_rule: Dict[str, int],
        fix_rate: float = 0.0,
        fixes_applied: int = 0,
        total_errors: int = 0,
        recorded_at: Optional[str] = None,
    ) -> bool:
        """
        Persist a :ViolationSnapshot node and its :HAS_RULE edges.

        Returns True on success, False on any error (including Neo4j unavailable).
        """
        ts = recorded_at or datetime.now(timezone.utc).isoformat()

        with self._session() as session:
            if session is None:
                return False
            try:
                self._ensure_schema(session)
                # Upsert snapshot
                session.run(
                    """
                    MERGE (s:ViolationSnapshot {run_id: $run_id})
                    SET s.repo_id      = $repo_id,
                        s.agent        = $agent,
                        s.recorded_at  = datetime($recorded_at),
                        s.total_errors = $total_errors,
                        s.fix_rate     = $fix_rate,
                        s.fixes_applied= $fixes_applied
                    """,
                    run_id=run_id,
                    repo_id=repo_id,
                    agent=agent,
                    recorded_at=ts,
                    total_errors=total_errors,
                    fix_rate=round(fix_rate, 4),
                    fixes_applied=fixes_applied,
                )
                # Upsert rule nodes + edges
                for rule, count in violations_by_rule.items():
                    session.run(
                        """
                        MERGE (r:ViolationRule {name: $rule})
                        WITH r
                        MATCH (s:ViolationSnapshot {run_id: $run_id})
                        MERGE (s)-[e:HAS_RULE]->(r)
                        SET e.count = $count
                        """,
                        rule=rule,
                        run_id=run_id,
                        count=count,
                    )
                return True
            except Exception as exc:
                logger.debug("record_run failed: %s", exc)
                return False

    # ──────────────────────────────────────────────────────────────────────
    # Read
    # ──────────────────────────────────────────────────────────────────────

    def get_violation_trend(
        self,
        repo_id: str,
        days: int = 30,
        granularity: str = "day",
    ) -> List[Dict[str, Any]]:
        """
        Return daily/weekly total violation counts for a repo.

        Each point: {"period": str, "total_errors": int, "avg_fix_rate": float, "runs": int}
        """
        trunc = granularity if granularity in ("hour", "day", "week") else "day"
        with self._session() as session:
            if session is None:
                return []
            try:
                result = session.run(
                    f"""
                    MATCH (s:ViolationSnapshot)
                    WHERE s.repo_id = $repo_id
                      AND s.recorded_at > datetime() - duration({{days: $days}})
                    WITH date.truncate('{trunc}', s.recorded_at) AS period,
                         sum(s.total_errors)  AS total_errors,
                         avg(s.fix_rate)       AS avg_fix_rate,
                         count(s)              AS runs
                    RETURN toString(period) AS period,
                           total_errors, avg_fix_rate, runs
                    ORDER BY period
                    """,
                    repo_id=repo_id,
                    days=days,
                )
                return [dict(r) for r in result]
            except Exception as exc:
                logger.debug("get_violation_trend failed: %s", exc)
                return []

    def get_fix_rate_trend(
        self,
        repo_id: str,
        days: int = 30,
    ) -> List[Dict[str, Any]]:
        """
        Return per-run fix rate for a repo, ordered by time.

        Each point: {"run_id": str, "recorded_at": str, "fix_rate": float, "total_errors": int}
        """
        with self._session() as session:
            if session is None:
                return []
            try:
                result = session.run(
                    """
                    MATCH (s:ViolationSnapshot)
                    WHERE s.repo_id = $repo_id
                      AND s.recorded_at > datetime() - duration({days: $days})
                    RETURN s.run_id        AS run_id,
                           toString(s.recorded_at) AS recorded_at,
                           s.fix_rate      AS fix_rate,
                           s.total_errors  AS total_errors,
                           s.agent         AS agent
                    ORDER BY s.recorded_at
                    """,
                    repo_id=repo_id,
                    days=days,
                )
                return [dict(r) for r in result]
            except Exception as exc:
                logger.debug("get_fix_rate_trend failed: %s", exc)
                return []

    def get_top_rules_over_time(
        self,
        repo_id: str,
        days: int = 30,
        top_n: int = 5,
    ) -> List[Dict[str, Any]]:
        """
        Return the top-N violation rules by total count over the time window.

        Each item: {"rule": str, "total_count": int, "runs_affected": int}
        """
        with self._session() as session:
            if session is None:
                return []
            try:
                result = session.run(
                    """
                    MATCH (s:ViolationSnapshot)-[e:HAS_RULE]->(r:ViolationRule)
                    WHERE s.repo_id = $repo_id
                      AND s.recorded_at > datetime() - duration({days: $days})
                    WITH r.name          AS rule,
                         sum(e.count)    AS total_count,
                         count(s)        AS runs_affected
                    RETURN rule, total_count, runs_affected
                    ORDER BY total_count DESC
                    LIMIT $top_n
                    """,
                    repo_id=repo_id,
                    days=days,
                    top_n=top_n,
                )
                return [dict(r) for r in result]
            except Exception as exc:
                logger.debug("get_top_rules_over_time failed: %s", exc)
                return []

    def get_agent_comparison(
        self,
        repo_id: str,
        days: int = 30,
    ) -> List[Dict[str, Any]]:
        """
        Return per-agent violation and fix rate summary over the window.

        Each item: {"agent": str, "runs": int, "avg_fix_rate": float, "total_errors": int}
        """
        with self._session() as session:
            if session is None:
                return []
            try:
                result = session.run(
                    """
                    MATCH (s:ViolationSnapshot)
                    WHERE s.repo_id = $repo_id
                      AND s.recorded_at > datetime() - duration({days: $days})
                    WITH s.agent         AS agent,
                         count(s)        AS runs,
                         avg(s.fix_rate) AS avg_fix_rate,
                         sum(s.total_errors) AS total_errors
                    RETURN agent, runs, avg_fix_rate, total_errors
                    ORDER BY total_errors DESC
                    """,
                    repo_id=repo_id,
                    days=days,
                )
                return [dict(r) for r in result]
            except Exception as exc:
                logger.debug("get_agent_comparison failed: %s", exc)
                return []
