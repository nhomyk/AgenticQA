"""Unit tests for ObligationsTimeline."""
import pytest
from datetime import date

from agenticqa.compliance.obligations_timeline import (
    ObligationsTimeline,
    ObligationsPlan,
    Obligation,
)


# ── Helpers ────────────────────────────────────────────────────────────────────

def timeline() -> ObligationsTimeline:
    return ObligationsTimeline()


def plan(tier="high_risk", eu=0.40, hipaa=0.50, include_met=True) -> ObligationsPlan:
    return timeline().generate(
        eu_ai_act_tier=tier,
        eu_conformity_score=eu,
        hipaa_score=hipaa,
        include_met=include_met,
    )


# ── Output structure ───────────────────────────────────────────────────────────

@pytest.mark.unit
def test_returns_obligation_plan():
    p = plan()
    assert isinstance(p, ObligationsPlan)
    assert isinstance(p.obligations, list)
    assert len(p.obligations) > 0


@pytest.mark.unit
def test_to_dict_has_required_fields():
    d = plan().to_dict()
    for key in ("eu_ai_act_tier", "eu_conformity_score", "hipaa_score",
                "unmet_count", "overdue_count", "critical_count", "obligations"):
        assert key in d


@pytest.mark.unit
def test_obligation_to_dict_has_required_fields():
    ob = plan().obligations[0]
    d = ob.to_dict()
    for key in ("regulation", "article", "title", "action",
                "deadline", "days_remaining", "priority", "met"):
        assert key in d


@pytest.mark.unit
def test_summary_is_string():
    assert isinstance(plan().summary(), str)


# ── EU AI Act tier gating ──────────────────────────────────────────────────────

@pytest.mark.unit
def test_high_risk_includes_art9():
    regulations = [(o.regulation, o.article) for o in plan(tier="high_risk").obligations]
    assert ("EU AI Act", "Art.9") in regulations


@pytest.mark.unit
def test_high_risk_includes_art13():
    regulations = [(o.regulation, o.article) for o in plan(tier="high_risk").obligations]
    assert ("EU AI Act", "Art.13") in regulations


@pytest.mark.unit
def test_high_risk_includes_art14():
    regulations = [(o.regulation, o.article) for o in plan(tier="high_risk").obligations]
    assert ("EU AI Act", "Art.14") in regulations


@pytest.mark.unit
def test_high_risk_includes_art17():
    regulations = [(o.regulation, o.article) for o in plan(tier="high_risk").obligations]
    assert ("EU AI Act", "Art.17") in regulations


@pytest.mark.unit
def test_minimal_risk_excludes_art9():
    regulations = [(o.regulation, o.article) for o in plan(tier="minimal_risk").obligations]
    assert ("EU AI Act", "Art.9") not in regulations


@pytest.mark.unit
def test_limited_risk_includes_art52():
    regulations = [(o.regulation, o.article) for o in plan(tier="limited_risk").obligations]
    assert ("EU AI Act", "Art.52") in regulations


@pytest.mark.unit
def test_all_tiers_include_art5():
    for tier in ("high_risk", "limited_risk", "minimal_risk", "unknown"):
        regulations = [(o.regulation, o.article) for o in plan(tier=tier).obligations]
        assert ("EU AI Act", "Art.5") in regulations, f"Art.5 missing for tier={tier}"


@pytest.mark.unit
def test_all_tiers_include_gpai_art53():
    for tier in ("high_risk", "limited_risk", "minimal_risk"):
        regulations = [(o.regulation, o.article) for o in plan(tier=tier).obligations]
        assert ("EU AI Act", "Art.53") in regulations, f"Art.53 missing for tier={tier}"


# ── HIPAA obligations ──────────────────────────────────────────────────────────

@pytest.mark.unit
def test_hipaa_obligations_always_present():
    p = plan(tier="minimal_risk", hipaa=0.30)
    hipaa_obs = [o for o in p.obligations if o.regulation == "HIPAA"]
    assert len(hipaa_obs) >= 3


