"""Tests for AI output bias and fairness detector."""
import pytest
from agenticqa.security.bias_detector import (
    BiasDetector, BiasReport, BiasFinding, PROTECTED_ATTRIBUTES,
)


@pytest.fixture
def detector():
    return BiasDetector()


@pytest.fixture
def high_sensitivity():
    return BiasDetector(sensitivity="high")


# ── Protected attribute + decision context ──────────────────────────────────

class TestProtectedAttrInDecision:
    @pytest.mark.unit
    def test_gender_in_hiring_decision(self, detector):
        text = "The female candidate was rejected due to insufficient experience."
        report = detector.scan(text)
        assert report.has_bias_risk
        assert "gender" in report.categories_flagged

    @pytest.mark.unit
    def test_age_in_hiring_decision(self, detector):
        text = "The elderly applicant was deemed unqualified for the position."
        report = detector.scan(text)
        assert report.has_bias_risk
        assert "age" in report.categories_flagged

    @pytest.mark.unit
    def test_race_in_scoring(self, detector):
        text = "The hispanic applicant received a lower score than average."
        report = detector.scan(text)
        assert report.has_bias_risk
        assert "race" in report.categories_flagged

    @pytest.mark.unit
    def test_disability_in_decision(self, detector):
        text = "The handicapped employee was not promoted this cycle."
        report = detector.scan(text)
        assert report.has_bias_risk
        assert "disability" in report.categories_flagged

    @pytest.mark.unit
    def test_no_decision_context_no_finding(self, detector):
        text = "The team includes both male and female engineers."
        report = detector.scan(text)
        # Protected attributes present but no decision context
        assert report.protected_attrs_detected.get("gender", 0) > 0
        assert report.decision_contexts_detected == 0
        # Should not produce findings since no decision context
        decision_findings = [f for f in report.findings if f.rule_id == "PROTECTED_ATTR_IN_DECISION"]
        assert len(decision_findings) == 0


# ── Stereotyping detection ──────────────────────────────────────────────────

class TestStereotyping:
    @pytest.mark.unit
    def test_gender_stereotype_women(self, high_sensitivity):
        text = "Women tend to be emotional in leadership roles."
        report = high_sensitivity.scan(text)
        assert any(f.rule_id == "STEREOTYPE" for f in report.findings)

    @pytest.mark.unit
    def test_gender_stereotype_men(self, high_sensitivity):
        text = "Men are aggressive in workplace disputes."
        report = high_sensitivity.scan(text)
        assert any(f.rule_id == "STEREOTYPE" for f in report.findings)

    @pytest.mark.unit
    def test_age_stereotype(self, high_sensitivity):
        text = "Older workers tend to be slow to adopt new technology."
        report = high_sensitivity.scan(text)
        assert any(f.rule_id == "STEREOTYPE" for f in report.findings)

    @pytest.mark.unit
    def test_racial_stereotype(self, high_sensitivity):
        text = "Certain races tend to be more athletic."
        report = high_sensitivity.scan(text)
        assert any(f.rule_id == "STEREOTYPE" for f in report.findings)


# ── Clean text ───────────────────────────────────────────────────────────────

class TestCleanText:
    @pytest.mark.unit
    def test_neutral_text(self, detector):
        text = "Pipeline completed all quality validations with 95% coverage."
        report = detector.scan(text)
        assert not report.has_bias_risk

    @pytest.mark.unit
    def test_empty_text(self, detector):
        report = detector.scan("")
        assert not report.has_bias_risk
        assert report.risk_score == 0.0

    @pytest.mark.unit
    def test_technical_text(self, detector):
        text = "The API endpoint returns a JSON response with status 200."
        report = detector.scan(text)
        assert not report.has_bias_risk


# ── Risk score ───────────────────────────────────────────────────────────────

class TestRiskScore:
    @pytest.mark.unit
    def test_high_severity_produces_higher_score(self, high_sensitivity):
        biased = "The female candidate was rejected for the senior role."
        report = high_sensitivity.scan(biased)
        assert report.risk_score > 0

    @pytest.mark.unit
    def test_score_capped_at_one(self, high_sensitivity):
        # Multiple bias signals
        text = ("The female candidate was rejected. The elderly applicant was denied. "
                "The disabled worker was eliminated. The hispanic person was not selected.")
        report = high_sensitivity.scan(text)
        assert report.risk_score <= 1.0


# ── Sensitivity levels ──────────────────────────────────────────────────────

class TestSensitivity:
    @pytest.mark.unit
    def test_low_sensitivity_filters_weak_signals(self):
        detector = BiasDetector(sensitivity="low")
        # A single mention might not cross the threshold
        text = "The candidate was ranked based on experience."
        report = detector.scan(text)
        # Low sensitivity has higher threshold, so weak signals filtered
        assert report.risk_score == 0.0 or report.risk_score >= 0.3

    @pytest.mark.unit
    def test_high_sensitivity_catches_more(self):
        detector = BiasDetector(sensitivity="high")
        text = "She was promoted to the senior role."
        report = detector.scan(text)
        # High sensitivity has lower threshold
        if report.protected_attrs_detected and report.decision_contexts_detected:
            assert report.has_bias_risk


# ── Dict scanning ────────────────────────────────────────────────────────────

class TestDictScanning:
    @pytest.mark.unit
    def test_scan_dict(self, detector):
        output = {
            "decision": "rejected",
            "reason": "The female applicant lacks qualifications.",
        }
        report = detector.scan_dict(output)
        assert report.has_bias_risk

    @pytest.mark.unit
    def test_scan_nested_dict(self, detector):
        output = {
            "results": [
                {"candidate": "A", "action": "We reject the elderly applicant."},
            ],
        }
        report = detector.scan_dict(output)
        assert report.has_bias_risk

    @pytest.mark.unit
    def test_scan_clean_dict(self, detector):
        output = {"status": "ok", "items": ["test passed", "no issues"]}
        report = detector.scan_dict(output)
        assert not report.has_bias_risk


# ── Report properties ────────────────────────────────────────────────────────

class TestReportProperties:
    @pytest.mark.unit
    def test_categories_flagged(self, high_sensitivity):
        text = "The female candidate and the elderly worker were both rejected."
        report = high_sensitivity.scan(text)
        cats = report.categories_flagged
        assert "gender" in cats or "age" in cats

    @pytest.mark.unit
    def test_total_findings(self, high_sensitivity):
        text = "The female applicant was rejected. The young male was hired."
        report = high_sensitivity.scan(text)
        assert report.total_findings >= 1
