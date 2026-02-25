"""Unit tests for PRCommenter and CIResultBundle."""
import os
from unittest.mock import MagicMock, patch, call

import pytest

from agenticqa.github.pr_commenter import (
    CIResultBundle,
    PRCommenter,
    _COMMENT_MARKER,
)


def _full_bundle() -> CIResultBundle:
    return CIResultBundle(
        run_id="run-12345",
        commit_sha="abc123def456",
        total_tests=100,
        tests_passed=98,
        tests_failed=2,
        coverage_percent=82.5,
        coverage_status="adequate",
        tests_generated=3,
        sre_total_errors=15,
        sre_fix_rate=0.73,
        sre_fixes_applied=11,
        scanner_strength=0.64,
        gate_strength=1.0,
        successful_bypasses=0,
        compliance_violations=0,
        data_encryption=True,
        reachable_cves=1,
        cve_risk_score=0.7,
    )


@pytest.mark.unit
class TestCIResultBundle:
    def test_default_optional_fields_are_none(self):
        bundle = CIResultBundle(run_id="r1", commit_sha="abc123")
        assert bundle.total_tests is None
        assert bundle.scanner_strength is None
        assert bundle.compliance_violations is None


@pytest.mark.unit
class TestFormatComment:
    def test_format_contains_marker(self):
        commenter = PRCommenter(github_token="fake")
        body = commenter._format_comment(_full_bundle())
        assert _COMMENT_MARKER in body

    def test_format_contains_run_id(self):
        commenter = PRCommenter(github_token="fake")
        body = commenter._format_comment(_full_bundle())
        assert "run-12345" in body

    def test_format_contains_commit_sha_prefix(self):
        commenter = PRCommenter(github_token="fake")
        body = commenter._format_comment(_full_bundle())
        # Only first 8 chars of sha
        assert "abc123de" in body
        assert "abc123def456" not in body

    def test_format_full_bundle_has_all_sections(self):
        commenter = PRCommenter(github_token="fake")
        body = commenter._format_comment(_full_bundle())
        assert "### Tests" in body
        assert "### SRE" in body
        assert "### Red Team Security" in body
        assert "### Compliance" in body

    def test_format_partial_bundle_omits_sections(self):
        # Only red team fields — other sections should be absent
        bundle = CIResultBundle(
            run_id="r1",
            commit_sha="abc123",
            scanner_strength=0.64,
            gate_strength=1.0,
            successful_bypasses=0,
        )
        commenter = PRCommenter(github_token="fake")
        body = commenter._format_comment(bundle)
        assert "### Red Team Security" in body
        assert "### Tests" not in body
        assert "### SRE" not in body
        assert "### Compliance" not in body

    def test_format_shows_green_when_no_failures(self):
        bundle = CIResultBundle(
            run_id="r1", commit_sha="abc",
            total_tests=50, tests_passed=50, tests_failed=0,
        )
        commenter = PRCommenter(github_token="fake")
        body = commenter._format_comment(bundle)
        assert ":green_circle:" in body
        assert ":red_circle:" not in body

    def test_format_shows_red_on_failures(self):
        bundle = CIResultBundle(
            run_id="r1", commit_sha="abc",
            total_tests=50, tests_passed=48, tests_failed=2,
        )
        commenter = PRCommenter(github_token="fake")
        body = commenter._format_comment(bundle)
        assert ":red_circle:" in body

    def test_format_shows_cve_risk_score(self):
        bundle = CIResultBundle(
            run_id="r1", commit_sha="abc",
            compliance_violations=1,
            reachable_cves=2,
            cve_risk_score=0.7,
        )
        commenter = PRCommenter(github_token="fake")
        body = commenter._format_comment(bundle)
        assert "0.70" in body
        assert "Reachable CVEs" in body

    def test_format_shows_auto_generated_tests(self):
        bundle = CIResultBundle(
            run_id="r1", commit_sha="abc",
            total_tests=10, tests_passed=10, tests_failed=0,
            tests_generated=3,
        )
        commenter = PRCommenter(github_token="fake")
        body = commenter._format_comment(bundle)
        assert "3" in body
        assert "Auto-Generated" in body


