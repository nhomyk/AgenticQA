"""Unit tests for ComplianceDriftDetector."""
import pytest
from agenticqa.compliance.drift_detector import ComplianceDriftDetector


@pytest.mark.unit
class TestComplianceDriftDetector:
    def _detector(self, tmp_path):
        return ComplianceDriftDetector(store_dir=tmp_path)

    def _violations(self, types):
        return [{"type": t} for t in types]

    def test_record_appends_jsonl(self, tmp_path):
        d = self._detector(tmp_path)
        d.record_run("r1", self._violations(["pii", "pii"]), repo_path="/repo/a")
        lines = (tmp_path / "compliance_history.jsonl").read_text().strip().splitlines()
        assert len(lines) == 1

    def test_single_run_returns_stable(self, tmp_path):
        d = self._detector(tmp_path)
        d.record_run("r1", self._violations(["pii"]), repo_path="/repo/a")
        result = d.detect_drift("/repo/a")
        assert result["direction"] == "stable"
        assert result["previous_count"] is None
        assert result["runs_analysed"] == 1

    def test_worsening_direction(self, tmp_path):
        d = self._detector(tmp_path)
        d.record_run("r1", self._violations(["pii"]), repo_path="/repo")
        d.record_run("r2", self._violations(["pii", "pii", "audit"]), repo_path="/repo")
        result = d.detect_drift("/repo")
        assert result["direction"] == "worsening"
        assert result["delta"] == 2
        assert len(result["trending_rules"]) >= 1

    def test_improving_direction(self, tmp_path):
        d = self._detector(tmp_path)
        d.record_run("r1", self._violations(["pii", "pii", "pii"]), repo_path="/repo")
        d.record_run("r2", self._violations(["pii"]), repo_path="/repo")
        result = d.detect_drift("/repo")
        assert result["direction"] == "improving"
        assert result["delta"] == -2

    def test_stable_same_count(self, tmp_path):
        d = self._detector(tmp_path)
        d.record_run("r1", self._violations(["pii", "audit"]), repo_path="/repo")
        d.record_run("r2", self._violations(["pii", "audit"]), repo_path="/repo")
        result = d.detect_drift("/repo")
        assert result["direction"] == "stable"
        assert result["delta"] == 0

    def test_repo_isolation(self, tmp_path):
        d = self._detector(tmp_path)
        d.record_run("r1", self._violations(["pii"]), repo_path="/repo/a")
        d.record_run("r1", self._violations(["pii", "pii", "pii"]), repo_path="/repo/b")
        result_a = d.detect_drift("/repo/a")
        assert result_a["runs_analysed"] == 1  # only sees /repo/a records

    def test_history_limit(self, tmp_path):
        d = self._detector(tmp_path)
        for i in range(5):
            d.record_run(f"r{i}", self._violations(["pii"] * i), repo_path="/repo")
        hist = d.history("/repo", limit=3)
        assert len(hist) == 3

    def test_trending_rules_sorted_by_delta(self, tmp_path):
        d = self._detector(tmp_path)
        d.record_run("r1", self._violations(["a"]), repo_path="/repo")
        d.record_run("r2", self._violations(["a", "a", "a", "b", "b"]), repo_path="/repo")
        result = d.detect_drift("/repo")
        assert result["trending_rules"][0]["rule"] == "a"  # largest delta first

    def test_no_history_returns_zero_count(self, tmp_path):
        d = self._detector(tmp_path)
        result = d.detect_drift("/nonexistent/repo")
        assert result["current_count"] == 0