@pytest.mark.unit
def test_hipaa_308_present():
    obs = [o for o in plan().obligations if o.regulation == "HIPAA"]
    articles = [o.article for o in obs]
    assert "§164.308(a)(1)" in articles


@pytest.mark.unit
def test_hipaa_312a_present():
    obs = [o for o in plan().obligations if o.regulation == "HIPAA"]
    articles = [o.article for o in obs]
    assert "§164.312(a)(1)" in articles


# ── Met / unmet logic ──────────────────────────────────────────────────────────

@pytest.mark.unit
def test_perfect_scores_mark_obligations_met():
    p = timeline().generate(
        eu_ai_act_tier="minimal_risk",
        eu_conformity_score=1.0,
        hipaa_score=1.0,
    )
    unmet = [o for o in p.obligations if not o.met]
    # Some obligations (Art.9, 13, 14, 17, 22) only apply to high_risk
    # For minimal_risk + perfect scores, most should be met
    assert len(unmet) <= 2


@pytest.mark.unit
def test_zero_scores_produce_many_unmet():
    p = plan(eu=0.0, hipaa=0.0)
    assert p.unmet_count > 5


@pytest.mark.unit
def test_include_met_false_filters_satisfied():
    p_all = plan(eu=1.0, hipaa=1.0, include_met=True)
    p_unmet = plan(eu=1.0, hipaa=1.0, include_met=False)
    assert len(p_unmet.obligations) <= len(p_all.obligations)


@pytest.mark.unit
def test_unmet_count_matches_obligation_list():
    p = plan(eu=0.30, hipaa=0.40)
    assert p.unmet_count == sum(1 for o in p.obligations if not o.met)


# ── Priority ordering ──────────────────────────────────────────────────────────

@pytest.mark.unit
def test_obligations_sorted_highest_priority_first():
    p = plan(eu=0.30, hipaa=0.30)
    priority_order = ["OVERDUE", "CRITICAL", "HIGH", "MEDIUM", "LOW"]
    indices = [priority_order.index(o.priority) for o in p.obligations]
    assert indices == sorted(indices)


@pytest.mark.unit
def test_deadline_is_iso_date_string():
    for ob in plan().obligations:
        date.fromisoformat(ob.deadline)   # raises if invalid


@pytest.mark.unit
def test_days_remaining_matches_deadline():
    today = date.today()
    for ob in plan().obligations:
        expected = (date.fromisoformat(ob.deadline) - today).days
        assert ob.days_remaining == expected


# ── HIPAA urgency scaling ──────────────────────────────────────────────────────

@pytest.mark.unit
def test_low_hipaa_score_gives_short_deadline():
    p_low = timeline().generate("minimal_risk", 1.0, hipaa_score=0.20)
    hipaa_obs = [o for o in p_low.obligations if o.regulation == "HIPAA"]
    assert any(o.days_remaining <= 90 for o in hipaa_obs)


@pytest.mark.unit
def test_high_hipaa_score_gives_longer_deadline():
    p_high = timeline().generate("minimal_risk", 1.0, hipaa_score=0.80)
    hipaa_obs = [o for o in p_high.obligations if o.regulation == "HIPAA"]
    assert any(o.days_remaining > 90 for o in hipaa_obs)


# ── Aggregate counts ───────────────────────────────────────────────────────────

@pytest.mark.unit
def test_overdue_count_non_negative():
    assert plan().overdue_count >= 0


@pytest.mark.unit
def test_critical_count_non_negative():
    assert plan().critical_count >= 0


@pytest.mark.unit
def test_high_risk_has_more_obligations_than_minimal():
    p_high = plan(tier="high_risk")
    p_min = plan(tier="minimal_risk")
    assert len(p_high.obligations) > len(p_min.obligations)
