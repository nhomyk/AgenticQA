"""Unit tests for WebhookNotifier."""
import json
import os
import urllib.error
from unittest.mock import MagicMock, patch

import pytest

from agenticqa.notifications.webhook import (
    WebhookDeliveryError,
    WebhookNotifier,
    WebhookPayload,
)


# ── Helpers ────────────────────────────────────────────────────────────────────

def _payload(**kwargs) -> WebhookPayload:
    defaults = dict(
        release_readiness_score=82.5,
        recommendation="SHIP IT",
        tests_passed=18,
        tests_total=20,
        owasp_critical_count=0,
        feature_description="Add OAuth2 login",
    )
    defaults.update(kwargs)
    return WebhookPayload(**defaults)


def _mock_response(body: bytes = b'{"ok": true}', status: int = 200):
    resp = MagicMock()
    resp.read.return_value = body
    resp.__enter__ = lambda s: s
    resp.__exit__ = MagicMock(return_value=False)
    return resp


# ── Payload schema ─────────────────────────────────────────────────────────────

@pytest.mark.unit
def test_payload_to_dict_has_required_keys():
    p = _payload()
    d = p.to_dict()
    assert d["event"] == "pipeline_complete"
    assert d["recommendation"] == "SHIP IT"
    assert d["release_readiness_score"] == 82.5
    assert d["tests_passed"] == 18
    assert d["tests_total"] == 20
    assert d["owasp_critical_count"] == 0
    assert "timestamp" in d
    assert "feature_description" in d


@pytest.mark.unit
def test_payload_timestamp_auto_set():
    p = _payload()
    d = p.to_dict()
    assert d["timestamp"]  # non-empty
    assert "T" in d["timestamp"]  # ISO format


@pytest.mark.unit
def test_payload_custom_timestamp_preserved():
    p = _payload(timestamp="2026-01-01T00:00:00+00:00")
    assert p.to_dict()["timestamp"] == "2026-01-01T00:00:00+00:00"


@pytest.mark.unit
def test_payload_do_not_ship():
    p = _payload(recommendation="DO NOT SHIP", release_readiness_score=12.0)
    d = p.to_dict()
    assert d["recommendation"] == "DO NOT SHIP"
    assert d["release_readiness_score"] == 12.0


# ── URL validation ─────────────────────────────────────────────────────────────

@pytest.mark.unit
def test_raises_value_error_when_no_url(monkeypatch):
    monkeypatch.delenv("AGENTICQA_WEBHOOK_URL", raising=False)
    notifier = WebhookNotifier(url="")
    with pytest.raises(ValueError, match="AGENTICQA_WEBHOOK_URL"):
        notifier.notify(_payload())


@pytest.mark.unit
def test_reads_url_from_env(monkeypatch):
    monkeypatch.setenv("AGENTICQA_WEBHOOK_URL", "http://example.com/hook")
    n = WebhookNotifier()
    assert n.url == "http://example.com/hook"


@pytest.mark.unit
def test_explicit_url_overrides_env(monkeypatch):
    monkeypatch.setenv("AGENTICQA_WEBHOOK_URL", "http://wrong.example.com")
    n = WebhookNotifier(url="http://correct.example.com/hook")
    assert n.url == "http://correct.example.com/hook"


# ── Successful delivery ────────────────────────────────────────────────────────

@pytest.mark.unit
def test_successful_post_returns_json(monkeypatch):
    monkeypatch.setenv("AGENTICQA_WEBHOOK_URL", "http://example.com/hook")
    with patch("urllib.request.urlopen") as mock_open:
        mock_open.return_value = _mock_response(b'{"status": "received"}')
        result = WebhookNotifier().notify(_payload())
    assert result == {"status": "received"}


@pytest.mark.unit
def test_post_sends_correct_content_type(monkeypatch):
    monkeypatch.setenv("AGENTICQA_WEBHOOK_URL", "http://example.com/hook")
    captured = {}
    with patch("urllib.request.urlopen") as mock_open:
        mock_open.return_value = _mock_response()

        def capture(req, timeout=None):
            captured["content_type"] = req.get_header("Content-type")
            return _mock_response()

        mock_open.side_effect = capture
        WebhookNotifier().notify(_payload())
    assert captured["content_type"] == "application/json"


@pytest.mark.unit
def test_post_body_is_valid_json(monkeypatch):
    monkeypatch.setenv("AGENTICQA_WEBHOOK_URL", "http://example.com/hook")
    captured_body = {}
    with patch("urllib.request.urlopen") as mock_open:
        def capture(req, timeout=None):
            captured_body["data"] = json.loads(req.data)
            return _mock_response()
        mock_open.side_effect = capture
        WebhookNotifier().notify(_payload())
    assert captured_body["data"]["event"] == "pipeline_complete"
    assert captured_body["data"]["recommendation"] == "SHIP IT"


