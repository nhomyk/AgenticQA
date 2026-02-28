"""Unit tests for ReleaseReadinessScorer."""
import pytest
from agenticqa.scoring.release_readiness import ReleaseReadinessScorer, _SHIP_THRESHOLD


@pytest.fixture
def scorer():
    return ReleaseReadinessScorer()


# ── Perfect / all-green ───────────────────────────────────────────────────────

@pytest.mark.unit
def test_perfect_score_ships(scorer):
    report = scorer.score(
        sdet_result={"current_coverage": 90.0},
        security_findings=[],
        cve_result={"critical_cves": 0, "high_cves": 0, "reachable_cves": []},
        perf_result={"regression_detected": False},
        compliance_result={"violations": [], "conformity_score": 1.0},
        architecture_result={"untested_critical_high": 0, "total_areas": 20},
    )
    assert report.recommendation == "SHIP IT"
    assert report.overall_score >= _SHIP_THRESHOLD
    assert report.blocking_issues == []


@pytest.mark.unit
def test_perfect_score_is_100(scorer):
    report = scorer.score(
        sdet_result={"current_coverage": 95.0},
        security_findings=[],
        cve_result={"critical_cves": 0, "reachable_cves": []},
        perf_result={"regression_detected": False},
        compliance_result={"violations": [], "conformity_score": 1.0},
        architecture_result={"untested_critical_high": 0, "total_areas": 10},
    )
    assert report.overall_score == 100.0


# ── Blocking conditions ───────────────────────────────────────────────────────

@pytest.mark.unit
def test_critical_cve_blocks(scorer):
    report = scorer.score(
        sdet_result={"current_coverage": 90.0},
        security_findings=[],
        cve_result={"critical_cves": 1, "reachable_cves": []},
        perf_result={"regression_detected": False},
    )
    assert report.recommendation == "DO NOT SHIP"
    assert len(report.blocking_issues) >= 1
    cve_signal = report.by_name("cve_exposure")
    assert cve_signal.blocking is True
    assert cve_signal.status == "red"


@pytest.mark.unit
def test_critical_security_finding_blocks(scorer):
    report = scorer.score(
        security_findings=[{"severity": "critical", "detail": "RCE via eval"}],
    )
    assert report.recommendation == "DO NOT SHIP"
    assert report.by_name("security_findings").blocking is True


@pytest.mark.unit
def test_two_critical_security_findings_blocks(scorer):
    findings = [{"severity": "critical"}, {"severity": "critical"}]
    report = scorer.score(security_findings=findings)
    signal = report.by_name("security_findings")
    assert signal.score == 0.0
    assert report.recommendation == "DO NOT SHIP"


@pytest.mark.unit
def test_performance_regression_blocks(scorer):
    report = scorer.score(
        sdet_result={"current_coverage": 88.0},
        security_findings=[],
        perf_result={"regression_detected": True, "duration_ms": 500, "baseline_ms": 200},
    )
    assert report.recommendation == "DO NOT SHIP"
    assert report.by_name("performance_regression").blocking is True


@pytest.mark.unit
def test_very_low_coverage_blocks(scorer):
    report = scorer.score(sdet_result={"current_coverage": 30.0})
    cov = report.by_name("test_coverage")
    assert cov.blocking is True
    assert report.recommendation == "DO NOT SHIP"


@pytest.mark.unit
def test_three_high_cves_blocks(scorer):
    report = scorer.score(
        cve_result={"critical_cves": 0, "high_cves": 3, "reachable_cves": []}
    )
    assert report.by_name("cve_exposure").blocking is True


# ── Yellow / review required ──────────────────────────────────────────────────

@pytest.mark.unit
def test_high_findings_review_required(scorer):
    findings = [{"severity": "high"}]
    report = scorer.score(
        sdet_result={"current_coverage": 85.0},
        security_findings=findings,
        cve_result={"critical_cves": 0, "reachable_cves": []},
        perf_result={"regression_detected": False},
        compliance_result={"violations": [], "conformity_score": 1.0},
        architecture_result={"untested_critical_high": 0, "total_areas": 10},
    )
    assert report.recommendation in ("REVIEW REQUIRED", "SHIP IT")
    assert report.by_name("security_findings").status == "yellow"


