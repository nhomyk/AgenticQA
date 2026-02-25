"""Unit tests for DeveloperProfile and DeveloperRiskLeaderboard."""
import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from data_store.developer_profile import (
    DeveloperProfile,
    DeveloperRiskLeaderboard,
    _hash_email,
    _get_primary_author,
)


@pytest.mark.unit
class TestHashEmail:
    def test_hash_email_consistent(self):
        h1 = _hash_email("alice@example.com")
        h2 = _hash_email("alice@example.com")
        assert h1 == h2

    def test_hash_email_case_insensitive(self):
        assert _hash_email("Alice@Example.com") == _hash_email("alice@example.com")

    def test_hash_email_12_chars(self):
        h = _hash_email("dev@corp.io")
        assert len(h) == 12

    def test_different_emails_different_hashes(self):
        assert _hash_email("alice@example.com") != _hash_email("bob@example.com")


@pytest.mark.unit
class TestGetPrimaryAuthor:
    def test_returns_none_on_nonzero_returncode(self):
        mock_proc = MagicMock()
        mock_proc.returncode = 128
        mock_proc.stdout = ""
        with patch("subprocess.run", return_value=mock_proc):
            result = _get_primary_author("nonexistent.py")
        assert result is None

    def test_returns_most_frequent_author(self):
        # alice owns 2 lines, bob owns 1
        blame_output = (
            "abc123 1 1 2\nauthor Alice\nauthor-mail <alice@example.com>\n"
            "abc124 3 3 1\nauthor Bob\nauthor-mail <bob@example.com>\n"
            "abc123 2 2\nauthor Alice\nauthor-mail <alice@example.com>\n"
        )
        mock_proc = MagicMock()
        mock_proc.returncode = 0
        mock_proc.stdout = blame_output
        with patch("subprocess.run", return_value=mock_proc):
            result = _get_primary_author("file.py")
        assert result == "alice@example.com"

    def test_returns_none_on_exception(self):
        with patch("subprocess.run", side_effect=Exception("no git")):
            result = _get_primary_author("file.py")
        assert result is None

    def test_skips_not_committed_yet(self):
        blame_output = "abc123 1 1\nauthor Not Committed Yet\nauthor-mail <not.committed.yet>\n"
        mock_proc = MagicMock()
        mock_proc.returncode = 0
        mock_proc.stdout = blame_output
        with patch("subprocess.run", return_value=mock_proc):
            result = _get_primary_author("file.py")
        assert result is None