@pytest.mark.unit
class TestDetectPRNumber:
    def test_detect_from_github_ref(self):
        commenter = PRCommenter(github_token="fake")
        with patch.dict(os.environ, {"GITHUB_REF": "refs/pull/42/merge"}):
            result = commenter._detect_pr_number()
        assert result == 42

    def test_detect_from_github_ref_large_number(self):
        commenter = PRCommenter(github_token="fake")
        with patch.dict(os.environ, {"GITHUB_REF": "refs/pull/1234/merge"}):
            result = commenter._detect_pr_number()
        assert result == 1234

    def test_detect_returns_none_no_ref(self):
        commenter = PRCommenter(github_token="fake")
        env = {k: v for k, v in os.environ.items() if k != "GITHUB_REF"}
        env.pop("GITHUB_REF", None)
        mock_proc = MagicMock()
        mock_proc.returncode = 1
        mock_proc.stdout = ""
        with patch.dict(os.environ, {"GITHUB_REF": ""}, clear=False):
            with patch("subprocess.run", return_value=mock_proc):
                result = commenter._detect_pr_number()
        assert result is None

    def test_detect_from_gh_cli_fallback(self):
        commenter = PRCommenter(github_token="fake")
        mock_proc = MagicMock()
        mock_proc.returncode = 0
        mock_proc.stdout = "99\n"
        with patch.dict(os.environ, {"GITHUB_REF": "refs/heads/main"}):
            with patch("subprocess.run", return_value=mock_proc):
                result = commenter._detect_pr_number()
        assert result == 99


@pytest.mark.unit
class TestPostResults:
    def test_post_no_token_returns_false(self):
        commenter = PRCommenter(github_token="")
        # Should return False without calling subprocess
        with patch("subprocess.run") as mock_run:
            result = commenter.post_results(_full_bundle(), pr_number=42)
        assert result is False
        mock_run.assert_not_called()

    def test_post_no_pr_number_returns_false(self):
        commenter = PRCommenter(github_token="ghp_fake")
        # No GITHUB_REF, gh CLI returns non-zero → no PR detected
        mock_proc = MagicMock()
        mock_proc.returncode = 1
        mock_proc.stdout = ""
        with patch.dict(os.environ, {"GITHUB_REF": "refs/heads/main"}):
            with patch("subprocess.run", return_value=mock_proc):
                result = commenter.post_results(_full_bundle())
        assert result is False

    def test_upsert_edit_last_success(self):
        commenter = PRCommenter(github_token="ghp_fake")
        mock_proc = MagicMock()
        mock_proc.returncode = 0
        with patch("subprocess.run", return_value=mock_proc) as mock_run:
            result = commenter._upsert_comment(42, "body text")
        assert result is True
        # Should have called with --edit-last
        first_call_args = mock_run.call_args_list[0][0][0]
        assert "--edit-last" in first_call_args

    def test_upsert_falls_back_to_create(self):
        commenter = PRCommenter(github_token="ghp_fake")
        # First call (edit-last) fails, second call (create) succeeds
        fail_proc = MagicMock()
        fail_proc.returncode = 1
        fail_proc.stderr = "no previous comment"
        success_proc = MagicMock()
        success_proc.returncode = 0
        with patch("subprocess.run", side_effect=[fail_proc, success_proc]) as mock_run:
            result = commenter._upsert_comment(42, "body text")
        assert result is True
        assert mock_run.call_count == 2
        # Second call should NOT have --edit-last
        second_call_args = mock_run.call_args_list[1][0][0]
        assert "--edit-last" not in second_call_args

    def test_upsert_returns_false_on_both_fail(self):
        commenter = PRCommenter(github_token="ghp_fake")
        fail_proc = MagicMock()
        fail_proc.returncode = 1
        fail_proc.stderr = "error"
        with patch("subprocess.run", return_value=fail_proc):
            result = commenter._upsert_comment(42, "body")
        assert result is False

    def test_post_results_calls_upsert_with_pr_number(self):
        commenter = PRCommenter(github_token="ghp_fake")
        with patch.object(commenter, "_upsert_comment", return_value=True) as mock_upsert:
            commenter.post_results(_full_bundle(), pr_number=77)
        mock_upsert.assert_called_once_with(77, mock_upsert.call_args[0][1])