@pytest.mark.unit
def test_coverage_70_pct_is_yellow(scorer):
    report = scorer.score(sdet_result={"current_coverage": 74.0})
    assert report.by_name("test_coverage").status == "yellow"


@pytest.mark.unit
def test_compliance_violations_are_yellow(scorer):
    report = scorer.score(
        compliance_result={"violations": [{"rule": "HIPAA_AUDIT_MISSING"}], "conformity_score": 0.75}
    )
    assert report.by_name("compliance_violations").status == "yellow"


# ── Grey / missing signals ────────────────────────────────────────────────────

@pytest.mark.unit
def test_no_inputs_returns_50(scorer):
    report = scorer.score()
    assert report.overall_score == 50.0
    assert report.signals_provided == 0


@pytest.mark.unit
def test_partial_signals_grey_excluded(scorer):
    report = scorer.score(
        sdet_result={"current_coverage": 90.0},
        security_findings=[],
    )
    # Grey signals don't drag down score
    assert report.signals_provided == 2
    provided = [s for s in report.signals if s.status != "grey"]
    assert len(provided) == 2


@pytest.mark.unit
def test_grey_signal_not_blocking(scorer):
    report = scorer.score()  # all grey
    assert report.blocking_issues == []


# ── Score structure ───────────────────────────────────────────────────────────

@pytest.mark.unit
def test_to_dict_has_required_fields(scorer):
    report = scorer.score(sdet_result={"current_coverage": 80.0})
    d = report.to_dict()
    for key in ("overall_score", "recommendation", "recommendation_reason",
                "color", "signals", "blocking_issues",
                "signals_provided", "signals_total", "timestamp"):
        assert key in d


@pytest.mark.unit
def test_signal_to_dict_fields(scorer):
    report = scorer.score(sdet_result={"current_coverage": 80.0})
    sig = report.by_name("test_coverage").to_dict()
    for key in ("name", "display_name", "score", "weight",
                "weighted_contribution", "status", "blocking", "detail"):
        assert key in sig


@pytest.mark.unit
def test_six_signals_always_returned(scorer):
    report = scorer.score()
    assert len(report.signals) == 6
    assert report.signals_total == 6


@pytest.mark.unit
def test_color_red_on_do_not_ship(scorer):
    report = scorer.score(
        cve_result={"critical_cves": 2, "reachable_cves": []}
    )
    assert report.color == "red"


@pytest.mark.unit
def test_color_green_on_ship_it(scorer):
    report = scorer.score(
        sdet_result={"current_coverage": 92.0},
        security_findings=[],
        cve_result={"critical_cves": 0, "reachable_cves": []},
        perf_result={"regression_detected": False},
        compliance_result={"violations": [], "conformity_score": 1.0},
        architecture_result={"untested_critical_high": 0, "total_areas": 5},
    )
    assert report.color == "green"


# ── Architecture coverage signal ──────────────────────────────────────────────

@pytest.mark.unit
def test_arch_full_dict_parsed(scorer):
    # Simulate a full ArchitectureScanResult.to_dict() output
    arch_dict = {
        "integration_areas": [
            {"severity": "critical", "test_files": []},
            {"severity": "high", "test_files": ["tests/test_foo.py"]},
            {"severity": "medium", "test_files": []},
        ]
    }
    report = scorer.score(architecture_result=arch_dict)
    sig = report.by_name("architecture_coverage")
    assert sig.status != "grey"
    # 1 untested critical (medium not counted), 1 covered high → 1/2 untested = 50%
    assert sig.score <= 60.0


@pytest.mark.unit
def test_arch_all_tested_is_green(scorer):
    report = scorer.score(
        architecture_result={"untested_critical_high": 0, "total_areas": 50}
    )
    assert report.by_name("architecture_coverage").status == "green"
    assert report.by_name("architecture_coverage").score == 100.0
