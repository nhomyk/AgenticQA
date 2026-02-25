"""Unit tests for SemanticDiffAnalyzer."""
import pytest
from agenticqa.diff.semantic_diff import SemanticDiffAnalyzer, SemanticDiffResult


def _diff(removed_lines: list[str], file: str = "src/foo.py", func_ctx: str = "") -> str:
    """Build a minimal unified diff with the given removed lines."""
    func_line = f" def {func_ctx}():\n" if func_ctx else ""
    body = "".join(f"-    {ln}\n" for ln in removed_lines)
    return (
        f"--- a/{file}\n"
        f"+++ b/{file}\n"
        f"@@ -1,10 +1,5 @@\n"
        f"{func_line}"
        f"{body}"
    )


@pytest.mark.unit
class TestSemanticDiffAnalyzer:
    def _a(self) -> SemanticDiffAnalyzer:
        return SemanticDiffAnalyzer()

    def test_empty_diff_returns_no_changes(self):
        result = self._a().analyze_diff("")
        assert result.changes == []
        assert result.risk_score == 0.0

    def test_detects_removed_except_handler(self):
        diff = _diff(["except ValueError:"], func_ctx="process")
        result = self._a().analyze_diff(diff)
        assert result.high_risk_count == 1
        assert result.changes[0].change_type == "removed_error_handler"
        assert result.changes[0].risk == "high"

    def test_detects_removed_null_check(self):
        diff = _diff(["if x is None:"], func_ctx="validate")
        result = self._a().analyze_diff(diff)
        assert result.high_risk_count == 1
        assert result.changes[0].change_type == "removed_null_check"

    def test_detects_removed_assertion(self):
        diff = _diff(["assert user is not None, 'user required'"])
        result = self._a().analyze_diff(diff)
        assert result.high_risk_count >= 1
        types = [c.change_type for c in result.changes]
        assert "removed_assertion" in types

    def test_detects_removed_auth_decorator(self):
        diff = _diff(["@login_required"])
        result = self._a().analyze_diff(diff)
        assert result.high_risk_count >= 1
        assert any(c.change_type == "removed_auth_decorator" for c in result.changes)

    def test_detects_removed_validation_call(self):
        diff = _diff(["validate_input(data)"])
        result = self._a().analyze_diff(diff)
        assert any(c.change_type == "removed_validation" for c in result.changes)

    def test_detects_removed_timeout(self):
        diff = _diff(["requests.get(url, timeout=30)"])
        result = self._a().analyze_diff(diff)
        assert result.medium_risk_count >= 1
        assert any(c.change_type == "removed_timeout" for c in result.changes)

    def test_detects_removed_logging(self):
        diff = _diff(["logger.warning('invalid state')"])
        result = self._a().analyze_diff(diff)
        assert any(c.change_type == "removed_logging" for c in result.changes)

    def test_addition_lines_ignored(self):
        diff = (
            "--- a/src/foo.py\n+++ b/src/foo.py\n"
            "@@ -1,3 +1,4 @@\n"
            "+    except ValueError:\n"
            "+    if x is None:\n"
        )
        result = self._a().analyze_diff(diff)
        assert result.changes == []

    def test_function_context_attribution(self):
        diff = (
            "--- a/src/foo.py\n+++ b/src/foo.py\n"
            "@@ -10,5 +10,3 @@\n"
            " def my_handler():\n"
            "-    except Exception:\n"
        )
        result = self._a().analyze_diff(diff)
        assert result.changes[0].function == "my_handler"

    def test_multiple_files_counted(self):
        diff = (
            "--- a/src/a.py\n+++ b/src/a.py\n"
            "@@ -1,3 +1,2 @@\n"
            "-    except ValueError:\n"
            "--- a/src/b.py\n+++ b/src/b.py\n"
            "@@ -1,3 +1,2 @@\n"
            "-    if x is None:\n"
        )
        result = self._a().analyze_diff(diff)
        assert result.files_analyzed == 2
        assert result.high_risk_count == 2

    def test_risk_score_nonzero_on_high_findings(self):
        diff = _diff(["except Exception:", "assert x > 0"])
        result = self._a().analyze_diff(diff)
        assert result.risk_score > 0.0

    def test_risk_score_zero_on_clean_diff(self):
        diff = (
            "--- a/src/foo.py\n+++ b/src/foo.py\n"
            "@@ -1,3 +1,2 @@\n"
            "-    x = 1  # old value\n"
        )
        result = self._a().analyze_diff(diff)
        assert result.risk_score == 0.0

    def test_summary_keys_present(self):
        result = SemanticDiffResult()
        s = result.summary()
        assert "risk_score" in s
        assert "high_risk_count" in s
        assert "changes" in s

    def test_git_range_handles_no_git(self, tmp_path):
        result = SemanticDiffAnalyzer().analyze_git_range(cwd=str(tmp_path))
        assert result.error is not None or result.changes == []
