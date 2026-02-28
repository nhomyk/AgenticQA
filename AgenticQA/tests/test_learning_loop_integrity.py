"""Unit tests for LearningLoopIntegrityGuard."""
import json
import os
import pytest
from pathlib import Path
from agenticqa.security.learning_loop_integrity import LearningLoopIntegrityGuard, IntegrityViolation


@pytest.fixture
def guard():
    return LearningLoopIntegrityGuard()


@pytest.fixture
def strict_guard():
    return LearningLoopIntegrityGuard(strict=True)


# ── Valid records ─────────────────────────────────────────────────────────────

@pytest.mark.unit
def test_valid_metrics_record_passes(guard):
    rec = {"repo_id": "repo1", "run_id": "run-001", "recorded_at": "2026-01-01T00:00:00Z"}
    ok, violations = guard.validate_metrics_record(rec)
    assert ok
    assert violations == []


@pytest.mark.unit
def test_valid_repo_profile_passes(guard):
    data = {
        "repo_id": "repo1",
        "total_runs": 10,
        "fix_rates_by_language": {"python": 0.8},
        "known_unfixable_rules": [],
    }
    ok, violations = guard.validate_repo_profile(data)
    assert ok
    assert violations == []


# ── Missing fields ────────────────────────────────────────────────────────────

@pytest.mark.unit
def test_missing_repo_id_blocked(guard):
    rec = {"run_id": "r1", "recorded_at": "2026-01-01T00:00:00Z"}
    ok, violations = guard.validate_metrics_record(rec)
    assert not ok
    assert any(v.violation_type == "MISSING_FIELD" for v in violations)


@pytest.mark.unit
def test_missing_total_runs_in_profile_blocked(guard):
    data = {"repo_id": "r", "fix_rates_by_language": {}, "known_unfixable_rules": []}
    ok, violations = guard.validate_repo_profile(data)
    assert not ok


# ── Out-of-range values ───────────────────────────────────────────────────────

@pytest.mark.unit
def test_fix_rate_above_1_blocked(guard):
    data = {
        "repo_id": "r", "total_runs": 1,
        "fix_rates_by_language": {"python": 1.5},  # impossible
        "known_unfixable_rules": [],
    }
    ok, violations = guard.validate_repo_profile(data)
    assert not ok
    assert any(v.violation_type == "OUT_OF_RANGE" for v in violations)


@pytest.mark.unit
def test_negative_fix_rate_blocked(guard):
    data = {
        "repo_id": "r", "total_runs": 1,
        "fix_rates_by_language": {"python": -0.1},
        "known_unfixable_rules": [],
    }
    ok, violations = guard.validate_repo_profile(data)
    assert not ok


@pytest.mark.unit
def test_impossible_total_runs_blocked(guard):
    rec = {"repo_id": "r", "run_id": "x", "recorded_at": "t", "total_runs": -5}
    ok, violations = guard.validate_metrics_record(rec)
    assert not ok
    assert any(v.violation_type == "OUT_OF_RANGE" for v in violations)


# ── Type errors ───────────────────────────────────────────────────────────────

@pytest.mark.unit
def test_wrong_type_repo_id(guard):
    rec = {"repo_id": 123, "run_id": "x", "recorded_at": "t"}
    ok, violations = guard.validate_metrics_record(rec)
    assert any(v.violation_type == "TYPE_ERROR" for v in violations)


# ── Strict mode ───────────────────────────────────────────────────────────────

@pytest.mark.unit
def test_strict_fails_on_type_error(strict_guard):
    rec = {"repo_id": 123, "run_id": "x", "recorded_at": "t"}
    ok, _ = strict_guard.validate_metrics_record(rec)
    assert not ok


# ── HMAC sidecar ─────────────────────────────────────────────────────────────

@pytest.mark.unit
def test_sign_file_no_key_returns_false(guard, tmp_path):
    f = tmp_path / "test.jsonl"
    f.write_text("line1\n")
    assert guard.sign_file(f) is False


@pytest.mark.unit
def test_sign_and_verify_roundtrip(tmp_path):
    g = LearningLoopIntegrityGuard()
    g._hmac_key = b"test-secret-key"
    f = tmp_path / "metrics.jsonl"
    f.write_text('{"repo_id":"r","run_id":"x","recorded_at":"t"}\n')
    assert g.sign_file(f) is True
    ok, msg = g.verify_file(f)
    assert ok, msg


@pytest.mark.unit
def test_verify_fails_on_tampered_file(tmp_path):
    g = LearningLoopIntegrityGuard()
    g._hmac_key = b"test-secret-key"
    f = tmp_path / "metrics.jsonl"
    f.write_text('{"repo_id":"r","run_id":"x","recorded_at":"t"}\n')
    g.sign_file(f)
    f.write_text('{"repo_id":"r","run_id":"x","recorded_at":"t","extra":"injected"}\n')
    ok, msg = g.verify_file(f)
    assert not ok
    assert "tampered" in msg


@pytest.mark.unit
def test_verify_no_sidecar_passes(tmp_path):
    g = LearningLoopIntegrityGuard()
    g._hmac_key = b"test-secret-key"
    f = tmp_path / "metrics.jsonl"
    f.write_text("data\n")
    ok, msg = g.verify_file(f)
    assert ok  # no sidecar → not blocking


# ── Bulk file validation ──────────────────────────────────────────────────────

@pytest.mark.unit
def test_validate_metrics_file(guard, tmp_path):
    f = tmp_path / "metrics.jsonl"
    f.write_text(
        '{"repo_id":"r","run_id":"x","recorded_at":"t"}\n'
        '{"repo_id":"r","run_id":"y","recorded_at":"t","total_runs":-1}\n'
        '{"invalid json\n'
    )
    total, bad, errors = guard.validate_metrics_file(f)
    assert total == 3
    assert bad == 2  # out-of-range + json error
    assert len(errors) == 2


@pytest.mark.unit
def test_violation_str():
    v = IntegrityViolation("fix_rate", "OUT_OF_RANGE", "value=1.5 outside [0, 1]")
    assert "OUT_OF_RANGE" in str(v)
    assert "fix_rate" in str(v)
