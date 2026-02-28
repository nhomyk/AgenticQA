"""Unit tests for post_pr_risk_comment helpers."""
import json
import sys
import urllib.error
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from post_pr_risk_comment import (
    _format_comment,
    _post_github_comment,
    _validate_ref,
)
from agenticqa.scoring.pr_risk_scorer import PRRiskReport


# ── Helpers ────────────────────────────────────────────────────────────────────

def _report(**kwargs) -> PRRiskReport:
    defaults = dict(
        author_email="dev@example.com",
        risk_score=42.0,
        recommendation="MEDIUM RISK",
        predicted_violations=["SENSITIVE_FILE_TOUCHED"],
        reasoning=["Author fix rate is moderate (45%)."],
        author_fix_rate=0.45,
        unfixable_rules_hit=[],
        trend="stable",
    )
    defaults.update(kwargs)
    return PRRiskReport(**defaults)


def _mock_response(status: int = 201, body: bytes = b'{"id":1}'):
    resp = MagicMock()
    resp.status = status
    resp.read.return_value = body
    resp.__enter__ = lambda s: s
    resp.__exit__ = MagicMock(return_value=False)
    return resp


# ── _validate_ref ──────────────────────────────────────────────────────────────

@pytest.mark.unit
def test_valid_ref_passes():
    assert _validate_ref("origin/main") == "origin/main"
    assert _validate_ref("HEAD~1") == "HEAD~1"
    assert _validate_ref("refs/heads/feature-branch") == "refs/heads/feature-branch"


@pytest.mark.unit
def test_ref_with_shell_chars_rejected():
    with pytest.raises(ValueError, match="Unsafe"):
        _validate_ref("origin/main; rm -rf /")


@pytest.mark.unit
def test_ref_with_backtick_rejected():
    with pytest.raises(ValueError, match="Unsafe"):
        _validate_ref("`whoami`")


@pytest.mark.unit
def test_ref_with_dollar_rejected():
    with pytest.raises(ValueError, match="Unsafe"):
        _validate_ref("$HOME")


# ── _format_comment ────────────────────────────────────────────────────────────

@pytest.mark.unit
def test_low_risk_gets_green_icon():
    r = _report(risk_score=10, recommendation="LOW RISK")
    assert "🟢" in _format_comment(r)


@pytest.mark.unit
def test_medium_risk_gets_yellow_icon():
    r = _report(risk_score=42, recommendation="MEDIUM RISK")
    assert "🟡" in _format_comment(r)


@pytest.mark.unit
def test_high_risk_gets_red_icon():
    r = _report(risk_score=80, recommendation="HIGH RISK")
    assert "🔴" in _format_comment(r)


@pytest.mark.unit
def test_comment_contains_score():
    r = _report(risk_score=55.0)
    assert "55" in _format_comment(r)


@pytest.mark.unit
def test_comment_contains_violations():
    r = _report(predicted_violations=["DANGEROUS_DIFF_PATTERN", "SENSITIVE_FILE_TOUCHED"])
    comment = _format_comment(r)
    assert "DANGEROUS_DIFF_PATTERN" in comment
    assert "SENSITIVE_FILE_TOUCHED" in comment


@pytest.mark.unit
def test_comment_contains_reasoning():
    r = _report(reasoning=["Author fix rate is low (10%)."])
    assert "Author fix rate is low" in _format_comment(r)


@pytest.mark.unit
def test_comment_contains_fix_rate():
    r = _report(author_fix_rate=0.78)
    assert "78%" in _format_comment(r)


@pytest.mark.unit
def test_comment_no_history_when_fix_rate_none():
    r = _report(author_fix_rate=None)
    assert "No history" in _format_comment(r)


@pytest.mark.unit
def test_comment_contains_agenticqa_attribution():
    assert "AgenticQA" in _format_comment(_report())


# ── _post_github_comment ───────────────────────────────────────────────────────

@pytest.mark.unit
def test_post_returns_true_on_201():
    with patch("urllib.request.urlopen") as mock_open:
        mock_open.return_value = _mock_response(status=201)
        result = _post_github_comment("owner/repo", "42", "body", "token123")
    assert result is True


@pytest.mark.unit
def test_post_returns_true_on_200():
    with patch("urllib.request.urlopen") as mock_open:
        mock_open.return_value = _mock_response(status=200)
        result = _post_github_comment("owner/repo", "42", "body", "token123")
    assert result is True


@pytest.mark.unit
def test_post_returns_false_on_network_error():
    with patch("urllib.request.urlopen", side_effect=urllib.error.URLError("refused")):
        result = _post_github_comment("owner/repo", "42", "body", "token123")
    assert result is False


@pytest.mark.unit
def test_post_sends_bearer_token():
    captured = {}
    def capture(req, timeout=None):
        captured["auth"] = req.get_header("Authorization")
        return _mock_response()
    with patch("urllib.request.urlopen", side_effect=capture):
        _post_github_comment("owner/repo", "42", "body", "mytoken")
    assert captured["auth"] == "Bearer mytoken"


@pytest.mark.unit
def test_post_sends_json_body():
    captured = {}
    def capture(req, timeout=None):
        captured["body"] = json.loads(req.data)
        return _mock_response()
    with patch("urllib.request.urlopen", side_effect=capture):
        _post_github_comment("owner/repo", "42", "hello world", "tok")
    assert captured["body"]["body"] == "hello world"


@pytest.mark.unit
def test_post_targets_correct_url():
    captured = {}
    def capture(req, timeout=None):
        captured["url"] = req.full_url
        return _mock_response()
    with patch("urllib.request.urlopen", side_effect=capture):
        _post_github_comment("myorg/myrepo", "99", "body", "tok")
    assert "myorg/myrepo" in captured["url"]
    assert "/issues/99/comments" in captured["url"]
