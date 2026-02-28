"""Unit tests for LearningMetricsSnapshot and RepoProfile."""

import json
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from data_store.learning_metrics import LearningMetricsSnapshot
from data_store.repo_profile import RepoProfile, _detect_repo_id


# ─────────────────────────────────────────────────────────────────────────────
# LearningMetricsSnapshot
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.unit
def test_record_appends_jsonl(tmp_path):
    snap = LearningMetricsSnapshot(history_path=tmp_path / "h.jsonl")
    snap.record(run_id="r1", fix_rate=0.82, artifact_count=10)
    snap.record(run_id="r2", fix_rate=0.85, artifact_count=12)

    lines = (tmp_path / "h.jsonl").read_text().strip().splitlines()
    assert len(lines) == 2
    assert json.loads(lines[0])["run_id"] == "r1"
    assert json.loads(lines[1])["fix_rate"] == 0.85


@pytest.mark.unit
def test_record_omits_none_fields(tmp_path):
    snap = LearningMetricsSnapshot(history_path=tmp_path / "h.jsonl")
    result = snap.record(run_id="r1")  # all optional fields None

    assert "fix_rate" not in result
    assert "artifact_count" not in result
    assert result["run_id"] == "r1"


@pytest.mark.unit
def test_load_history_returns_records(tmp_path):
    snap = LearningMetricsSnapshot(history_path=tmp_path / "h.jsonl")
    for i in range(5):
        snap.record(run_id=f"r{i}", fix_rate=0.5 + i * 0.05, repo_id="test-repo")

    history = snap.load_history()
    assert len(history) == 5


@pytest.mark.unit
def test_load_history_filters_by_repo_id(tmp_path):
    snap = LearningMetricsSnapshot(history_path=tmp_path / "h.jsonl")
    snap.record(run_id="r1", repo_id="abc", fix_rate=0.7)
    snap.record(run_id="r2", repo_id="xyz", fix_rate=0.8)

    filtered = snap.load_history(repo_id="abc")
    assert len(filtered) == 1
    assert filtered[0]["run_id"] == "r1"


@pytest.mark.unit
def test_load_history_empty_when_no_file(tmp_path):
    snap = LearningMetricsSnapshot(history_path=tmp_path / "missing.jsonl")
    assert snap.load_history() == []


@pytest.mark.unit
def test_get_improvement_curve(tmp_path):
    snap = LearningMetricsSnapshot(history_path=tmp_path / "h.jsonl")
    snap.record(run_id="r1", fix_rate=0.60, repo_id="test-repo")
    snap.record(run_id="r2", fix_rate=0.70, repo_id="test-repo")
    snap.record(run_id="r3", repo_id="test-repo")  # no fix_rate — should be excluded

    curve = snap.get_improvement_curve("fix_rate")
    assert len(curve) == 2
    assert curve[0]["value"] == pytest.approx(0.60)
    assert curve[1]["value"] == pytest.approx(0.70)


@pytest.mark.unit
def test_summary_reports_trend(tmp_path):
    snap = LearningMetricsSnapshot(history_path=tmp_path / "h.jsonl")
    for i in range(10):
        snap.record(run_id=f"r{i}", fix_rate=0.5 + i * 0.03, repo_id="test-repo")

    s = snap.summary()
    assert s["runs"] == 10
    assert s["fix_rate_trend"] == "improving"


@pytest.mark.unit
def test_summary_no_history(tmp_path):
    snap = LearningMetricsSnapshot(history_path=tmp_path / "missing.jsonl")
    s = snap.summary()
    assert s["runs"] == 0


# ─────────────────────────────────────────────────────────────────────────────
# RepoProfile
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.unit
def test_repo_profile_creates_and_persists(tmp_path):
    rp = RepoProfile("testrepo", store_dir=tmp_path)
    rp.record_run(
        run_id="r1", fix_rate=0.72, fixes_applied=18, fixable_errors=25,
        architectural_violations={"F403": 3, "F405": 2},
    )

    assert (tmp_path / "testrepo.json").exists()
    data = json.loads((tmp_path / "testrepo.json").read_text())
    assert data["total_runs"] == 1
    assert data["known_architectural_violations"]["F403"] == 3


@pytest.mark.unit
def test_repo_profile_accumulates_across_runs(tmp_path):
    rp = RepoProfile("testrepo", store_dir=tmp_path)
    rp.record_run(run_id="r1", fix_rate=0.7, fixes_applied=7, fixable_errors=10,
                  architectural_violations={"F403": 2})
    rp.record_run(run_id="r2", fix_rate=0.8, fixes_applied=8, fixable_errors=10,
                  architectural_violations={"F403": 3})

    assert rp.total_runs == 2
    assert rp.known_architectural_violations["F403"] == 5


