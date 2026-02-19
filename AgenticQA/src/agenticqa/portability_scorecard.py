"""Repo-portability scorecard for baseline-to-delta value tracking across any repository."""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Dict, List, Optional


def _coerce_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except Exception:
        return default


def _repo_key(repo_root: str) -> str:
    normalized = str(Path(repo_root).expanduser().resolve())
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()[:16]


def _default_baseline_path() -> Path:
    base = Path.home() / ".agenticqa"
    base.mkdir(parents=True, exist_ok=True)
    return base / "repo_portability_baselines.json"


def load_baseline(repo_root: str, baseline_path: Optional[Path] = None) -> Optional[Dict[str, Any]]:
    path = baseline_path or _default_baseline_path()
    if not path.exists():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        return (payload.get("repos") or {}).get(_repo_key(repo_root))
    except Exception:
        return None


def save_baseline(
    repo_root: str,
    scorecard: Dict[str, Any],
    note: str = "",
    baseline_path: Optional[Path] = None,
) -> Dict[str, Any]:
    path = baseline_path or _default_baseline_path()
    payload: Dict[str, Any]
    if path.exists():
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            payload = {"repos": {}}
    else:
        payload = {"repos": {}}

    repos = payload.setdefault("repos", {})
    key = _repo_key(repo_root)
    repos[key] = {
        "repo_root": str(Path(repo_root).expanduser().resolve()),
        "saved_at": datetime.now(UTC).isoformat(),
        "note": note,
        "scorecard": scorecard,
    }

    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return repos[key]


