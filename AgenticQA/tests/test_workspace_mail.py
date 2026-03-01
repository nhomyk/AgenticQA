"""Tests for the safe mail client.

Validates:
  - Config loading from env vars
  - Send blocked without approval
  - Draft composition (safe)
  - MailOpResult structure
"""
import os
import pytest
from unittest.mock import patch, MagicMock

from agenticqa.workspace.mail_client import (
    SafeMailClient,
    MailConfig,
    MailMessage,
    MailOpResult,
)


# ── MailConfig ───────────────────────────────────────────────────────────────


@pytest.mark.unit
def test_config_from_env():
    """MailConfig.from_env() reads environment variables."""
    env = {
        "AGENTICQA_MAIL_IMAP_HOST": "imap.test.com",
        "AGENTICQA_MAIL_IMAP_PORT": "993",
        "AGENTICQA_MAIL_SMTP_HOST": "smtp.test.com",
        "AGENTICQA_MAIL_SMTP_PORT": "587",
        "AGENTICQA_MAIL_USER": "user@test.com",
        "AGENTICQA_MAIL_PASSWORD": "secret123",
    }
    with patch.dict(os.environ, env):
        cfg = MailConfig.from_env()
    assert cfg.imap_host == "imap.test.com"
    assert cfg.smtp_host == "smtp.test.com"
    assert cfg.user == "user@test.com"
    assert cfg.is_configured


@pytest.mark.unit
def test_config_not_configured_by_default():
    """MailConfig is not configured when env vars are empty."""
    env = {
        "AGENTICQA_MAIL_IMAP_HOST": "",
        "AGENTICQA_MAIL_USER": "",
        "AGENTICQA_MAIL_PASSWORD": "",
    }
    with patch.dict(os.environ, env, clear=False):
        cfg = MailConfig.from_env()
    assert not cfg.is_configured


@pytest.mark.unit
def test_config_is_configured_property():
    """is_configured requires host + user + password."""
    cfg = MailConfig(imap_host="imap.test.com", user="u", password="p")
    assert cfg.is_configured
    cfg2 = MailConfig(imap_host="imap.test.com", user="u", password="")
    assert not cfg2.is_configured


# ── Send gate ────────────────────────────────────────────────────────────────


@pytest.mark.unit
def test_send_blocked_without_approval():
    """Sending is blocked unless approved=True."""
    client = SafeMailClient(config=MailConfig(
        imap_host="imap.test.com",
        smtp_host="smtp.test.com",
        user="user@test.com",
        password="secret",
    ))
    result = client.send_message("to@test.com", "Test", "Body")
    assert not result.success
    assert result.requires_approval
    assert "IRREVERSIBLE" in result.error


@pytest.mark.unit
def test_send_with_approval_no_smtp():
    """With approval but no SMTP configured, send fails gracefully."""
    client = SafeMailClient(config=MailConfig(
        imap_host="imap.test.com",
        smtp_host="",
        user="user@test.com",
        password="secret",
    ))
    result = client.send_message("to@test.com", "Test", "Body", approved=True)
    assert not result.success
    assert "SMTP not configured" in result.error


# ── Draft composition ────────────────────────────────────────────────────────


@pytest.mark.unit
def test_compose_draft():
    """compose_draft builds a draft dict without sending."""
    client = SafeMailClient(config=MailConfig(
        user="me@test.com", imap_host="x", password="x",
    ))
    draft = client.compose_draft("to@test.com", "Hello", "Hi there")
    assert draft["from"] == "me@test.com"
    assert draft["to"] == "to@test.com"
    assert draft["subject"] == "Hello"
    assert draft["body"] == "Hi there"
    assert "timestamp" in draft


# ── Read operations (without real IMAP) ──────────────────────────────────────


@pytest.mark.unit
def test_list_folders_not_configured():
    """list_folders fails gracefully when not configured."""
    client = SafeMailClient(config=MailConfig())
    result = client.list_folders()
    assert not result.success
    assert "not configured" in result.error.lower()


@pytest.mark.unit
def test_list_messages_not_configured():
    """list_messages fails gracefully when not configured."""
    client = SafeMailClient(config=MailConfig())
    result = client.list_messages()
    assert not result.success
    assert "not configured" in result.error.lower()


@pytest.mark.unit
def test_read_message_not_configured():
    """read_message fails gracefully when not configured."""
    client = SafeMailClient(config=MailConfig())
    result = client.read_message("1")
    assert not result.success
    assert "not configured" in result.error.lower()


# ── MailMessage dataclass ────────────────────────────────────────────────────


@pytest.mark.unit
def test_mail_message_defaults():
    """MailMessage has sensible defaults."""
    msg = MailMessage()
    assert msg.uid == ""
    assert msg.subject == ""
    assert msg.folder == "INBOX"
    assert not msg.has_attachments


@pytest.mark.unit
def test_mail_message_fields():
    """MailMessage stores all fields."""
    msg = MailMessage(
        uid="42", subject="Test", sender="from@test.com",
        to="to@test.com", date="2026-01-01",
        body_plain="Hello", body_html="<p>Hello</p>",
        has_attachments=True, folder="Sent",
    )
    assert msg.uid == "42"
    assert msg.subject == "Test"
    assert msg.has_attachments
    assert msg.folder == "Sent"


# ── MailOpResult dataclass ───────────────────────────────────────────────────


@pytest.mark.unit
def test_mail_op_result_success():
    """MailOpResult success case."""
    r = MailOpResult(success=True, action="read", data={"uid": "1"})
    assert r.success
    assert r.action == "read"
    assert r.data == {"uid": "1"}
    assert r.error is None
    assert not r.requires_approval


@pytest.mark.unit
def test_mail_op_result_failure():
    """MailOpResult failure case."""
    r = MailOpResult(success=False, action="send", error="blocked",
                     requires_approval=True)
    assert not r.success
    assert r.requires_approval


@pytest.mark.unit
def test_close_idempotent():
    """close() can be called multiple times safely."""
    client = SafeMailClient(config=MailConfig())
    client.close()
    client.close()  # should not raise