@pytest.mark.unit
def test_non_json_response_wrapped_in_raw(monkeypatch):
    monkeypatch.setenv("AGENTICQA_WEBHOOK_URL", "http://example.com/hook")
    with patch("urllib.request.urlopen") as mock_open:
        mock_open.return_value = _mock_response(b"OK")
        result = WebhookNotifier().notify(_payload())
    assert result == {"raw": "OK"}


# ── Retry logic ────────────────────────────────────────────────────────────────

@pytest.mark.unit
def test_retries_on_network_error(monkeypatch):
    monkeypatch.setenv("AGENTICQA_WEBHOOK_URL", "http://example.com/hook")
    call_count = {"n": 0}

    def flaky(req, timeout=None):
        call_count["n"] += 1
        if call_count["n"] < 3:
            raise urllib.error.URLError("connection refused")
        return _mock_response()

    with patch("urllib.request.urlopen", side_effect=flaky):
        with patch("time.sleep"):          # don't actually sleep in tests
            result = WebhookNotifier(max_retries=3).notify(_payload())
    assert result == {"ok": True}
    assert call_count["n"] == 3


@pytest.mark.unit
def test_raises_delivery_error_after_all_retries(monkeypatch):
    monkeypatch.setenv("AGENTICQA_WEBHOOK_URL", "http://example.com/hook")
    with patch("urllib.request.urlopen", side_effect=urllib.error.URLError("timeout")):
        with patch("time.sleep"):
            with pytest.raises(WebhookDeliveryError, match="attempt"):
                WebhookNotifier(max_retries=2).notify(_payload())


@pytest.mark.unit
def test_zero_retries_raises_immediately(monkeypatch):
    monkeypatch.setenv("AGENTICQA_WEBHOOK_URL", "http://example.com/hook")
    with patch("urllib.request.urlopen", side_effect=OSError("refused")):
        with pytest.raises(WebhookDeliveryError):
            WebhookNotifier(max_retries=0).notify(_payload())


@pytest.mark.unit
def test_no_sleep_on_first_attempt(monkeypatch):
    """First attempt must not sleep — zero latency on happy path."""
    monkeypatch.setenv("AGENTICQA_WEBHOOK_URL", "http://example.com/hook")
    with patch("urllib.request.urlopen", return_value=_mock_response()):
        with patch("time.sleep") as mock_sleep:
            WebhookNotifier(max_retries=2).notify(_payload())
    mock_sleep.assert_not_called()


@pytest.mark.unit
def test_exponential_backoff_delays(monkeypatch):
    monkeypatch.setenv("AGENTICQA_WEBHOOK_URL", "http://example.com/hook")
    sleeps = []

    def capture_sleep(s):
        sleeps.append(s)

    with patch("urllib.request.urlopen", side_effect=urllib.error.URLError("x")):
        with patch("time.sleep", side_effect=capture_sleep):
            with pytest.raises(WebhookDeliveryError):
                WebhookNotifier(max_retries=3).notify(_payload())
    # 3 retries → sleeps of 1, 2, 4
    assert sleeps == [1, 2, 4]


# ── Edge cases ─────────────────────────────────────────────────────────────────

@pytest.mark.unit
def test_owasp_count_zero_in_payload(monkeypatch):
    monkeypatch.setenv("AGENTICQA_WEBHOOK_URL", "http://example.com/hook")
    with patch("urllib.request.urlopen") as mock_open:
        captured = {}
        def cap(req, timeout=None):
            captured["d"] = json.loads(req.data)
            return _mock_response()
        mock_open.side_effect = cap
        WebhookNotifier().notify(_payload(owasp_critical_count=0))
    assert captured["d"]["owasp_critical_count"] == 0


@pytest.mark.unit
def test_high_owasp_count_do_not_ship(monkeypatch):
    monkeypatch.setenv("AGENTICQA_WEBHOOK_URL", "http://example.com/hook")
    with patch("urllib.request.urlopen") as mock_open:
        captured = {}
        def cap(req, timeout=None):
            captured["d"] = json.loads(req.data)
            return _mock_response()
        mock_open.side_effect = cap
        WebhookNotifier().notify(_payload(
            recommendation="DO NOT SHIP",
            owasp_critical_count=3,
            release_readiness_score=15.0,
        ))
    d = captured["d"]
    assert d["recommendation"] == "DO NOT SHIP"
    assert d["owasp_critical_count"] == 3
