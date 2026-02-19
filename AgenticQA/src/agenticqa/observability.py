"""Lightweight observability event store for agent actions."""

from __future__ import annotations

import json
import hashlib
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
                span_id TEXT,
                parent_span_id TEXT,
                agent TEXT NOT NULL,
                action TEXT NOT NULL,
                event_type TEXT,
                step_key TEXT,
                attempt INTEGER,
                status TEXT NOT NULL,
                started_at TEXT,
                ended_at TEXT,
                latency_ms REAL,
                input_hash TEXT,
                output_hash TEXT,
                decision_json TEXT,
                error TEXT,
                metadata_json TEXT,
                created_at TEXT NOT NULL
            )
            """
        )
        self._ensure_columns(
            [
                ("span_id", "TEXT"),
                ("parent_span_id", "TEXT"),
                ("event_type", "TEXT"),
                ("step_key", "TEXT"),
                ("attempt", "INTEGER"),
                ("input_hash", "TEXT"),
                ("output_hash", "TEXT"),
                ("decision_json", "TEXT"),
            ]
        )
        c.execute("CREATE INDEX IF NOT EXISTS idx_obs_trace ON agent_action_events(trace_id)")
        c.execute("CREATE INDEX IF NOT EXISTS idx_obs_request ON agent_action_events(request_id)")
        c.execute("CREATE INDEX IF NOT EXISTS idx_obs_agent_action ON agent_action_events(agent, action)")
        c.execute("CREATE INDEX IF NOT EXISTS idx_obs_span ON agent_action_events(span_id)")
        c.execute("CREATE INDEX IF NOT EXISTS idx_obs_parent_span ON agent_action_events(parent_span_id)")
        c.execute("CREATE INDEX IF NOT EXISTS idx_obs_event_type ON agent_action_events(event_type)")
        c.execute("CREATE INDEX IF NOT EXISTS idx_obs_created ON agent_action_events(created_at)")
        c.execute(
            """
            CREATE TABLE IF NOT EXISTS agent_complexity_metrics (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                trace_id TEXT,
                agent TEXT NOT NULL,
                action TEXT NOT NULL,
                rag_docs_retrieved INTEGER DEFAULT 0,
                avg_similarity_score REAL DEFAULT 0.0,
                patterns_considered INTEGER DEFAULT 0,
                strategy TEXT,
                llm_prompt_tokens INTEGER DEFAULT 0,
                llm_completion_tokens INTEGER DEFAULT 0,
                timestamp TEXT NOT NULL
            )
            """
        )
        c.execute("CREATE INDEX IF NOT EXISTS idx_complexity_agent ON agent_complexity_metrics(agent)")
        c.execute("CREATE INDEX IF NOT EXISTS idx_complexity_ts ON agent_complexity_metrics(timestamp)")
        self.conn.commit()

    def _ensure_columns(self, columns: List[tuple[str, str]]) -> None:
        c = self.conn.cursor()
        c.execute("PRAGMA table_info(agent_action_events)")
        existing = {str(r[1]) for r in c.fetchall()}
        for name, ddl_type in columns:
            if name not in existing:
                c.execute(f"ALTER TABLE agent_action_events ADD COLUMN {name} {ddl_type}")
        self.conn.commit()

    def log_event(
        self,
        trace_id: str,
        request_id: Optional[str],
        agent: str,
        action: str,
        status: str,
        span_id: Optional[str] = None,
        parent_span_id: Optional[str] = None,
        event_type: Optional[str] = None,
        step_key: Optional[str] = None,
        attempt: Optional[int] = None,
        started_at: Optional[str] = None,
        ended_at: Optional[str] = None,
        latency_ms: Optional[float] = None,
        input_hash: Optional[str] = None,
        output_hash: Optional[str] = None,
        decision: Optional[Dict[str, Any]] = None,
        error: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> int:
        now = datetime.now(UTC).isoformat()
        normalized_status = (status or "UNKNOWN").upper()
        c = self.conn.cursor()
        c.execute(
            """
            INSERT INTO agent_action_events (
                trace_id, request_id, span_id, parent_span_id, agent, action,
                event_type, step_key, attempt, status,
                started_at, ended_at, latency_ms, input_hash, output_hash,
                decision_json, error, metadata_json, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                trace_id,
                request_id,
                span_id,
                parent_span_id,
                agent,
                action,
                event_type,
                step_key,
                attempt,
                normalized_status,
                started_at,
                ended_at,
                latency_ms,
                input_hash,
                output_hash,
                json.dumps(decision or {}),
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
        status: Optional[str] = None,
        event_type: Optional[str] = None,
        newest_first: bool = True,
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
        if status:
            where.append("status = ?")
            params.append(status.upper())
        if event_type:
            where.append("event_type = ?")
            params.append(event_type)

        clause = f"WHERE {' AND '.join(where)}" if where else ""
        order_clause = "DESC" if newest_first else "ASC"
        c = self.conn.cursor()
        c.execute(
            f"""
            SELECT *
            FROM agent_action_events
            {clause}
            ORDER BY id {order_clause}
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
                SUM(CASE WHEN status = 'STARTED' THEN 1 ELSE 0 END) AS started_count,
                SUM(CASE WHEN status IN ('COMPLETED','FAILED','CANCELLED','SKIPPED') THEN 1 ELSE 0 END) AS terminal_count,
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
            started_count = int(row.get("started_count") or 0)
            terminal_count = int(row.get("terminal_count") or 0)
            row["completeness_ratio"] = (
                round(terminal_count / started_count, 3) if started_count > 0 else 1.0
            )
            row.pop("last_event_id", None)
        return rows

    def get_trace(self, trace_id: str, limit: int = 500) -> Dict[str, Any]:
        events = self.list_events(limit=limit, trace_id=trace_id, newest_first=False)
        analysis = self.analyze_trace(trace_id=trace_id, events=events)
        return {
            "trace_id": trace_id,
            "event_count": len(events),
            "events": events,
            "analysis": analysis,
        }

    def analyze_trace(
        self,
        trace_id: str,
        events: Optional[List[Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        records = events or self.list_events(limit=1000, trace_id=trace_id, newest_first=False)

        spans: Dict[str, Dict[str, Any]] = {}
        roots: List[str] = []
        by_agent_action: Dict[str, Dict[str, Any]] = {}
        event_type_counts: Dict[str, int] = {}
        started_spans: set[str] = set()
        terminal_spans: set[str] = set()

        for e in records:
            span_id = e.get("span_id")
            parent_span_id = e.get("parent_span_id")
            status = str(e.get("status") or "").upper()
            event_type = str(e.get("event_type") or "unknown")

            event_type_counts[event_type] = event_type_counts.get(event_type, 0) + 1

            key = f"{e.get('agent')}::{e.get('action')}"
            entry = by_agent_action.setdefault(
                key,
                {
                    "agent": e.get("agent"),
                    "action": e.get("action"),
                    "count": 0,
                    "failures": 0,
                    "avg_latency_ms": 0.0,
                },
            )
            entry["count"] += 1
            if status == "FAILED":
                entry["failures"] += 1

            latency = e.get("latency_ms")
            if isinstance(latency, (int, float)):
                prior = float(entry["avg_latency_ms"]) * (entry["count"] - 1)
                entry["avg_latency_ms"] = round((prior + float(latency)) / entry["count"], 3)

            if span_id:
                node = spans.setdefault(
                    span_id,
                    {
                        "span_id": span_id,
                        "parent_span_id": parent_span_id,
                        "agent": e.get("agent"),
                        "action": e.get("action"),
                        "event_type": e.get("event_type"),
                        "step_key": e.get("step_key"),
                        "statuses": [],
                        "started_at": e.get("started_at") or e.get("created_at"),
                        "ended_at": e.get("ended_at") or e.get("created_at"),
                        "latency_ms": e.get("latency_ms"),
                        "children": [],
                    },
                )
                node["statuses"].append(status)
                node["ended_at"] = e.get("ended_at") or e.get("created_at")
                if isinstance(e.get("latency_ms"), (int, float)):
                    node["latency_ms"] = e.get("latency_ms")

                if status == "STARTED":
                    started_spans.add(span_id)
                if status in {"COMPLETED", "FAILED", "CANCELLED", "SKIPPED"}:
                    terminal_spans.add(span_id)

        for span_id, node in spans.items():
            parent = node.get("parent_span_id")
            if parent and parent in spans:
                spans[parent]["children"].append(span_id)
            else:
                roots.append(span_id)

        started_count = len(started_spans)
        terminal_count = len(terminal_spans)
        completeness_ratio = round((terminal_count / started_count), 3) if started_count > 0 else 1.0

        orphan_span_count = len([s for s in spans.values() if s.get("parent_span_id") and s.get("parent_span_id") not in spans])

        critical_path_ms = 0.0
        for root in roots:
            critical_path_ms = max(critical_path_ms, self._span_path_latency(spans=spans, span_id=root))

        return {
            "trace_id": trace_id,
            "span_count": len(spans),
            "root_spans": roots,
            "started_span_count": started_count,
            "terminal_span_count": terminal_count,
            "completeness_ratio": completeness_ratio,
            "orphan_span_count": orphan_span_count,
            "critical_path_ms": round(critical_path_ms, 3),
            "by_agent_action": sorted(by_agent_action.values(), key=lambda r: (r["failures"], r["count"]), reverse=True),
            "event_type_counts": event_type_counts,
            "spans": list(spans.values()),
        }

    def get_quality_summary(
        self,
        limit: int = 100,
        min_completeness: float = 0.95,
        min_decision_quality: float = 0.60,
    ) -> Dict[str, Any]:
        traces = self.list_traces(limit=limit)
        if not traces:
            return {
                "trace_count": 0,
                "avg_completeness_ratio": 1.0,
                "min_completeness_ratio": 1.0,
                "below_threshold_count": 0,
                "min_completeness_threshold": min_completeness,
                "avg_decision_quality_score": 1.0,
                "min_decision_quality_score": 1.0,
                "decision_quality_below_threshold_count": 0,
                "min_decision_quality_threshold": min_decision_quality,
                "status": "no_traces",
            }

        ratios = [float(t.get("completeness_ratio") or 0.0) for t in traces]
        below = [r for r in ratios if r < min_completeness]

        decision_scores: List[float] = []
        decision_below = 0
        for t in traces:
            trace_id = str(t.get("trace_id") or "")
            if not trace_id:
                continue
            trace_events = self.list_events(limit=1000, trace_id=trace_id, newest_first=False)
            score = self._compute_decision_quality_score(trace_events)
            decision_scores.append(score)
            if score < min_decision_quality:
                decision_below += 1

        avg_decision_score = round(sum(decision_scores) / len(decision_scores), 3) if decision_scores else 1.0
        min_decision_score = round(min(decision_scores), 3) if decision_scores else 1.0

        return {
            "trace_count": len(traces),
            "avg_completeness_ratio": round(sum(ratios) / len(ratios), 3),
            "min_completeness_ratio": round(min(ratios), 3),
            "below_threshold_count": len(below),
            "min_completeness_threshold": min_completeness,
            "avg_decision_quality_score": avg_decision_score,
            "min_decision_quality_score": min_decision_score,
            "decision_quality_below_threshold_count": decision_below,
            "min_decision_quality_threshold": min_decision_quality,
            "status": "pass" if (not below and decision_below == 0) else "warn",
        }

    def get_failure_insights(self, limit: int = 300) -> Dict[str, Any]:
        events = self.list_events(limit=limit)
        failed = [e for e in events if str(e.get("status") or "").upper() == "FAILED"]

        root_causes: Dict[str, int] = {}
        by_agent_action: Dict[str, int] = {}
        examples: List[Dict[str, Any]] = []

        for e in failed:
            rc = self._classify_root_cause(error=e.get("error"), metadata=e.get("metadata") or {})
            root_causes[rc] = root_causes.get(rc, 0) + 1

            key = f"{e.get('agent')}::{e.get('action')}"
            by_agent_action[key] = by_agent_action.get(key, 0) + 1

            if len(examples) < 20:
                examples.append(
                    {
                        "trace_id": e.get("trace_id"),
                        "request_id": e.get("request_id"),
                        "agent": e.get("agent"),
                        "action": e.get("action"),
                        "root_cause": rc,
                        "error": (e.get("error") or "")[:220],
                        "created_at": e.get("created_at"),
                    }
                )

        ranked_causes = sorted(root_causes.items(), key=lambda it: it[1], reverse=True)
        ranked_pairs = sorted(by_agent_action.items(), key=lambda it: it[1], reverse=True)
        return {
            "window_events": len(events),
            "failed_events": len(failed),
            "failure_rate": round((len(failed) / len(events)), 3) if events else 0.0,
            "root_cause_counts": [{"root_cause": k, "count": v} for k, v in ranked_causes],
            "top_failure_agent_actions": [
                {"agent_action": k, "count": v} for k, v in ranked_pairs[:20]
            ],
            "examples": examples,
        }

    def get_policy_impact_summary(self, limit: int = 500) -> Dict[str, Any]:
        events = self.list_events(limit=limit)

        policy_blocked = 0
        quality_gate_blocked = 0
        policy_passed = 0

        for e in events:
            err = str(e.get("error") or "")
            md = e.get("metadata") or {}
            status = str(e.get("status") or "").upper()

            if "policy_gate_failed" in err:
                policy_blocked += 1
            if "quality_gate_failed" in err or (status == "FAILED" and md.get("quality_gate_passed") is False):
                quality_gate_blocked += 1
            if e.get("action") == "run_request" and status == "COMPLETED":
                policy_passed += 1

        total = max(policy_passed + policy_blocked, 1)
        return {
            "window_events": len(events),
            "policy_passed_runs": policy_passed,
            "policy_blocked_runs": policy_blocked,
            "quality_gate_blocked_runs": quality_gate_blocked,
            "policy_block_rate": round(policy_blocked / total, 3),
        }

    def get_counterfactual_recommendations(self, trace_id: str, limit: int = 100) -> Dict[str, Any]:
        events = self.list_events(limit=limit, trace_id=trace_id, newest_first=False)
        recs: List[Dict[str, Any]] = []

        for e in events:
            status = str(e.get("status") or "").upper()
            if status not in {"FAILED", "RETRY"}:
                continue

            reason = str(e.get("error") or "")
            action = str(e.get("action") or "")
            event_type = str(e.get("event_type") or "")
            root_cause = self._classify_root_cause(reason, e.get("metadata") or {})

            alternatives: List[str] = []
            if "policy_gate_failed" in reason:
                alternatives.append("Provide required policy metadata (`approved_by`, `policy_ticket`) before non-dry run")
            if action == "sdet_test_loop":
                alternatives.append("Increase `max_sdet_iterations` by 1 for flaky test synthesis paths")
                alternatives.append("Enable SDET auto-fix and include syntax-safe fallback templates")
            if root_cause == "DEPENDENCY_UNAVAILABLE":
                alternatives.append("Preflight dependency readiness in CI before workflow execution")
            if root_cause == "PYTEST_FAILURE":
                alternatives.append("Persist failing test signature and generate targeted remediation tests")
            if root_cause == "IMPORT_OR_MODULE_ERROR":
                alternatives.append("Add package export compatibility check in validation stage")
            if not alternatives:
                alternatives.append("Capture additional decision metadata to improve replayable remediation")

            recs.append(
                {
                    "event_id": e.get("id"),
                    "agent": e.get("agent"),
                    "action": action,
                    "event_type": event_type,
                    "status": status,
                    "root_cause": root_cause,
                    "error": reason[:240],
                    "counterfactuals": alternatives,
                }
            )

        return {
            "trace_id": trace_id,
            "event_count": len(events),
            "recommendations": recs,
        }

    def get_global_insights(self, limit: int = 500) -> Dict[str, Any]:
        return {
            "quality": self.get_quality_summary(limit=limit),
            "failures": self.get_failure_insights(limit=limit),
            "policy_impact": self.get_policy_impact_summary(limit=limit),
        }

    def hash_payload(self, payload: Optional[Any]) -> Optional[str]:
        if payload is None:
            return None
        try:
            data = json.dumps(payload, sort_keys=True, default=str)
            return hashlib.sha256(data.encode("utf-8")).hexdigest()
        except Exception:
            return None

    def _span_path_latency(self, spans: Dict[str, Dict[str, Any]], span_id: str) -> float:
        node = spans.get(span_id) or {}
        here = float(node.get("latency_ms") or 0.0)
        children = node.get("children") or []
        if not children:
            return here
        return here + max(self._span_path_latency(spans, c) for c in children)

    def _classify_root_cause(self, error: Optional[str], metadata: Dict[str, Any]) -> str:
        text = (error or "").lower()
        if "policy_gate_failed" in text:
            return "POLICY_GATE"
        if "quality_gate_failed" in text:
            return "QUALITY_GATE"
        if "repo_not_found" in text:
            return "REPO_NOT_FOUND"
        if "syntaxerror" in text:
            return "SYNTAX_ERROR"
        if "importerror" in text or "modulenotfounderror" in text:
            return "IMPORT_OR_MODULE_ERROR"
        if "pytest" in text or "assert" in text or "sdet_loop_failed" in text:
            return "PYTEST_FAILURE"
        if "connection refused" in text or "timed out" in text or "weaviate" in text or "neo4j" in text:
            return "DEPENDENCY_UNAVAILABLE"
        if metadata.get("quality_gate_passed") is False:
            return "QUALITY_GATE"
        return "UNKNOWN"

    def _compute_decision_quality_score(self, events: List[Dict[str, Any]]) -> float:
        if not events:
            return 1.0

        terminal = [
            e
            for e in events
            if str(e.get("status") or "").upper() in {"COMPLETED", "FAILED", "CANCELLED", "SKIPPED"}
        ]
        if not terminal:
            return 1.0

        with_decision = [e for e in terminal if bool(e.get("decision"))]
        decision_coverage = len(with_decision) / len(terminal)

        successful_decisions = [e for e in with_decision if str(e.get("status") or "").upper() == "COMPLETED"]
        decision_success = (len(successful_decisions) / len(with_decision)) if with_decision else 1.0

        # Weighted blend: prioritize logging coverage, then decision outcome quality.
        score = (0.7 * decision_coverage) + (0.3 * decision_success)
        return round(score, 3)

    def _row_to_event(self, row: Dict[str, Any]) -> Dict[str, Any]:
        try:
            row["metadata"] = json.loads(row.pop("metadata_json") or "{}")
        except Exception:
            row["metadata"] = {}
            row.pop("metadata_json", None)
        try:
            row["decision"] = json.loads(row.pop("decision_json") or "{}")
        except Exception:
            row["decision"] = {}
            row.pop("decision_json", None)
        return row

    def log_complexity_metric(
        self,
        agent: str,
        action: str,
        *,
        trace_id: Optional[str] = None,
        rag_docs: int = 0,
        avg_sim: float = 0.0,
        patterns: int = 0,
        strategy: Optional[str] = None,
        llm_prompt_tokens: int = 0,
        llm_completion_tokens: int = 0,
    ) -> None:
        """Record one complexity snapshot — works for CBR agents (rag_docs/avg_sim)
        and LLM-based agents (llm_prompt_tokens/llm_completion_tokens)."""
        now = datetime.now(UTC).isoformat()
        c = self.conn.cursor()
        c.execute(
            """
            INSERT INTO agent_complexity_metrics
                (trace_id, agent, action, rag_docs_retrieved, avg_similarity_score,
                 patterns_considered, strategy, llm_prompt_tokens, llm_completion_tokens,
                 timestamp)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (trace_id, agent, action, rag_docs, avg_sim, patterns, strategy,
             llm_prompt_tokens, llm_completion_tokens, now),
        )
        self.conn.commit()

    def get_complexity_trends(
        self, agent: str, window_days: int = 14
    ) -> Dict[str, Any]:
        """Return daily complexity averages and anomaly flag for an agent.

        Anomaly: current 3-day avg_similarity < 14-day baseline * 0.80
        (signals retrieval quality degradation, e.g. from a bad code change).
        """
        from datetime import timedelta

        cutoff = (datetime.now(UTC) - timedelta(days=window_days)).isoformat()
        c = self.conn.cursor()
        rows = c.execute(
            """
            SELECT substr(timestamp, 1, 10)     AS day,
                   AVG(rag_docs_retrieved)       AS avg_rag_docs,
                   AVG(avg_similarity_score)     AS avg_similarity,
                   AVG(patterns_considered)      AS avg_patterns,
                   COUNT(*)                      AS actions,
                   SUM(llm_prompt_tokens)        AS total_prompt_tokens,
                   SUM(llm_completion_tokens)    AS total_completion_tokens
            FROM agent_complexity_metrics
            WHERE agent = ? AND timestamp >= ?
            GROUP BY day
            ORDER BY day ASC
            """,
            (agent, cutoff),
        ).fetchall()

        daily = [
            {
                "date": r[0],
                "avg_rag_docs": round(r[1] or 0.0, 2),
                "avg_similarity": round(r[2] or 0.0, 3),
                "avg_patterns": round(r[3] or 0.0, 2),
                "actions": r[4],
                "llm_prompt_tokens": int(r[5] or 0),
                "llm_completion_tokens": int(r[6] or 0),
            }
            for r in rows
        ]

        total_actions = sum(d["actions"] for d in daily)
        avg_rag_docs = round(sum(d["avg_rag_docs"] for d in daily) / len(daily), 2) if daily else 0.0
        avg_similarity = round(sum(d["avg_similarity"] for d in daily) / len(daily), 3) if daily else 0.0
        total_prompt_tokens = sum(d["llm_prompt_tokens"] for d in daily)
        total_completion_tokens = sum(d["llm_completion_tokens"] for d in daily)

        # Anomaly: compare recent 3-day avg to full-window baseline
        anomaly = False
        anomaly_reason: Optional[str] = None
        if len(daily) >= 4:
            baseline_sim = sum(d["avg_similarity"] for d in daily[:-3]) / max(len(daily) - 3, 1)
            recent_sim = sum(d["avg_similarity"] for d in daily[-3:]) / 3
            if baseline_sim > 0 and recent_sim < baseline_sim * 0.80:
                anomaly = True
                anomaly_reason = (
                    f"similarity_degraded: recent {round(recent_sim, 3)} "
                    f"vs baseline {round(baseline_sim, 3)} "
                    f"({round((1 - recent_sim / baseline_sim) * 100, 1)}% drop)"
                )

        return {
            "agent": agent,
            "window_days": window_days,
            "daily": daily,
            "summary": {
                "total_actions": total_actions,
                "avg_rag_docs": avg_rag_docs,
                "avg_similarity": avg_similarity,
                "total_llm_prompt_tokens": total_prompt_tokens,
                "total_llm_completion_tokens": total_completion_tokens,
            },
            "anomaly": anomaly,
            "anomaly_reason": anomaly_reason,
        }

    def close(self) -> None:
        self.conn.close()
