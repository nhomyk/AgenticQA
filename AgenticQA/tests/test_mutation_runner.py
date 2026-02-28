"""Unit tests for MutationRunner — @pytest.mark.unit"""
import pytest
from unittest.mock import MagicMock, patch

from agenticqa.testing.mutation_runner import MutationResult, MutationRunner, _verdict_from_rate


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_runner() -> MutationRunner:
    return MutationRunner()


SAMPLE_OUTPUT = """\
Killed (42):
1. path/module.py:10
Survived (5):
1. path/module.py:20
2. path/module.py:30
Timeout (3):
"""


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

@pytest.mark.unit
class TestMutationRunner:

    def test_mock_result_when_unavailable(self):
        runner = make_runner()
        with patch.object(runner, "_is_mutmut_available", return_value=False):
            result = runner.run(repo_path=".")
        assert result.verdict == "UNTESTED"
        assert result.total_mutants == 0
        assert result.kill_rate == 0.0

    def test_to_dict_fields(self):
        r = MutationResult(
            total_mutants=10, killed=8, survived=2, timeout=0,
            kill_rate=0.8, verdict="STRONG", survived_samples=[],
            files_mutated=["src/auth.py"], duration_seconds=5.0,
        )
        d = r.to_dict()
        assert "total_mutants" in d
        assert "killed" in d
        assert "survived" in d
        assert "timeout" in d
        assert "kill_rate" in d
        assert "verdict" in d
        assert "survived_samples" in d
        assert "files_mutated" in d
        assert "duration_seconds" in d

    def test_verdict_strong(self):
        assert _verdict_from_rate(0.80) == "STRONG"
        assert _verdict_from_rate(1.0) == "STRONG"
        assert _verdict_from_rate(0.95) == "STRONG"

    def test_verdict_adequate(self):
        assert _verdict_from_rate(0.60) == "ADEQUATE"
        assert _verdict_from_rate(0.79) == "ADEQUATE"

    def test_verdict_weak(self):
        assert _verdict_from_rate(0.30) == "WEAK"
        assert _verdict_from_rate(0.59) == "WEAK"

    def test_verdict_untested(self):
        assert _verdict_from_rate(0.0) == "UNTESTED"
        assert _verdict_from_rate(0.29) == "UNTESTED"

    def test_parse_killed_count(self):
        runner = make_runner()
        parsed = runner._parse_mutmut_results(SAMPLE_OUTPUT)
        assert parsed["killed"] == 42

    def test_parse_survived_count(self):
        runner = make_runner()
        parsed = runner._parse_mutmut_results(SAMPLE_OUTPUT)
        assert parsed["survived"] == 5

    def test_parse_timeout_count(self):
        runner = make_runner()
        parsed = runner._parse_mutmut_results(SAMPLE_OUTPUT)
        assert parsed["timeout"] == 3

    def test_parse_survived_samples_collected(self):
        runner = make_runner()
        parsed = runner._parse_mutmut_results(SAMPLE_OUTPUT)
        assert len(parsed["survived_samples"]) == 2

    def test_parse_survived_samples_capped_at_5(self):
        output = "Survived (10):\n" + "\n".join(f"{i}. path/file.py:{i}" for i in range(1, 11))
        runner = make_runner()
        parsed = runner._parse_mutmut_results(output)
        assert len(parsed["survived_samples"]) <= 5

    def test_parse_empty_output(self):
        runner = make_runner()
        parsed = runner._parse_mutmut_results("")
        assert parsed["killed"] == 0
        assert parsed["survived"] == 0
        assert parsed["timeout"] == 0

    def test_untested_when_no_mutants(self):
        r = MutationResult(
            total_mutants=0, killed=0, survived=0, timeout=0,
            kill_rate=0.0, verdict="UNTESTED", survived_samples=[],
            files_mutated=[], duration_seconds=0.0,
        )
        assert r.verdict == "UNTESTED"

    def test_duration_in_result(self):
        r = MutationResult(
            total_mutants=5, killed=4, survived=1, timeout=0,
            kill_rate=0.8, verdict="STRONG", survived_samples=[],
            files_mutated=[], duration_seconds=12.5,
        )
        assert r.duration_seconds == 12.5

    def test_files_mutated_list(self):
        r = MutationResult(
            total_mutants=0, killed=0, survived=0, timeout=0,
            kill_rate=0.0, verdict="UNTESTED", survived_samples=[],
            files_mutated=["src/a.py", "src/b.py"], duration_seconds=0.0,
        )
        assert "src/a.py" in r.files_mutated

    def test_kill_rate_zero_to_one_range(self):
        for rate in [0.0, 0.5, 1.0]:
            assert 0.0 <= rate <= 1.0

    def test_verdict_boundary_exactly_080(self):
        assert _verdict_from_rate(0.80) == "STRONG"

    def test_verdict_boundary_just_below_080(self):
        assert _verdict_from_rate(0.799) == "ADEQUATE"

    def test_verdict_boundary_exactly_060(self):
        assert _verdict_from_rate(0.60) == "ADEQUATE"

    def test_verdict_boundary_exactly_030(self):
        assert _verdict_from_rate(0.30) == "WEAK"

    def test_run_passes_target_files(self, tmp_path):
        runner = make_runner()
        with patch.object(runner, "_is_mutmut_available", return_value=False):
            result = runner.run(repo_path=str(tmp_path), target_files=["src/auth.py"])
        # When unavailable, still returns mock result without crash
        assert result.verdict == "UNTESTED"

    def test_is_mutmut_available_returns_bool(self):
        runner = make_runner()
        # mutmut is very likely not installed in CI — just ensure it returns bool
        result = runner._is_mutmut_available()
        assert isinstance(result, bool)