@pytest.mark.unit
def test_known_unfixable_rules_after_two_runs(tmp_path):
    rp = RepoProfile("testrepo", store_dir=tmp_path)
    # F403 appears in 2 runs → marked unfixable
    rp.record_run(run_id="r1", fix_rate=0.7, fixes_applied=7, fixable_errors=10,
                  architectural_violations={"F403": 1})
    rp.record_run(run_id="r2", fix_rate=0.7, fixes_applied=7, fixable_errors=10,
                  architectural_violations={"F403": 1})

    assert "F403" in rp.known_unfixable_rules


@pytest.mark.unit
def test_per_language_fix_rate_ewma(tmp_path):
    rp = RepoProfile("testrepo", store_dir=tmp_path)
    rp.record_run(run_id="r1", fix_rate=0.8, fixes_applied=8, fixable_errors=10,
                  architectural_violations={}, language="python")
    rp.record_run(run_id="r2", fix_rate=0.6, fixes_applied=6, fixable_errors=10,
                  architectural_violations={}, language="python")

    rate = rp.fix_rate_for_language("python")
    # EWMA: 0.3 * 0.6 + 0.7 * 0.8 = 0.74
    assert rate == pytest.approx(0.74)


@pytest.mark.unit
def test_repo_profile_loads_existing(tmp_path):
    rp1 = RepoProfile("testrepo", store_dir=tmp_path)
    rp1.record_run(run_id="r1", fix_rate=0.7, fixes_applied=7, fixable_errors=10,
                   architectural_violations={"F403": 2})

    # Load fresh instance — should see persisted data
    rp2 = RepoProfile("testrepo", store_dir=tmp_path)
    assert rp2.total_runs == 1
    assert rp2.known_architectural_violations["F403"] == 2


@pytest.mark.unit
def test_run_history_capped_at_30(tmp_path):
    rp = RepoProfile("testrepo", store_dir=tmp_path)
    for i in range(35):
        rp.record_run(run_id=f"r{i}", fix_rate=0.7, fixes_applied=7, fixable_errors=10,
                      architectural_violations={})
    data = json.loads((tmp_path / "testrepo.json").read_text())
    assert len(data["run_history"]) == 30


@pytest.mark.unit
def test_detect_repo_id_fallback_is_stable(tmp_path):
    # No git remote available in tmp_path — should fall back to path hash
    with patch("subprocess.run", side_effect=Exception("no git")):
        id1 = _detect_repo_id(str(tmp_path))
        id2 = _detect_repo_id(str(tmp_path))
    assert id1 == id2
    assert len(id1) == 12


@pytest.mark.unit
def test_summary_contents(tmp_path):
    rp = RepoProfile("testrepo", store_dir=tmp_path)
    rp.record_run(run_id="r1", fix_rate=0.75, fixes_applied=15, fixable_errors=20,
                  architectural_violations={"F403": 5}, language="python")

    s = rp.summary()
    assert s["repo_id"] == "testrepo"
    assert s["total_runs"] == 1
    assert "python" in s["fix_rates_by_language"]
    assert s["known_architectural_violations"]["F403"] == 5


# ─────────────────────────────────────────────────────────────────────────────
# SREAgent integration — architectural violations excluded from fix_rate
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.unit
def test_sre_agent_excludes_architectural_violations_from_fix_rate():
    """fix_rate should be over fixable errors only, not total."""
    import sys
    sys.path.insert(0, str(Path(__file__).parent.parent / "src"))
    from agents import SREAgent

    agent = SREAgent.__new__(SREAgent)
    agent.agent_name = "SRE_Agent"
    agent.use_data_store = False
    agent.use_rag = False
    agent.rag = None
    agent.feedback = None
    agent.outcome_tracker = None
    agent._threshold_calibrator = None
    agent._strategy_selector = None
    agent.execution_history = []
    agent.agent_registry = None
    agent._delegation_depth = 0

    errors = [
        {"rule": "W291", "message": "trailing whitespace"},   # fixable
        {"rule": "W291", "message": "trailing whitespace"},   # fixable
        {"rule": "F403", "message": "star import"},            # architectural
        {"rule": "F405", "message": "may be undefined"},       # architectural
    ]
    result = agent.execute({"errors": errors})

    assert result["total_errors"] == 4
    assert result["fixable_errors"] == 2
    assert result["architectural_violations"] == 2
    assert result["architectural_violations_by_rule"]["F403"] == 1
    assert result["architectural_violations_by_rule"]["F405"] == 1
    # fix_rate is over fixable only — even if W291 is in fix_map
    assert result["fix_rate"] == pytest.approx(result["fixes_applied"] / 2)
