"""Tests for PatternAnalyzer.sync_delegation_outcomes()."""

import json
import sqlite3
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from src.data_store.pattern_analyzer import PatternAnalyzer


# ---------------------------------------------------------------------------
# Minimal store stub
# ---------------------------------------------------------------------------

class _Store:
    def __init__(self, tmp_path: Path):
        self.patterns_dir = tmp_path / "patterns"
        self.patterns_dir.mkdir(parents=True, exist_ok=True)

    def search_artifacts(self, artifact_type=None):
        return []

    def get_artifact(self, artifact_id):
        return {}


def _make_outcomes_db(db_path: Path, rows):
    """Create a minimal outcomes.db with supplied rows."""
    conn = sqlite3.connect(str(db_path))
    conn.execute("""
        CREATE TABLE delegation_outcomes (
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
            outcome_recorded_at TEXT
        )
    """)
    conn.executemany(
        "INSERT INTO delegation_outcomes "
        "(delegation_id, from_agent, to_agent, task_type, predicted_confidence, actual_success, duration_ms, timestamp) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        rows,
    )
    conn.commit()
    conn.close()


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

@pytest.mark.unit
def test_sync_writes_delegation_stats_to_performance_json(tmp_path):
    db_path = tmp_path / ".agenticqa" / "outcomes.db"
    db_path.parent.mkdir(parents=True)

    _make_outcomes_db(db_path, [
        ("d1", "qa_agent",    "sre_agent",    "lint",     0.8, 1, 120.0, "2026-02-20T10:00:00"),
        ("d2", "qa_agent",    "sre_agent",    "lint",     0.7, 1, 150.0, "2026-02-21T10:00:00"),
        ("d3", "sdet_agent",  "qa_agent",     "coverage", 0.6, 0, 200.0, "2026-02-21T11:00:00"),
    ])

    store = _Store(tmp_path)
    pa = PatternAnalyzer(store)

    with patch.object(Path, "home", return_value=tmp_path):
        result = pa.sync_delegation_outcomes()

    assert result["synced_pairs"] == 2

    perf_file = store.patterns_dir / "performance.json"
    assert perf_file.exists()
    data = json.loads(perf_file.read_text())

    assert "delegation_stats" in data
    assert "delegation_synced_at" in data
    assert len(data["delegation_stats"]) == 2

    # Verify the qa→sre pair has correct stats
    qa_sre = next(
        r for r in data["delegation_stats"]
        if r["from_agent"] == "qa_agent" and r["to_agent"] == "sre_agent"
    )
    assert qa_sre["total"] == 2
    assert qa_sre["success_rate"] == pytest.approx(1.0)


@pytest.mark.unit
def test_sync_merges_with_existing_performance_json(tmp_path):
    db_path = tmp_path / ".agenticqa" / "outcomes.db"
    db_path.parent.mkdir(parents=True)

    _make_outcomes_db(db_path, [
        ("d1", "qa_agent", "sre_agent", "lint", 0.8, 1, 100.0, "2026-02-20T10:00:00"),
    ])

    store = _Store(tmp_path)
    pa = PatternAnalyzer(store)

    # Pre-populate performance.json
    perf_file = store.patterns_dir / "performance.json"
    perf_file.write_text(json.dumps({
        "analyzed_at": "2026-02-20T00:00:00+00:00",
        "total_executions": 42,
        "avg_latency_ms": 350.0,
    }))

    with patch.object(Path, "home", return_value=tmp_path):
        pa.sync_delegation_outcomes()

    data = json.loads(perf_file.read_text())
    # Existing keys must be preserved
    assert data["total_executions"] == 42
    assert data["avg_latency_ms"] == 350.0
    # New keys added
    assert "delegation_stats" in data


@pytest.mark.unit
def test_sync_returns_zero_when_no_db(tmp_path):
    store = _Store(tmp_path)
    pa = PatternAnalyzer(store)

    with patch.object(Path, "home", return_value=tmp_path):
        result = pa.sync_delegation_outcomes()

    assert result["synced_pairs"] == 0
    assert "skipped" in result


@pytest.mark.unit
def test_sync_returns_zero_when_no_completed_outcomes(tmp_path):
    db_path = tmp_path / ".agenticqa" / "outcomes.db"
    db_path.parent.mkdir(parents=True)

    # All rows have actual_success = NULL (in-flight delegations)
    conn = sqlite3.connect(str(db_path))
    conn.execute("""
        CREATE TABLE delegation_outcomes (
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
            outcome_recorded_at TEXT
        )
    """)
    conn.execute(
        "INSERT INTO delegation_outcomes "
        "(delegation_id, from_agent, to_agent, task_type, predicted_confidence, actual_success, timestamp) "
        "VALUES ('d1', 'qa', 'sre', 'lint', 0.8, NULL, '2026-02-20T10:00:00')"
    )
    conn.commit()
    conn.close()

    store = _Store(tmp_path)
    pa = PatternAnalyzer(store)

    with patch.object(Path, "home", return_value=tmp_path):
        result = pa.sync_delegation_outcomes()

    assert result["synced_pairs"] == 0


@pytest.mark.unit
def test_sync_handles_corrupt_performance_json(tmp_path):
    db_path = tmp_path / ".agenticqa" / "outcomes.db"
    db_path.parent.mkdir(parents=True)

    _make_outcomes_db(db_path, [
        ("d1", "qa_agent", "sre_agent", "lint", 0.8, 1, 100.0, "2026-02-20T10:00:00"),
    ])

    store = _Store(tmp_path)
    pa = PatternAnalyzer(store)

    # Write invalid JSON to performance.json
    (store.patterns_dir / "performance.json").write_text("{invalid}")

    with patch.object(Path, "home", return_value=tmp_path):
        result = pa.sync_delegation_outcomes()

    # Should still succeed — bad JSON is silently replaced
    assert result["synced_pairs"] == 1
    data = json.loads((store.patterns_dir / "performance.json").read_text())
    assert "delegation_stats" in data
