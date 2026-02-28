"""Unit tests for SecretsHistoryScanner — @pytest.mark.unit

NOTE: Secret pattern test fixtures are constructed programmatically
to avoid triggering GitHub push protection on static strings.
"""
import pytest
from pathlib import Path

from agenticqa.security.secrets_scanner import (
    SecretFinding,
    SecretsHistoryScanResult,
    SecretsHistoryScanner,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_scanner() -> SecretsHistoryScanner:
    return SecretsHistoryScanner()


def write(path: Path, content: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return path


def _aws_key() -> str:
    """Construct an AWS-key-shaped fixture string at runtime."""
    return "AKIA" + "I" * 16  # AKIA + 16 uppercase alphanum


def _github_token() -> str:
    """Construct a GitHub token-shaped fixture string at runtime."""
    return "ghp_" + "a" * 36  # ghp_ + 36 alphanum


def _stripe_live_key() -> str:
    """Construct a Stripe live key-shaped fixture at runtime."""
    prefix = "sk_" + "live" + "_"  # split to avoid static detection
    return prefix + "A" * 24


def _stripe_pub_key() -> str:
    """Construct a Stripe publishable key fixture at runtime."""
    prefix = "pk_" + "test" + "_"
    return prefix + "A" * 24


def _slack_token() -> str:
    """Construct a Slack token-shaped fixture at runtime."""
    # xoxb-<12digits>-<12digits>-<24alphanum>
    part = "xox" + "b"
    return f"{part}-{'1' * 12}-{'2' * 12}-{'a' * 24}"


def _sendgrid_key() -> str:
    """Construct a SendGrid key-shaped fixture at runtime."""
    return "SG." + "a" * 22 + "." + "b" * 43


# ---------------------------------------------------------------------------
# scan_content tests (no git required)
# ---------------------------------------------------------------------------

@pytest.mark.unit
class TestScanContent:

    def test_aws_access_key_detected(self):
        key = _aws_key()
        findings = make_scanner().scan_content(key + "\n", "config.py")
        types = [f.secret_type for f in findings]
        assert "AWS_ACCESS_KEY" in types

    def test_github_token_detected(self):
        token = _github_token()
        content = f"token = '{token}'\n"
        findings = make_scanner().scan_content(content, "config.py")
        types = [f.secret_type for f in findings]
        assert "GITHUB_TOKEN" in types

    def test_stripe_key_detected(self):
        key = _stripe_live_key()
        content = f"STRIPE_SK = '{key}'\n"
        findings = make_scanner().scan_content(content, "stripe.py")
        types = [f.secret_type for f in findings]
        assert "STRIPE_KEY" in types

    def test_stripe_publishable_detected(self):
        key = _stripe_pub_key()
        content = f"pk = '{key}'\n"
        findings = make_scanner().scan_content(content, "stripe.py")
        types = [f.secret_type for f in findings]
        assert "STRIPE_PUBLISHABLE" in types

    def test_pem_key_detected(self):
        content = "-----BEGIN RSA PRIVATE KEY-----\nMIIEo...\n"
        findings = make_scanner().scan_content(content, "key.pem")
        types = [f.secret_type for f in findings]
        assert "PRIVATE_KEY_PEM" in types

    def test_generic_api_key_detected(self):
        content = "api_key = 'abcdefghijklmnopqrstuvwxyz123456'\n"
        findings = make_scanner().scan_content(content, "settings.py")
        types = [f.secret_type for f in findings]
        assert "GENERIC_API_KEY" in types

    def test_generic_secret_password_detected(self):
        content = 'password = "mysupersecretpassword123"\n'
        findings = make_scanner().scan_content(content, "settings.py")
        types = [f.secret_type for f in findings]
        assert "GENERIC_SECRET" in types

    def test_bearer_token_detected(self):
        content = "Authorization: Bearer eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9abc\n"
        findings = make_scanner().scan_content(content, "req.py")
        types = [f.secret_type for f in findings]
        assert "BEARER_TOKEN" in types

    def test_basic_auth_url_detected(self):
        content = "url = 'https://admin:password123@example.com/api'\n"
        findings = make_scanner().scan_content(content, "client.py")
        types = [f.secret_type for f in findings]
        assert "BASIC_AUTH_URL" in types

    def test_sendgrid_key_detected(self):
        key = _sendgrid_key()
        content = f"SENDGRID_KEY = '{key}'\n"
        findings = make_scanner().scan_content(content, "mail.py")
        types = [f.secret_type for f in findings]
        assert "SENDGRID_KEY" in types

    def test_slack_token_detected(self):
        token = _slack_token()
        content = f"SLACK_BOT_TOKEN = '{token}'\n"
        findings = make_scanner().scan_content(content, "slack.py")
        types = [f.secret_type for f in findings]
        assert "SLACK_TOKEN" in types

    def test_clean_content_no_findings(self):
        content = "def hello():\n    return 'world'\n"
        findings = make_scanner().scan_content(content, "clean.py")
        assert findings == []

    def test_redaction_format(self):
        key = _aws_key()
        findings = make_scanner().scan_content(key + "\n", "key.py")
        assert len(findings) > 0
        ev = findings[0].evidence
        assert "****" in ev
        # Should not contain raw key in full
        assert len(ev) < len(key)

    def test_evidence_is_redacted_not_raw(self):
        token = _github_token()
        content = f"token = '{token}'\n"
        findings = make_scanner().scan_content(content, "t.py")
        assert len(findings) > 0
        assert findings[0].evidence != token

    def test_to_dict_fields(self):
        key = _aws_key()
        findings = make_scanner().scan_content(key + "\n", "key.py")
        assert len(findings) > 0
        d = findings[0].to_dict()
        assert "secret_type" in d
        assert "commit_hash" in d
        assert "file_path" in d
        assert "line_number" in d
        assert "evidence" in d
        assert "severity" in d
        assert "still_present" in d

    def test_still_present_defaults_false(self):
        key = _aws_key()
        findings = make_scanner().scan_content(key + "\n", "key.py")
        # scan_content alone doesn't set still_present=True (caller does)
        assert findings[0].still_present is False

    def test_scan_content_standalone_no_git(self):
        # Ensure scan_content works without any git repo
        content = "secret = 'MyV3ryL0ngS3cr3tV@lue'\n"
        findings = make_scanner().scan_content(content, "app.py", commit_hash="abc123")
        assert findings[0].commit_hash == "abc123"


# ---------------------------------------------------------------------------
# scan() tests with tmp_path
# ---------------------------------------------------------------------------

@pytest.mark.unit
class TestScanDirectory:

    def test_risk_score_zero_on_clean(self, tmp_path):
        write(tmp_path / "app.py", "def hello():\n    return 1\n")
        result = make_scanner().scan(str(tmp_path), scan_history=False)
        assert result.risk_score == 0.0

    def test_unique_secret_types_populated(self, tmp_path):
        key = _aws_key()
        write(tmp_path / "config.py", key + "\n")
        result = make_scanner().scan(str(tmp_path), scan_history=False)
        assert len(result.unique_secret_types) > 0
        assert "AWS_ACCESS_KEY" in result.unique_secret_types

    def test_has_live_secrets_flag(self, tmp_path):
        key = _aws_key()
        write(tmp_path / "app.py", key + "\n")
        result = make_scanner().scan(str(tmp_path), scan_history=False)
        assert result.has_live_secrets is True

    def test_commits_scanned_reported(self, tmp_path):
        write(tmp_path / "clean.py", "x = 1\n")
        result = make_scanner().scan(str(tmp_path), scan_history=False)
        # When history is disabled, should be 0
        assert result.commits_scanned == 0

    def test_result_to_dict_fields(self, tmp_path):
        write(tmp_path / "app.py", "x = 1\n")
        result = make_scanner().scan(str(tmp_path), scan_history=False)
        d = result.to_dict()
        assert "repo_path" in d
        assert "findings" in d
        assert "commits_scanned" in d
        assert "files_scanned" in d
        assert "unique_secret_types" in d
        assert "has_live_secrets" in d
        assert "risk_score" in d


# ---------------------------------------------------------------------------
# Redaction helper
# ---------------------------------------------------------------------------

@pytest.mark.unit
class TestRedaction:

    def test_redact_long_value(self):
        r = SecretsHistoryScanner()._redact("AKIAIOSFODNN7EXAMPLE")
        assert r == "AKIA****MPLE"

    def test_redact_short_value(self):
        r = SecretsHistoryScanner()._redact("abc")
        assert r == "****"

    def test_redact_exactly_8_chars(self):
        r = SecretsHistoryScanner()._redact("abcdefgh")
        assert r == "abcd****efgh"