@pytest.mark.unit
class TestDeveloperProfile:
    def test_record_violation_unfixed_increases_risk(self, tmp_path):
        profile = DeveloperProfile("abc123", "repo1", store_dir=tmp_path)
        assert profile.risk_score == 0.0
        profile.record_violation("E501", fixed=False)
        assert profile.risk_score > 0.0

    def test_record_violation_fixed_keeps_low_risk(self, tmp_path):
        profile = DeveloperProfile("abc123", "repo1", store_dir=tmp_path)
        profile.record_violation("E501", fixed=True)
        # EWMA: 0.3 * 0.0 + 0.7 * 0.0 = 0.0
        assert profile.risk_score == 0.0

    def test_ewma_converges_on_repeated_unfixed(self, tmp_path):
        profile = DeveloperProfile("abc123", "repo1", store_dir=tmp_path)
        for _ in range(20):
            profile.record_violation("E501", fixed=False)
        # Should converge toward 1.0 but never exceed it
        assert 0.9 < profile.risk_score <= 1.0

    def test_ewma_recovers_with_fixes(self, tmp_path):
        profile = DeveloperProfile("abc123", "repo1", store_dir=tmp_path)
        # Drive risk up
        for _ in range(10):
            profile.record_violation("E501", fixed=False)
        high_risk = profile.risk_score
        # Now start fixing everything
        for _ in range(20):
            profile.record_violation("E501", fixed=True)
        assert profile.risk_score < high_risk

    def test_total_violations_accumulates(self, tmp_path):
        profile = DeveloperProfile("abc123", "repo1", store_dir=tmp_path)
        profile.record_violation("E501", fixed=False)
        profile.record_violation("F401", fixed=True)
        assert profile.total_violations == 2
        assert profile.total_fixes == 1

    def test_violations_by_rule_tracked(self, tmp_path):
        profile = DeveloperProfile("abc123", "repo1", store_dir=tmp_path)
        profile.record_violation("E501", fixed=False)
        profile.record_violation("E501", fixed=True)
        profile.record_violation("F401", fixed=False)
        by_rule = profile._data["violations_by_rule"]
        assert by_rule["E501"]["count"] == 2
        assert by_rule["E501"]["fixes"] == 1
        assert by_rule["F401"]["count"] == 1

    def test_save_and_reload(self, tmp_path):
        profile = DeveloperProfile("abc123", "repo1", store_dir=tmp_path)
        profile.record_violation("E501", fixed=False)
        score_before = profile.risk_score

        # Reload from disk
        profile2 = DeveloperProfile("abc123", "repo1", store_dir=tmp_path)
        assert profile2.risk_score == score_before
        assert profile2.total_violations == 1

    def test_record_run_keeps_last_30(self, tmp_path):
        profile = DeveloperProfile("abc123", "repo1", store_dir=tmp_path)
        for i in range(35):
            profile.record_run(f"run-{i}", violations=5, fixes=3)
        assert len(profile._data["run_history"]) == 30
        # Most recent run is last
        assert profile._data["run_history"][-1]["run_id"] == "run-34"

    def test_summary_contains_top_rules(self, tmp_path):
        profile = DeveloperProfile("abc123", "repo1", store_dir=tmp_path)
        for _ in range(3):
            profile.record_violation("E501", fixed=False)
        for _ in range(1):
            profile.record_violation("F401", fixed=True)
        summary = profile.summary()
        assert summary["dev_hash"] == "abc123"
        assert len(summary["top_rules"]) >= 1
        assert summary["top_rules"][0]["rule"] == "E501"

    def test_for_email_factory(self, tmp_path):
        profile = DeveloperProfile.for_email("dev@corp.io", "repo1", store_dir=tmp_path)
        assert profile.dev_hash == _hash_email("dev@corp.io")
        assert profile.repo_id == "repo1"

    def test_for_file_returns_none_when_blame_fails(self, tmp_path):
        with patch("data_store.developer_profile._get_primary_author", return_value=None):
            result = DeveloperProfile.for_file("missing.py", "repo1", store_dir=tmp_path)
        assert result is None

    def test_for_file_returns_profile_when_blame_succeeds(self, tmp_path):
        with patch("data_store.developer_profile._get_primary_author", return_value="dev@corp.io"):
            result = DeveloperProfile.for_file("app.py", "repo1", store_dir=tmp_path)
        assert result is not None
        assert result.dev_hash == _hash_email("dev@corp.io")


@pytest.mark.unit
class TestDeveloperRiskLeaderboard:
    def _make_profile_file(self, store_dir: Path, dev_hash: str, risk_score: float):
        data = {
            "dev_hash": dev_hash,
            "repo_id": "repo1",
            "risk_score": risk_score,
            "total_violations": 5,
            "total_fixes": 2,
            "last_seen": "2026-02-25T00:00:00+00:00",
        }
        store_dir.mkdir(parents=True, exist_ok=True)
        (store_dir / f"{dev_hash}.json").write_text(json.dumps(data))

    def test_top_n_sorts_by_risk_desc(self, tmp_path):
        # store_dir overrides the full path — files go directly into store_dir
        self._make_profile_file(tmp_path, "aaa111", 0.8)
        self._make_profile_file(tmp_path, "bbb222", 0.3)
        self._make_profile_file(tmp_path, "ccc333", 0.6)
        board = DeveloperRiskLeaderboard("repo1", store_dir=tmp_path)
        result = board.top_n(10)
        assert result[0]["dev_hash"] == "aaa111"
        assert result[1]["dev_hash"] == "ccc333"
        assert result[2]["dev_hash"] == "bbb222"

    def test_top_n_respects_limit(self, tmp_path):
        for i in range(5):
            self._make_profile_file(tmp_path, f"dev{i:03d}", float(i) / 4)
        board = DeveloperRiskLeaderboard("repo1", store_dir=tmp_path)
        result = board.top_n(3)
        assert len(result) == 3

    def test_top_n_empty_dir(self, tmp_path):
        empty = tmp_path / "nonexistent"
        board = DeveloperRiskLeaderboard("nonexistent", store_dir=empty)
        result = board.top_n(10)
        assert result == []

    def test_top_n_skips_malformed_json(self, tmp_path):
        self._make_profile_file(tmp_path, "aaa111", 0.9)
        (tmp_path / "corrupt.json").write_text("{not valid json")
        board = DeveloperRiskLeaderboard("repo1", store_dir=tmp_path)
        result = board.top_n(10)
        assert len(result) == 1  # corrupt file skipped
