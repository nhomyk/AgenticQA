"""Unit tests for PRCommenter.post_inline_comments."""
import json
from unittest.mock import MagicMock, patch
import urllib.error

import pytest

from agenticqa.github.pr_commenter import PRCommenter


@pytest.mark.unit
class TestPostInlineComments:
    def test_no_token_returns_zero(self):
        commenter = PRCommenter(github_token="")
        result = commenter.post_inline_comments(42, [{"path": "a.py", "line": 1, "body": "x"}])
        assert result == 0

    def test_no_repo_returns_zero(self, monkeypatch):
        monkeypatch.delenv("GITHUB_REPOSITORY", raising=False)
        monkeypatch.setenv("GITHUB_SHA", "abc123")
        commenter = PRCommenter(github_token="ghp_fake", repo="")
        result = commenter.post_inline_comments(42, [{"path": "a.py", "line": 1, "body": "x"}])
        assert result == 0

    def test_no_sha_returns_zero(self, monkeypatch):
        monkeypatch.delenv("GITHUB_SHA", raising=False)
        commenter = PRCommenter(github_token="ghp_fake", repo="org/repo")
        result = commenter.post_inline_comments(42, [{"path": "a.py", "line": 1, "body": "x"}])
        assert result == 0

    def test_skips_incomplete_findings(self, monkeypatch):
        monkeypatch.setenv("GITHUB_SHA", "abc123")
        commenter = PRCommenter(github_token="ghp_fake", repo="org/repo")
        # finding missing 'line'
        with patch("urllib.request.urlopen") as mock_open:
            result = commenter.post_inline_comments(42, [{"path": "a.py", "body": "x"}])
        assert result == 0
        mock_open.assert_not_called()

    def test_posts_valid_finding(self, monkeypatch):
        monkeypatch.setenv("GITHUB_SHA", "deadbeef")
        commenter = PRCommenter(github_token="ghp_fake", repo="org/repo")
        mock_resp = MagicMock()
        mock_resp.__enter__ = lambda s: s
        mock_resp.__exit__ = MagicMock(return_value=False)
        with patch("urllib.request.urlopen", return_value=mock_resp):
            result = commenter.post_inline_comments(
                42,
                [{"path": "src/app.py", "line": 10, "body": "CVE-2024-1234 in dependency"}],
                commit_sha="deadbeef",
            )
        assert result == 1

    def test_422_skipped_silently(self, monkeypatch):
        monkeypatch.setenv("GITHUB_SHA", "deadbeef")
        commenter = PRCommenter(github_token="ghp_fake", repo="org/repo")
        err = urllib.error.HTTPError(url="", code=422, msg="Unprocessable", hdrs=None, fp=None)
        with patch("urllib.request.urlopen", side_effect=err):
            result = commenter.post_inline_comments(
                42, [{"path": "f.py", "line": 5, "body": "note"}], commit_sha="abc"
            )
        assert result == 0  # skipped, not raised

    def test_severity_icons(self, monkeypatch):
        monkeypatch.setenv("GITHUB_SHA", "deadbeef")
        commenter = PRCommenter(github_token="ghp_fake", repo="org/repo")
        captured = []

        def fake_open(req, timeout):
            captured.append(json.loads(req.data.decode()))
            m = MagicMock()
            m.__enter__ = lambda s: s
            m.__exit__ = MagicMock(return_value=False)
            return m

        with patch("urllib.request.urlopen", side_effect=fake_open):
            commenter.post_inline_comments(
                1,
                [
                    {"path": "a.py", "line": 1, "body": "err", "severity": "error"},
                    {"path": "b.py", "line": 2, "body": "warn", "severity": "warning"},
                    {"path": "c.py", "line": 3, "body": "info", "severity": "info"},
                ],
                commit_sha="deadbeef",
            )
        assert "🔴" in captured[0]["body"]
        assert "🟡" in captured[1]["body"]
        assert "🔵" in captured[2]["body"]

    def test_multiple_findings_all_posted(self, monkeypatch):
        monkeypatch.setenv("GITHUB_SHA", "abc")
        commenter = PRCommenter(github_token="ghp_fake", repo="org/repo")
        mock_resp = MagicMock()
        mock_resp.__enter__ = lambda s: s
        mock_resp.__exit__ = MagicMock(return_value=False)
        findings = [{"path": f"f{i}.py", "line": i+1, "body": "x"} for i in range(5)]
        with patch("urllib.request.urlopen", return_value=mock_resp):
            result = commenter.post_inline_comments(7, findings, commit_sha="abc")
        assert result == 5
