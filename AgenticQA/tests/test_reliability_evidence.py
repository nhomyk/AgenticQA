"""Tests for reliability and evidence helpers."""

import json
import os
import sys
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from agenticqa.reliability_evidence import build_evidence_summary, read_latest_jsonl


def test_read_latest_jsonl_returns_last_valid_object(tmp_path):
    p = Path(tmp_path) / "history.jsonl"
    p.write_text(
        "\n".join(
            [
                json.dumps({"pass_rate_uplift": 0.1}),
                "not-json",
                json.dumps({"pass_rate_uplift": 0.25}),
            ]
        ),
        encoding="utf-8",
    )

    latest = read_latest_jsonl(p)
    assert latest is not None
    assert latest.get("pass_rate_uplift") == 0.25


def test_build_evidence_summary_sets_claim_statuses():
    metrics = {"pass_rate": 0.85, "mttr_minutes": 10}
    latest_benchmark = {
        "pass_rate_uplift": 0.2,
        "baseline_no_autofix": {"pass_rate": 0.0},
        "treatment_autofix": {"pass_rate": 0.2},
    }

    evidence = build_evidence_summary(metrics=metrics, latest_benchmark=latest_benchmark, trace_count=5)
    claims = evidence["claims"]

    assert claims["workflow_execution_reliability"]["status"] == "strong"
    assert claims["incident_recovery_speed"]["status"] == "strong"
    assert claims["sdet_autofix_effectiveness"]["status"] == "strong"
    assert claims["observability_coverage"]["status"] == "strong"
