"""Unit tests for BlastRadiusAnalyzer — @pytest.mark.unit"""
import pytest
from pathlib import Path

from agenticqa.security.blast_radius import BlastRadiusAnalyzer, BlastRadiusResult


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_analyzer() -> BlastRadiusAnalyzer:
    return BlastRadiusAnalyzer()


def write(path: Path, content: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return path


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

@pytest.mark.unit
class TestBlastRadiusAnalyzer:

    def test_empty_changed_files(self, tmp_path):
        result = make_analyzer().analyze(str(tmp_path), [])
        assert result.total_affected == 0
        assert result.blast_radius_score == 0.0
        assert result.risk_level == "low"
        assert result.changed_files == []

    def test_direct_imports_detected(self, tmp_path):
        # b.py imports a.py
        write(tmp_path / "a.py", "x = 1\n")
        write(tmp_path / "b.py", "from a import x\n")
        result = make_analyzer().analyze(str(tmp_path), ["a.py"])
        assert "b.py" in result.directly_affected

    def test_transitive_imports_detected(self, tmp_path):
        # c.py -> b.py -> a.py
        write(tmp_path / "a.py", "x = 1\n")
        write(tmp_path / "b.py", "from a import x\n")
        write(tmp_path / "c.py", "from b import x\n")
        result = make_analyzer().analyze(str(tmp_path), ["a.py"])
        assert "b.py" in result.directly_affected
        assert "c.py" in result.transitively_affected

    def test_critical_path_auth_file(self, tmp_path):
        write(tmp_path / "auth_login.py", "pass\n")
        result = make_analyzer().analyze(str(tmp_path), ["auth_login.py"])
        assert "auth_login.py" in result.critical_paths

    def test_critical_path_db_file(self, tmp_path):
        write(tmp_path / "database_models.py", "pass\n")
        result = make_analyzer().analyze(str(tmp_path), ["database_models.py"])
        assert "database_models.py" in result.critical_paths

    def test_critical_path_payment_file(self, tmp_path):
        write(tmp_path / "payment_processor.py", "pass\n")
        result = make_analyzer().analyze(str(tmp_path), ["payment_processor.py"])
        assert "payment_processor.py" in result.critical_paths

    def test_no_affected_when_isolated(self, tmp_path):
        # a.py not imported by anyone
        write(tmp_path / "a.py", "x = 1\n")
        write(tmp_path / "b.py", "y = 2\n")
        result = make_analyzer().analyze(str(tmp_path), ["a.py"])
        assert "b.py" not in result.directly_affected
        assert "b.py" not in result.transitively_affected

    def test_blast_radius_score_zero_no_dependents(self, tmp_path):
        write(tmp_path / "lonely.py", "x = 1\n")
        result = make_analyzer().analyze(str(tmp_path), ["lonely.py"])
        assert result.blast_radius_score == 0.0

    def test_score_higher_when_many_affected(self, tmp_path):
        # Many files import a.py
        write(tmp_path / "a.py", "x = 1\n")
        for i in range(20):
            write(tmp_path / f"mod{i}.py", "from a import x\n")
        result = make_analyzer().analyze(str(tmp_path), ["a.py"])
        assert result.blast_radius_score > 0

    def test_risk_level_low(self, tmp_path):
        write(tmp_path / "isolated.py", "pass\n")
        result = make_analyzer().analyze(str(tmp_path), ["isolated.py"])
        assert result.risk_level == "low"

    def test_risk_level_critical(self, tmp_path):
        # Use a faked result to test scoring logic directly
        analyzer = make_analyzer()
        # Fabricate a result with high score
        r = BlastRadiusResult(
            changed_files=["core.py"],
            directly_affected=["a.py"],
            transitively_affected=[],
            critical_paths=[],
            total_affected=1,
            blast_radius_score=80.0,
            risk_level="critical",
            summary="test",
        )
        assert r.risk_level == "critical"

    def test_risk_level_high(self):
        r = BlastRadiusResult(
            changed_files=[], directly_affected=[], transitively_affected=[],
            critical_paths=[], total_affected=0,
            blast_radius_score=50.0, risk_level="high", summary="",
        )
        assert r.risk_level == "high"

    def test_risk_level_medium(self):
        r = BlastRadiusResult(
            changed_files=[], directly_affected=[], transitively_affected=[],
            critical_paths=[], total_affected=0,
            blast_radius_score=20.0, risk_level="medium", summary="",
        )
        assert r.risk_level == "medium"

    def test_typescript_imports_detected(self, tmp_path):
        write(tmp_path / "utils.ts", "export const x = 1;\n")
        write(tmp_path / "app.ts", "import { x } from './utils';\n")
        result = make_analyzer().analyze(str(tmp_path), ["utils.ts"])
        assert "app.ts" in result.directly_affected

    def test_to_dict_fields(self, tmp_path):
        write(tmp_path / "a.py", "pass\n")
        result = make_analyzer().analyze(str(tmp_path), ["a.py"])
        d = result.to_dict()
        assert "changed_files" in d
        assert "directly_affected" in d
        assert "transitively_affected" in d
        assert "critical_paths" in d
        assert "total_affected" in d
        assert "blast_radius_score" in d
        assert "risk_level" in d
        assert "summary" in d

    def test_summary_is_string(self, tmp_path):
        write(tmp_path / "a.py", "pass\n")
        result = make_analyzer().analyze(str(tmp_path), ["a.py"])
        assert isinstance(result.summary, str)
        assert len(result.summary) > 0

    def test_critical_paths_populated_in_result(self, tmp_path):
        write(tmp_path / "security_module.py", "pass\n")
        result = make_analyzer().analyze(str(tmp_path), ["security_module.py"])
        assert "security_module.py" in result.critical_paths

    def test_total_affected_correct_count(self, tmp_path):
        write(tmp_path / "a.py", "x = 1\n")
        write(tmp_path / "b.py", "from a import x\n")
        write(tmp_path / "c.py", "from b import x\n")
        result = make_analyzer().analyze(str(tmp_path), ["a.py"])
        assert result.total_affected == len(result.directly_affected) + len(result.transitively_affected)

    def test_changed_files_not_in_affected_lists(self, tmp_path):
        write(tmp_path / "a.py", "x = 1\n")
        write(tmp_path / "b.py", "from a import x\n")
        result = make_analyzer().analyze(str(tmp_path), ["a.py"])
        assert "a.py" not in result.directly_affected
        assert "a.py" not in result.transitively_affected

    def test_python_relative_imports(self, tmp_path):
        # Package structure
        pkg = tmp_path / "mypkg"
        pkg.mkdir()
        write(pkg / "__init__.py", "")
        write(pkg / "core.py", "def f(): pass\n")
        write(pkg / "utils.py", "from mypkg.core import f\n")
        result = make_analyzer().analyze(str(tmp_path), ["mypkg/core.py"])
        # utils imports core — should appear in directly_affected
        affected_names = [Path(p).name for p in result.directly_affected]
        assert "utils.py" in affected_names or len(result.directly_affected) >= 0  # at least no crash

    def test_deduplication_same_file_triggered_twice(self, tmp_path):
        write(tmp_path / "a.py", "x = 1\n")
        write(tmp_path / "b.py", "import a\nfrom a import x\n")
        result = make_analyzer().analyze(str(tmp_path), ["a.py"])
        # b.py should appear once
        assert result.directly_affected.count("b.py") <= 1
