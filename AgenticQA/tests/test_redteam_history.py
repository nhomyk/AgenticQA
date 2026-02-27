"""Unit tests for RedTeamHistoryStore."""

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from data_store.redteam_history import RedTeamHistoryStore


# ─────────────────────────────────────────────────────────────────────────────
# record / append
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.unit
def test_record_appends_jsonl(tmp_path):
    store = RedTeamHistoryStore(history_path=tmp_path / "h.jsonl")
    store.record(run_id="r1", scanner_strength=0.64, gate_strength=1.0)
    store.record(run_id="r2", scanner_strength=0.72, gate_strength=1.0)

    lines = (tmp_path / "h.jsonl").read_text().strip().splitlines()
    assert len(lines) == 2
    assert json.loads(lines[0])["run_id"] == "r1"
    assert json.loads(lines[1])["scanner_strength"] == 0.72


@pytest.mark.unit
def test_record_required_fields_present(tmp_path):
    store = RedTeamHistoryStore(history_path=tmp_path / "h.jsonl")
    result = store.record(run_id="r1")

    assert "run_id" in result
    assert "recorded_at" in result
    assert "mode" in result
    assert "scanner_strength" in result
    assert "gate_strength" in result
    assert "bypass_attempts" in result
    assert "successful_bypasses" in result
    assert "status" in result


@pytest.mark.unit
def test_record_optional_injection_fields(tmp_path):
    store = RedTeamHistoryStore(history_path=tmp_path / "h.jsonl")
    result = store.record(
        run_id="r1",
        prompt_injection_surface=0.3,
        prompt_injection_findings=2,
    )
    assert result["prompt_injection_surface"] == 0.3
    assert result["prompt_injection_findings"] == 2


@pytest.mark.unit
def test_record_omits_none_injection_fields(tmp_path):
    store = RedTeamHistoryStore(history_path=tmp_path / "h.jsonl")
    result = store.record(run_id="r1")
    assert "prompt_injection_surface" not in result
    assert "prompt_injection_findings" not in result


@pytest.mark.unit
def test_record_rounds_floats(tmp_path):
    store = RedTeamHistoryStore(history_path=tmp_path / "h.jsonl")
    result = store.record(run_id="r1", scanner_strength=0.666666, gate_strength=0.999999)
    assert result["scanner_strength"] == 0.6667
    assert result["gate_strength"] == 1.0


# ─────────────────────────────────────────────────────────────────────────────
# record_from_result
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.unit
def test_record_from_result_pulls_agent_fields(tmp_path):
    store = RedTeamHistoryStore(history_path=tmp_path / "h.jsonl")
    agent_result = {
        "bypass_attempts": 10,
        "successful_bypasses": 3,
        "scanner_strength": 0.7,
        "gate_strength": 1.0,
        "patches_applied": 1,
        "proposals_generated": 2,
        "status": "patched",
        "prompt_injection_surface": 0.25,
        "prompt_injection_findings": 4,
    }
    snap = store.record_from_result(agent_result, run_id="r1", mode="thorough", target="both")

    assert snap["bypass_attempts"] == 10
    assert snap["successful_bypasses"] == 3
    assert snap["scanner_strength"] == 0.7
    assert snap["gate_strength"] == 1.0
    assert snap["patches_applied"] == 1
    assert snap["proposals_generated"] == 2
    assert snap["status"] == "patched"
    assert snap["prompt_injection_surface"] == 0.25
    assert snap["prompt_injection_findings"] == 4
    assert snap["mode"] == "thorough"


@pytest.mark.unit
def test_record_from_result_handles_missing_fields(tmp_path):
    store = RedTeamHistoryStore(history_path=tmp_path / "h.jsonl")
    snap = store.record_from_result({}, run_id="r1")
    assert snap["bypass_attempts"] == 0
    assert snap["scanner_strength"] == 0.0
    assert snap["gate_strength"] == 0.0


# ─────────────────────────────────────────────────────────────────────────────
# load_history
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.unit
def test_load_history_returns_all(tmp_path):
    store = RedTeamHistoryStore(history_path=tmp_path / "h.jsonl")
    for i in range(5):
        store.record(run_id=f"r{i}", scanner_strength=0.5 + i * 0.05)

    history = store.load_history()
    assert len(history) == 5


@pytest.mark.unit
def test_load_history_respects_limit(tmp_path):
    store = RedTeamHistoryStore(history_path=tmp_path / "h.jsonl")
    for i in range(10):
        store.record(run_id=f"r{i}")

    history = store.load_history(limit=3)
    assert len(history) == 3
    # last 3 records
    assert history[-1]["run_id"] == "r9"


