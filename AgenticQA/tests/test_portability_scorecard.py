from pathlib import Path

from src.agenticqa.portability_scorecard import (
    build_portability_roi_report,
    build_portability_scorecard,
    load_baseline,
    save_baseline,
)


def test_build_portability_scorecard_without_baseline():
    repo_profile = {
        "primary_language": "python",
        "package_managers": ["pip"],
        "test_runner_hints": ["pytest"],
        "ci_provider": "github_actions",
        "has_tests_dir": True,
    }
    workflow_metrics = {"pass_rate": 0.92}
    observability_insights = {
        "quality": {
            "avg_completeness_ratio": 0.98,
            "avg_decision_quality_score": 0.78,
        }
    }

    scorecard = build_portability_scorecard(
        repo_profile=repo_profile,
        workflow_metrics=workflow_metrics,
        observability_insights=observability_insights,
        baseline=None,
    )

    assert scorecard["scores"]["overall"] > 0
    assert scorecard["delta"] is None
    assert isinstance(scorecard["quick_wins"], list)


def test_build_portability_scorecard_with_improved_delta():
    repo_profile = {
        "primary_language": "python",
        "package_managers": ["pip"],
        "test_runner_hints": ["pytest"],
        "ci_provider": "github_actions",
        "has_tests_dir": True,
    }
    baseline = {
        "saved_at": "2026-01-01T00:00:00+00:00",
        "scorecard": {
            "scores": {
                "overall": 55.0,
            }
        },
    }

    scorecard = build_portability_scorecard(
        repo_profile=repo_profile,
        workflow_metrics={"pass_rate": 0.95},
        observability_insights={
            "quality": {
                "avg_completeness_ratio": 0.99,
                "avg_decision_quality_score": 0.90,
            }
        },
        baseline=baseline,
    )

    assert scorecard["delta"] is not None
    assert scorecard["delta"]["trend"] in {"improved", "regressed", "flat"}
    assert scorecard["delta"]["current_overall"] == scorecard["scores"]["overall"]


def test_save_and_load_baseline_roundtrip(tmp_path: Path):
    baseline_path = tmp_path / "baselines.json"
    repo_root = str(tmp_path / "repo")
    scorecard = {
        "scores": {"overall": 66.6},
        "quick_wins": [],
    }

    saved = save_baseline(
        repo_root=repo_root,
        scorecard=scorecard,
        note="initial baseline",
        baseline_path=baseline_path,
    )

    loaded = load_baseline(repo_root=repo_root, baseline_path=baseline_path)

    assert saved["note"] == "initial baseline"
    assert loaded is not None
    assert loaded["scorecard"]["scores"]["overall"] == 66.6


def test_build_portability_roi_report_contains_rows(tmp_path: Path):
    repo_root = str(tmp_path / "repo")
    report = build_portability_roi_report(
        repo_root=repo_root,
        scorecard={
            "scores": {"overall": 82.5},
            "delta": {
                "baseline_overall": 75.0,
                "current_overall": 82.5,
                "trend": "improved",
            },
            "quick_wins": ["Add CI workflow"],
        },
        workflow_metrics={
            "pass_rate": 0.91,
            "mttr_hours": 6.5,
            "rerun_rate": 0.14,
        },
    )

    assert report["trend"] == "improved"
    assert isinstance(report["rows"], list)
    assert len(report["rows"]) >= 4
    assert report["rows"][0]["kpi"] == "Portability overall score"
    assert report["rows"][0]["delta"] == 7.5
    # Verify estimated_dev_hours_saved is present in all rows
    for row in report["rows"]:
        assert "estimated_dev_hours_saved" in row


def test_quick_wins_are_ranked_dicts_when_fields_missing():
    """quick_wins should be dicts with action/impact_rank/why when profile is incomplete."""
    scorecard = build_portability_scorecard(
        repo_profile={
            "primary_language": "unknown",
            "package_managers": [],
            "test_runner_hints": [],
            "ci_provider": "none",
            "has_tests_dir": False,
        },
        workflow_metrics={"pass_rate": 0.0},
        observability_insights={},
        baseline=None,
    )

    wins = scorecard["quick_wins"]
    assert len(wins) == 4
    for win in wins:
        assert isinstance(win, dict)
        assert "action" in win
        assert "impact_rank" in win
        assert "why" in win
    # Sorted by impact_rank ascending
    ranks = [w["impact_rank"] for w in wins]
    assert ranks == sorted(ranks)
