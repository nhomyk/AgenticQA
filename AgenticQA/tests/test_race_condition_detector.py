"""Unit tests for RaceConditionDetector — @pytest.mark.unit"""
import pytest
from pathlib import Path

from agenticqa.security.race_condition_detector import (
    RaceConditionDetector,
    RaceConditionFinding,
    RaceConditionResult,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def det() -> RaceConditionDetector:
    return RaceConditionDetector()


def write(path: Path, content: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return path


# ---------------------------------------------------------------------------
# scan_content tests
# ---------------------------------------------------------------------------

@pytest.mark.unit
class TestScanContent:

    def test_toctou_file_existence(self):
        code = "if os.path.exists(path):\n    open(path, 'r')\n"
        findings = det().scan_content(code, "app.py")
        ids = [f.pattern_id for f in findings]
        assert "RC-001" in ids

    def test_global_var_mutation(self):
        code = "def inc():\n    global counter\n    counter += 1\n"
        findings = det().scan_content(code, "app.py")
        ids = [f.pattern_id for f in findings]
        assert "RC-003" in ids

    def test_double_checked_locking(self):
        code = "if instance is None:\n    lock.acquire()\n    if instance is None:\n        instance = Cls()\n"
        findings = det().scan_content(code, "app.py")
        ids = [f.pattern_id for f in findings]
        assert "RC-005" in ids

    def test_toctou_session_token(self):
        code = "if user.is_authenticated():\n    user.delete()\n"
        findings = det().scan_content(code, "auth.py")
        ids = [f.pattern_id for f in findings]
        assert "RC-004" in ids

    def test_shared_file_write_cache(self):
        code = "with open(cache_file, 'w') as f:\n    f.write(data)\n"
        findings = det().scan_content(code, "caching.py")
        ids = [f.pattern_id for f in findings]
        assert "RC-006" in ids

    def test_shared_file_write_non_shared_name_not_flagged(self):
        # Should NOT be flagged when file name doesn't suggest shared state
        code = "with open(output_file, 'w') as f:\n    f.write(data)\n"
        findings = det().scan_content(code, "utils.py")
        rc6 = [f for f in findings if f.pattern_id == "RC-006"]
        assert len(rc6) == 0

    def test_lazy_init_detected(self):
        code = "if self.client is None:\n    self.client = Client()\n"
        findings = det().scan_content(code, "app.py")
        ids = [f.pattern_id for f in findings]
        assert "RC-007" in ids

    def test_clean_file_no_findings(self):
        code = "def add(a, b):\n    return a + b\n\ndef main():\n    print(add(1, 2))\n"
        findings = det().scan_content(code, "clean.py")
        assert findings == []

    def test_scan_content_standalone(self):
        code = "if os.path.isfile(path):\n    data = open(path).read()\n"
        findings = det().scan_content(code, "reader.py")
        assert len(findings) > 0

    def test_to_dict_fields(self):
        code = "if os.path.exists(f):\n    open(f)\n"
        findings = det().scan_content(code, "app.py")
        assert len(findings) > 0
        d = findings[0].to_dict()
        assert "pattern_id" in d
        assert "severity" in d
        assert "source_file" in d
        assert "line_number" in d
        assert "evidence" in d
        assert "description" in d
        assert "attack_scenario" in d

    def test_finding_to_dict(self):
        f = RaceConditionFinding(
            pattern_id="RC-001",
            severity="critical",
            source_file="app.py",
            line_number=5,
            evidence="if os.path.exists(p):",
            description="TOCTOU",
            attack_scenario="Attacker replaces file",
        )
        d = f.to_dict()
        assert d["pattern_id"] == "RC-001"
        assert d["severity"] == "critical"

    def test_attack_scenario_populated(self):
        code = "if os.path.exists(f):\n    open(f)\n"
        findings = det().scan_content(code, "app.py")
        assert len(findings) > 0
        assert len(findings[0].attack_scenario) > 0

    def test_severity_critical_on_toctou(self):
        code = "if os.path.exists(f):\n    open(f)\n"
        findings = det().scan_content(code, "app.py")
        rc001 = [f for f in findings if f.pattern_id == "RC-001"]
        assert all(f.severity == "critical" for f in rc001)

    def test_multiple_findings_in_one_file(self):
        code = (
            "global counter\n"
            "if os.path.exists(path):\n"
            "    open(path)\n"
        )
        findings = det().scan_content(code, "multi.py")
        pattern_ids = {f.pattern_id for f in findings}
        assert len(pattern_ids) >= 2

    def test_read_modify_write_increment(self):
        code = "count += 1\n"
        findings = det().scan_content(code, "app.py")
        ids = [f.pattern_id for f in findings]
        assert "RC-002" in ids


# ---------------------------------------------------------------------------
# Full scan tests
# ---------------------------------------------------------------------------

@pytest.mark.unit
class TestScanDirectory:

    def test_risk_score_zero_on_clean(self, tmp_path):
        write(tmp_path / "clean.py", "def hello():\n    return 1\n")
        result = det().scan(str(tmp_path))
        assert result.risk_score == 0.0

    def test_risk_score_increases_with_findings(self, tmp_path):
        write(tmp_path / "app.py", "if os.path.exists(f):\n    open(f)\n")
        result = det().scan(str(tmp_path))
        assert result.risk_score > 0.0

    def test_by_pattern_grouping(self, tmp_path):
        write(tmp_path / "app.py",
              "if os.path.exists(f):\n    open(f)\nglobal x\n")
        result = det().scan(str(tmp_path))
        groups = result.by_pattern()
        assert isinstance(groups, dict)

    def test_result_to_dict_fields(self, tmp_path):
        write(tmp_path / "a.py", "pass\n")
        result = det().scan(str(tmp_path))
        d = result.to_dict()
        assert "repo_path" in d
        assert "findings" in d
        assert "files_scanned" in d
        assert "risk_score" in d
        assert "by_pattern" in d
