"""Tests for agent complexity tracking and decision provenance."""

import sys
import os
from datetime import datetime, timedelta, UTC

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))


def _make_store(tmp_path):
    from agenticqa.observability import ObservabilityStore
    return ObservabilityStore(db_path=str(tmp_path / "obs.db"))


@pytest.mark.unit
class TestComplexityMetrics:

    def test_log_complexity_metric_persists(self, tmp_path):
        store = _make_store(tmp_path)
        store.log_complexity_metric(
            agent="QA_Assistant",
            action="rag_augment",
            trace_id="tr_001",
            rag_docs=5,
            avg_sim=0.82,
            patterns=3,
            strategy="standard",
        )
        c = store.conn.cursor()
        rows = c.execute(
            "SELECT agent, action, rag_docs_retrieved, avg_similarity_score, strategy "
            "FROM agent_complexity_metrics WHERE trace_id = 'tr_001'"
        ).fetchall()
        assert len(rows) == 1
        assert rows[0][0] == "QA_Assistant"
        assert rows[0][2] == 5
        assert abs(rows[0][3] - 0.82) < 0.001
        assert rows[0][4] == "standard"
        store.close()

    def test_get_complexity_trends_returns_daily_and_summary(self, tmp_path):
        store = _make_store(tmp_path)
        for i in range(3):
            store.log_complexity_metric(
                agent="SDET_Agent",
                action="rag_augment",
                rag_docs=4,
                avg_sim=0.75,
                patterns=2,
                strategy="standard",
            )
        result = store.get_complexity_trends(agent="SDET_Agent", window_days=7)
        assert result["agent"] == "SDET_Agent"
        assert isinstance(result["daily"], list)
        assert result["summary"]["total_actions"] == 3
        assert result["summary"]["avg_similarity"] > 0
        assert "anomaly" in result
        store.close()

    def test_anomaly_flagged_when_similarity_drops(self, tmp_path):
        store = _make_store(tmp_path)
        c = store.conn.cursor()
        base_ts = datetime.now(UTC) - timedelta(days=10)
        # 7 days of healthy baseline (sim=0.80)
        for offset in range(7):
            day = (base_ts + timedelta(days=offset)).isoformat()[:10]
            c.execute(
                "INSERT INTO agent_complexity_metrics "
                "(agent, action, rag_docs_retrieved, avg_similarity_score, patterns_considered, strategy, timestamp) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                ("QA_Assistant", "rag_augment", 5, 0.80, 3, "standard", f"{day}T12:00:00+00:00"),
            )
        # 3 recent days with degraded similarity (sim=0.50 — 37.5% drop)
        for offset in range(3):
            day = (base_ts + timedelta(days=7 + offset)).isoformat()[:10]
            c.execute(
                "INSERT INTO agent_complexity_metrics "
                "(agent, action, rag_docs_retrieved, avg_similarity_score, patterns_considered, strategy, timestamp) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                ("QA_Assistant", "rag_augment", 2, 0.50, 1, "conservative", f"{day}T12:00:00+00:00"),
            )
        store.conn.commit()
        result = store.get_complexity_trends(agent="QA_Assistant", window_days=14)
        assert result["anomaly"] is True
        assert result["anomaly_reason"] is not None
        assert "similarity_degraded" in result["anomaly_reason"]
        store.close()

    def test_anomaly_clear_when_similarity_stable(self, tmp_path):
        store = _make_store(tmp_path)
        c = store.conn.cursor()
        base_ts = datetime.now(UTC) - timedelta(days=10)
        for offset in range(10):
            day = (base_ts + timedelta(days=offset)).isoformat()[:10]
            c.execute(
                "INSERT INTO agent_complexity_metrics "
                "(agent, action, rag_docs_retrieved, avg_similarity_score, patterns_considered, strategy, timestamp) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                ("DevOps_Agent", "rag_augment", 4, 0.78, 2, "standard", f"{day}T12:00:00+00:00"),
            )
        store.conn.commit()
        result = store.get_complexity_trends(agent="DevOps_Agent", window_days=14)
        assert result["anomaly"] is False
        assert result["anomaly_reason"] is None
        store.close()
