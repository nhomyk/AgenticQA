"""Tests for PII auto-redaction module."""
import pytest
from agenticqa.security.pii_redactor import PIIRedactor, RedactionReport


@pytest.fixture
def redactor():
    return PIIRedactor()


# ── Email ────────────────────────────────────────────────────────────────────

class TestEmailRedaction:
    @pytest.mark.unit
    def test_simple_email(self, redactor):
        text = "Contact user@example.com for details"
        result, events = redactor.redact_text(text)
        assert "[REDACTED_EMAIL]" in result
        assert "user@example.com" not in result
        assert len(events) == 1
        assert events[0].pii_type == "EMAIL"

    @pytest.mark.unit
    def test_multiple_emails(self, redactor):
        text = "Send to alice@corp.io and bob@test.org"
        result, events = redactor.redact_text(text)
        assert result.count("[REDACTED_EMAIL]") == 2

    @pytest.mark.unit
    def test_no_false_positive_at_sign(self, redactor):
        text = "Use the @ symbol in Python decorators"
        result, events = redactor.redact_text(text)
        assert "[REDACTED_EMAIL]" not in result


# ── Phone ────────────────────────────────────────────────────────────────────

class TestPhoneRedaction:
    @pytest.mark.unit
    def test_us_phone_dashes(self, redactor):
        result, events = redactor.redact_text("Call 555-123-4567")
        assert "[REDACTED_PHONE]" in result

    @pytest.mark.unit
    def test_us_phone_parens(self, redactor):
        result, events = redactor.redact_text("Call (555) 123-4567")
        assert "[REDACTED_PHONE]" in result

    @pytest.mark.unit
    def test_us_phone_with_country_code(self, redactor):
        result, events = redactor.redact_text("Call +1-555-123-4567")
        assert "[REDACTED_PHONE]" in result


# ── SSN ──────────────────────────────────────────────────────────────────────

class TestSSNRedaction:
    @pytest.mark.unit
    def test_ssn(self, redactor):
        result, events = redactor.redact_text("SSN: 123-45-6789")
        assert "[REDACTED_SSN]" in result
        assert "123-45-6789" not in result

    @pytest.mark.unit
    def test_not_date(self, redactor):
        # Dates like 2026-03-01 should NOT match SSN pattern
        result, events = redactor.redact_text("Date: 2026-03-01")
        assert "[REDACTED_SSN]" not in result


# ── Credit Card ──────────────────────────────────────────────────────────────

class TestCreditCardRedaction:
    @pytest.mark.unit
    def test_visa(self, redactor):
        result, events = redactor.redact_text("Card: 4111111111111111")
        assert "[REDACTED_CC]" in result

    @pytest.mark.unit
    def test_mastercard_with_spaces(self, redactor):
        result, events = redactor.redact_text("Card: 5500 0000 0000 0004")
        assert "[REDACTED_CC]" in result

    @pytest.mark.unit
    def test_amex(self, redactor):
        result, events = redactor.redact_text("Card: 378282246310005")
        assert "[REDACTED_CC]" in result


# ── IP Address ───────────────────────────────────────────────────────────────

class TestIPRedaction:
    @pytest.mark.unit
    def test_ipv4(self, redactor):
        result, events = redactor.redact_text("Server at 192.168.1.100")
        assert "[REDACTED_IP]" in result

    @pytest.mark.unit
    def test_ipv4_public(self, redactor):
        result, events = redactor.redact_text("DNS: 8.8.8.8")
        assert "[REDACTED_IP]" in result


# ── AWS / API Keys ───────────────────────────────────────────────────────────

class TestKeyRedaction:
    @pytest.mark.unit
    def test_aws_key(self, redactor):
        result, events = redactor.redact_text("key: AKIAIOSFODNN7EXAMPLE")
        assert "[REDACTED_AWS_KEY]" in result

    @pytest.mark.unit
    def test_openai_api_key(self, redactor):
        result, events = redactor.redact_text("sk-abc123def456ghi789jkl012mno345")
        assert "[REDACTED_API_KEY]" in result

    @pytest.mark.unit
    def test_anthropic_api_key(self, redactor):
        result, events = redactor.redact_text("key: sk-ant-api03-abcdef1234567890abcdef")
        assert "[REDACTED_API_KEY]" in result

    @pytest.mark.unit
    def test_bearer_token(self, redactor):
        result, events = redactor.redact_text("Authorization: Bearer eyJhbGciOiJIUzI1NiJ9.payload.sig")
        assert "[REDACTED_BEARER]" in result


# ── DOB / Address ────────────────────────────────────────────────────────────

class TestDOBAndAddress:
    @pytest.mark.unit
    def test_dob(self, redactor):
        result, events = redactor.redact_text("Date of Birth: 01/15/1990")
        assert "[REDACTED_DOB]" in result

    @pytest.mark.unit
    def test_us_address(self, redactor):
        result, events = redactor.redact_text("Lives at 123 Main Street")
        assert "[REDACTED_ADDRESS]" in result


# ── Recursive dict/list redaction ────────────────────────────────────────────

class TestRecursiveRedaction:
    @pytest.mark.unit
    def test_dict_redaction(self, redactor):
        data = {"email": "test@example.com", "name": "Alice"}
        report = redactor.redact(data)
        assert not report.clean
        assert report.redaction_count >= 1
        assert "[REDACTED_EMAIL]" in report.redacted_output["email"]

    @pytest.mark.unit
    def test_nested_dict(self, redactor):
        data = {"user": {"contact": {"phone": "555-123-4567"}}}
        report = redactor.redact(data)
        assert "[REDACTED_PHONE]" in report.redacted_output["user"]["contact"]["phone"]

    @pytest.mark.unit
    def test_list_redaction(self, redactor):
        data = ["user@test.com", "no pii here", "555-123-4567"]
        report = redactor.redact(data)
        assert "[REDACTED_EMAIL]" in report.redacted_output[0]
        assert "[REDACTED_PHONE]" in report.redacted_output[2]
        assert report.redacted_output[1] == "no pii here"

    @pytest.mark.unit
    def test_clean_data(self, redactor):
        data = {"status": "ok", "count": 42}
        report = redactor.redact(data)
        assert report.clean
        assert report.redaction_count == 0

    @pytest.mark.unit
    def test_non_string_values_unchanged(self, redactor):
        data = {"count": 42, "active": True, "ratio": 3.14}
        report = redactor.redact(data)
        assert report.redacted_output["count"] == 42
        assert report.redacted_output["active"] is True

    @pytest.mark.unit
    def test_field_path_tracking(self, redactor):
        data = {"user": {"email": "test@example.com"}}
        report = redactor.redact(data)
        assert any(e.field_path == "user.email" for e in report.events)


# ── Scan-only mode ───────────────────────────────────────────────────────────

class TestScanOnly:
    @pytest.mark.unit
    def test_scan_only_detects_but_doesnt_modify(self, redactor):
        data = {"email": "test@example.com"}
        report = redactor.scan_only(data)
        assert not report.clean
        assert report.redaction_count >= 1
        # Original should be unchanged
        assert report.redacted_output["email"] == "test@example.com"


# ── Custom patterns ──────────────────────────────────────────────────────────

class TestCustomPatterns:
    @pytest.mark.unit
    def test_extra_pattern(self):
        import re
        custom = [("CUSTOM_ID", re.compile(r"CUST-\d{6}"), "[REDACTED_CUST]")]
        redactor = PIIRedactor(extra_patterns=custom)
        result, events = redactor.redact_text("Customer CUST-123456 record")
        assert "[REDACTED_CUST]" in result