def build_portability_scorecard(
    repo_profile: Dict[str, Any],
    workflow_metrics: Dict[str, Any],
    observability_insights: Dict[str, Any],
    baseline: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    profile = repo_profile or {}
    metrics = workflow_metrics or {}
    insights = observability_insights or {}

    primary_language = str(profile.get("primary_language") or "unknown")
    package_managers = profile.get("package_managers") or []
    test_hints = profile.get("test_runner_hints") or []
    ci_provider = str(profile.get("ci_provider") or "none")
    has_tests_dir = bool(profile.get("has_tests_dir"))

    onboarding = 0.0
    onboarding += 30.0 if primary_language != "unknown" else 0.0
    onboarding += 20.0 if has_tests_dir else 0.0
    onboarding += 20.0 if ci_provider != "none" else 0.0
    onboarding += 15.0 if package_managers else 0.0
    onboarding += 15.0 if test_hints else 0.0

    pass_rate = _coerce_float(metrics.get("pass_rate"), 0.0)
    reliability = max(0.0, min(100.0, pass_rate * 100.0))

    quality = (insights.get("quality") or {}) if isinstance(insights, dict) else {}
    avg_completeness = _coerce_float(quality.get("avg_completeness_ratio"), 0.0)
    avg_decision_quality = _coerce_float(quality.get("avg_decision_quality_score"), 0.0)
    observability = max(0.0, min(100.0, (avg_completeness * 0.6 + avg_decision_quality * 0.4) * 100.0))

    overall = (onboarding * 0.40) + (reliability * 0.35) + (observability * 0.25)

    quick_wins: List[dict] = []
    if primary_language == "unknown":
        quick_wins.append({
            "action": "Add minimal language marker files (e.g., pyproject.toml or package.json) for faster auto-routing",
            "impact_rank": 1,
            "why": "Primary language is undetected — routing and test automation are blocked until resolved",
        })
    if not has_tests_dir:
        quick_wins.append({
            "action": "Create a tests directory and seed smoke tests for immediate quality signal",
            "impact_rank": 2,
            "why": "No tests directory found — execution reliability score cannot improve without test coverage",
        })
    if ci_provider == "none":
        quick_wins.append({
            "action": "Add CI workflow to enable automated baseline→delta tracking",
            "impact_rank": 3,
            "why": "No CI provider detected — automated quality gates and trend tracking are unavailable",
        })
    if not test_hints:
        quick_wins.append({
            "action": "Define a canonical test command (pytest/npm test) to maximize portability automation",
            "impact_rank": 4,
            "why": "No test runner detected — portability automation cannot confirm execution reliability",
        })

    scorecard = {
        "timestamp": datetime.now(UTC).isoformat(),
        "repo_profile": profile,
        "scores": {
            "onboarding_readiness": round(onboarding, 2),
            "execution_reliability": round(reliability, 2),
            "observability_quality": round(observability, 2),
            "overall": round(overall, 2),
        },
        "signals": {
            "pass_rate": pass_rate,
            "avg_trace_completeness": avg_completeness,
            "avg_decision_quality": avg_decision_quality,
        },
        "quick_wins": quick_wins,
    }

    baseline_score = None
    if baseline:
        baseline_score = (((baseline or {}).get("scorecard") or {}).get("scores") or {}).get("overall")
    elif (scorecard.get("scores") or {}).get("overall") is not None:
        baseline_score = None

    if baseline and baseline_score is not None:
        current = _coerce_float(scorecard["scores"]["overall"], 0.0)
        base = _coerce_float(baseline_score, 0.0)
        delta = current - base
        scorecard["delta"] = {
            "baseline_overall": round(base, 2),
            "current_overall": round(current, 2),
            "overall_delta": round(delta, 2),
            "trend": "improved" if delta > 0 else "regressed" if delta < 0 else "flat",
            "baseline_saved_at": baseline.get("saved_at"),
        }
    else:
        scorecard["delta"] = None

    return scorecard


def build_portability_roi_report(
    repo_root: str,
    scorecard: Dict[str, Any],
    workflow_metrics: Dict[str, Any],
) -> Dict[str, Any]:
    """Build a compact ROI report with baseline/current/delta rows.

    The report is intentionally lightweight so it can be exported by API and rendered
    in dashboard or downstream artifacts without additional transformation.
    """
    safe_scorecard = scorecard or {}
    safe_metrics = workflow_metrics or {}
    delta = safe_scorecard.get("delta") or {}
    scores = safe_scorecard.get("scores") or {}

    baseline_overall = _coerce_float(delta.get("baseline_overall"), _coerce_float(scores.get("overall"), 0.0))
    current_overall = _coerce_float(delta.get("current_overall"), _coerce_float(scores.get("overall"), 0.0))
    overall_delta = round(current_overall - baseline_overall, 2)

    pass_rate = _coerce_float(safe_metrics.get("pass_rate"), 0.0)
    mttr_hours = _coerce_float(safe_metrics.get("mttr_hours"), 0.0)
    rerun_rate = _coerce_float(safe_metrics.get("rerun_rate"), 0.0)

    # Heuristic: each 1% pass rate improvement saves ~0.5 dev-hours/sprint per 100 pipeline runs.
    # Each 1-hour MTTR reduction saves ~1 dev-hour per incident.
    pass_rate_pct = round(pass_rate * 100.0, 2)
    dev_hours_from_pass_rate = round(pass_rate_pct * 0.5, 1)
    dev_hours_from_mttr = round(max(0.0, (10.0 - mttr_hours)) * 1.0, 1)  # baseline assumption: 10h MTTR pre-adoption

    rows = [
        {
            "kpi": "Portability overall score",
            "baseline": round(baseline_overall, 2),
            "current": round(current_overall, 2),
            "delta": round(overall_delta, 2),
            "direction": "improved" if overall_delta > 0 else "regressed" if overall_delta < 0 else "flat",
            "estimated_dev_hours_saved": None,
        },
        {
            "kpi": "Workflow pass rate",
            "baseline": None,
            "current": pass_rate_pct,
            "delta": None,
            "direction": "higher_is_better",
            "estimated_dev_hours_saved": dev_hours_from_pass_rate,
        },
        {
            "kpi": "Mean time to resolve (hours)",
            "baseline": None,
            "current": round(mttr_hours, 2),
            "delta": None,
            "direction": "lower_is_better",
            "estimated_dev_hours_saved": dev_hours_from_mttr,
        },
        {
            "kpi": "Pipeline re-run rate",
            "baseline": None,
            "current": round(rerun_rate * 100.0, 2),
            "delta": None,
            "direction": "lower_is_better",
            "estimated_dev_hours_saved": None,
        },
    ]

    return {
        "generated_at": datetime.now(UTC).isoformat(),
        "repo": str(Path(repo_root).expanduser().resolve()),
        "trend": (delta.get("trend") or ("improved" if overall_delta > 0 else "regressed" if overall_delta < 0 else "flat")),
        "rows": rows,
        "quick_wins": list(safe_scorecard.get("quick_wins") or []),
    }