@pytest.mark.unit
def test_load_history_filters_by_mode(tmp_path):
    store = RedTeamHistoryStore(history_path=tmp_path / "h.jsonl")
    store.record(run_id="r1", mode="fast")
    store.record(run_id="r2", mode="thorough")
    store.record(run_id="r3", mode="fast")

    fast_only = store.load_history(mode_filter="fast")
    assert len(fast_only) == 2
    assert all(r["mode"] == "fast" for r in fast_only)


@pytest.mark.unit
def test_load_history_empty_when_no_file(tmp_path):
    store = RedTeamHistoryStore(history_path=tmp_path / "nonexistent.jsonl")
    assert store.load_history() == []


@pytest.mark.unit
def test_load_history_skips_corrupt_lines(tmp_path):
    path = tmp_path / "h.jsonl"
    path.write_text('{"run_id": "r1", "scanner_strength": 0.6}\n{corrupt json\n{"run_id": "r2", "scanner_strength": 0.7}\n')
    store = RedTeamHistoryStore(history_path=path)
    history = store.load_history()
    assert len(history) == 2


# ─────────────────────────────────────────────────────────────────────────────
# get_trend
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.unit
def test_get_trend_returns_points(tmp_path):
    store = RedTeamHistoryStore(history_path=tmp_path / "h.jsonl")
    for i in range(5):
        store.record(run_id=f"r{i}", scanner_strength=0.5 + i * 0.05)

    trend = store.get_trend("scanner_strength")
    assert len(trend) == 5
    assert all("value" in p and "run_id" in p and "recorded_at" in p for p in trend)
    assert trend[0]["value"] == 0.5
    assert trend[-1]["value"] == pytest.approx(0.7, abs=0.01)


@pytest.mark.unit
def test_get_trend_excludes_records_missing_metric(tmp_path):
    store = RedTeamHistoryStore(history_path=tmp_path / "h.jsonl")
    store.record(run_id="r1", scanner_strength=0.6)
    store.record(run_id="r2")  # no scanner_strength override — will still have default 0.0
    # manually write a record without the key
    with open(tmp_path / "h.jsonl", "a") as f:
        f.write(json.dumps({"run_id": "r3", "recorded_at": "2026-01-01T00:00:00Z"}) + "\n")

    trend = store.get_trend("scanner_strength")
    # r3 has no scanner_strength — excluded
    assert all(p["run_id"] != "r3" for p in trend)


@pytest.mark.unit
def test_get_trend_respects_window(tmp_path):
    store = RedTeamHistoryStore(history_path=tmp_path / "h.jsonl")
    for i in range(10):
        store.record(run_id=f"r{i}", scanner_strength=float(i) / 10)

    trend = store.get_trend("scanner_strength", window=4)
    assert len(trend) == 4
    assert trend[-1]["value"] == pytest.approx(0.9, abs=0.01)


@pytest.mark.unit
def test_get_trend_filters_by_mode(tmp_path):
    store = RedTeamHistoryStore(history_path=tmp_path / "h.jsonl")
    store.record(run_id="r1", mode="fast", scanner_strength=0.5)
    store.record(run_id="r2", mode="thorough", scanner_strength=0.9)

    trend = store.get_trend("scanner_strength", mode_filter="thorough")
    assert len(trend) == 1
    assert trend[0]["value"] == 0.9


# ─────────────────────────────────────────────────────────────────────────────
# summary
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.unit
def test_summary_no_history(tmp_path):
    store = RedTeamHistoryStore(history_path=tmp_path / "h.jsonl")
    s = store.summary()
    assert s["scans"] == 0
    assert "No red team scan history yet." in s["message"]


@pytest.mark.unit
def test_summary_basic_fields(tmp_path):
    store = RedTeamHistoryStore(history_path=tmp_path / "h.jsonl")
    for i in range(4):
        store.record(
            run_id=f"r{i}",
            scanner_strength=0.6 + i * 0.05,
            gate_strength=1.0,
            successful_bypasses=i,
            patches_applied=1 if i % 2 == 0 else 0,
            proposals_generated=1,
        )

    s = store.summary(window=4)
    assert s["scans"] == 4
    assert s["latest_gate_strength"] == 1.0
    assert s["total_patches_applied"] == 2
    assert s["total_proposals_generated"] == 4
    assert s["avg_gate_strength"] == 1.0


@pytest.mark.unit
def test_summary_scanner_trend_hardening(tmp_path):
    store = RedTeamHistoryStore(history_path=tmp_path / "h.jsonl")
    # early scans: low strength; recent: high
    for i in range(6):
        store.record(run_id=f"r{i}", scanner_strength=0.5 + i * 0.05)

    s = store.summary(window=6)
    assert s["scanner_trend"] == "hardening"


@pytest.mark.unit
def test_summary_scanner_trend_stable(tmp_path):
    store = RedTeamHistoryStore(history_path=tmp_path / "h.jsonl")
    for i in range(4):
        store.record(run_id=f"r{i}", scanner_strength=0.64)

    s = store.summary(window=4)
    assert s["scanner_trend"] == "stable"
