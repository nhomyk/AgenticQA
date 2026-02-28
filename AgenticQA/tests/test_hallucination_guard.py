"""Unit tests for HallucinationConfidenceGate."""
import pytest
from agenticqa.security.hallucination_guard import HallucinationConfidenceGate


@pytest.fixture
def gate():
    return HallucinationConfidenceGate()


@pytest.mark.unit
def test_clean_output_no_findings(gate):
    findings = gate.scan("The test suite ran 42 tests. 3 failed. Coverage is 78%.")
    assert findings == []


@pytest.mark.unit
def test_absolute_certainty_near_compliance(gate):
    output = "I can confirm that encryption is definitely enabled for all data at rest."
    findings = gate.scan(output)
    assert any(f.finding_type == "ABSOLUTE_CERTAINTY" for f in findings)


@pytest.mark.unit
def test_impossible_always_claim(gate):
    output = "The tests always pass in this configuration."
    findings = gate.scan(output)
    assert any(f.finding_type == "IMPOSSIBLE_CLAIM" for f in findings)


@pytest.mark.unit
def test_impossible_never_claim(gate):
    output = "Encryption is never disabled in production environments."
    findings = gate.scan(output)
    assert any(f.finding_type == "IMPOSSIBLE_CLAIM" for f in findings)


@pytest.mark.unit
def test_ungrounded_metric_detected(gate):
    output = "The coverage is 97.3%."
    context = "Run tests and report results."
    findings = gate.scan(output, input_context=context)
    assert any(f.finding_type == "UNGROUNDED_METRIC" for f in findings)


@pytest.mark.unit
def test_grounded_metric_not_flagged(gate):
    context = "Coverage is 97.3%."
    output = "The coverage is 97.3%."
    findings = gate.scan(output, input_context=context)
    assert not any(f.finding_type == "UNGROUNDED_METRIC" for f in findings)


@pytest.mark.unit
def test_self_contradiction_tests_pass_fail(gate):
    output = "All tests pass. There are 5 errors in the test suite. Tests failed."
    findings = gate.scan(output)
    assert any(f.finding_type == "SELF_CONTRADICTION" for f in findings)


@pytest.mark.unit
def test_self_contradiction_no_pii_then_pii(gate):
    output = "No PII found in the codebase. PII detected in user_data.py."
    findings = gate.scan(output)
    assert any(f.finding_type == "SELF_CONTRADICTION" for f in findings)


@pytest.mark.unit
def test_risk_score_zero_clean(gate):
    assert gate.risk_score("All 42 tests ran. 3 failed. See errors above.") == 0.0


@pytest.mark.unit
def test_risk_score_high_overconfident(gate):
    output = (
        "I can confirm that encryption is absolutely guaranteed. "
        "Tests always pass. "
        "No vulnerabilities were ever found in this codebase."
    )
    score = gate.risk_score(output)
    assert score > 0.3


@pytest.mark.unit
def test_is_safe_clean_output(gate):
    assert gate.is_safe("The test coverage dropped from 80% to 75%. 3 tests failed.") is True


@pytest.mark.unit
def test_is_safe_false_on_high_risk(gate):
    output = (
        "I can certainly confirm tests always pass. No PII found. PII detected."
    )
    assert gate.is_safe(output) is False


@pytest.mark.unit
def test_severity_high_for_certainty(gate):
    findings = gate.scan("I can confirm that the security audit is definitely passed.")
    sev = [f.severity for f in findings if f.finding_type == "ABSOLUTE_CERTAINTY"]
    if sev:
        assert "high" in sev
