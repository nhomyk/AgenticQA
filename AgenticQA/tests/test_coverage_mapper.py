"""Unit tests for CoverageMapper."""
import pytest
from pathlib import Path

from agenticqa.onboarding.coverage_mapper import (
    CoverageMap,
    CoverageMapper,
    LanguageCoverage,
    _is_test_file,
    _stem_variants,
)


# ── Helpers ────────────────────────────────────────────────────────────────────

def _write(tmp_path: Path, rel: str, content: str = "x") -> Path:
    p = tmp_path / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content)
    return p


# ── _is_test_file ──────────────────────────────────────────────────────────────

@pytest.mark.unit
def test_is_test_file_pytest_prefix():
    p = Path("tests/test_auth.py")
    assert _is_test_file(p)


@pytest.mark.unit
def test_is_test_file_pytest_suffix():
    p = Path("src/auth_test.py")
    assert _is_test_file(p)


@pytest.mark.unit
def test_is_test_file_jest_spec():
    p = Path("src/Button.spec.tsx")
    assert _is_test_file(p)


@pytest.mark.unit
def test_is_test_file_jest_test():
    p = Path("src/api.test.ts")
    assert _is_test_file(p)


@pytest.mark.unit
def test_is_test_file_go():
    p = Path("pkg/auth_test.go")
    assert _is_test_file(p)


@pytest.mark.unit
def test_is_test_file_swift():
    p = Path("Tests/AuthTests.swift")
    assert _is_test_file(p)


@pytest.mark.unit
def test_is_test_file_in_test_dir():
    p = Path("tests/integration/auth.py")
    assert _is_test_file(p)


@pytest.mark.unit
def test_is_test_file_in_spec_dir():
    p = Path("spec/auth.ts")
    assert _is_test_file(p)


@pytest.mark.unit
def test_is_not_test_file_regular_py():
    p = Path("src/auth.py")
    assert not _is_test_file(p)


@pytest.mark.unit
def test_is_not_test_file_regular_ts():
    p = Path("src/components/Button.tsx")
    assert not _is_test_file(p)


# ── _stem_variants ─────────────────────────────────────────────────────────────

@pytest.mark.unit
def test_stem_variants_plain():
    v = _stem_variants("auth")
    assert "auth" in v


@pytest.mark.unit
def test_stem_variants_service_suffix():
    v = _stem_variants("authservice")
    assert "auth" in v
    assert "authservice" in v


@pytest.mark.unit
def test_stem_variants_controller_suffix():
    v = _stem_variants("UserController")
    # lowercased
    assert "user" in v


@pytest.mark.unit
def test_stem_variants_handler_suffix():
    v = _stem_variants("paymenthandler")
    assert "payment" in v


# ── CoverageMapper.scan ────────────────────────────────────────────────────────

@pytest.mark.unit
def test_empty_repo(tmp_path):
    cm = CoverageMapper().scan(str(tmp_path))
    assert cm.total_source_files == 0
    assert cm.coverage_pct == 0.0
    assert cm.covered_files == []
    assert cm.uncovered_files == []
    assert cm.test_files == []


@pytest.mark.unit
def test_source_with_matching_test(tmp_path):
    _write(tmp_path, "src/auth.py", "def login(): pass")
    _write(tmp_path, "tests/test_auth.py", "def test_login(): pass")

    cm = CoverageMapper().scan(str(tmp_path))
    assert "src/auth.py" in cm.covered_files
    assert cm.coverage_pct == 100.0


@pytest.mark.unit
def test_source_without_test(tmp_path):
    _write(tmp_path, "src/payments.py", "def pay(): pass")

    cm = CoverageMapper().scan(str(tmp_path))
    assert "src/payments.py" in cm.uncovered_files
    assert cm.coverage_pct == 0.0


@pytest.mark.unit
def test_mixed_covered_uncovered(tmp_path):
    _write(tmp_path, "src/auth.py")
    _write(tmp_path, "src/payments.py")
    _write(tmp_path, "tests/test_auth.py")

    cm = CoverageMapper().scan(str(tmp_path))
    assert "src/auth.py" in cm.covered_files
    assert "src/payments.py" in cm.uncovered_files
    assert cm.total_source_files == 2


@pytest.mark.unit
def test_coverage_ratio_half(tmp_path):
    _write(tmp_path, "src/a.py")
    _write(tmp_path, "src/b.py")
    _write(tmp_path, "tests/test_a.py")

    cm = CoverageMapper().scan(str(tmp_path))
    assert cm.coverage_pct == 50.0


@pytest.mark.unit
def test_jest_spec_file_matched(tmp_path):
    _write(tmp_path, "src/Button.tsx", "export const Button = () => <div/>;")
    _write(tmp_path, "src/Button.spec.tsx", "test('renders', () => {});")

    cm = CoverageMapper().scan(str(tmp_path))
    assert "src/Button.tsx" in cm.covered_files


@pytest.mark.unit
def test_go_test_file_matched(tmp_path):
    _write(tmp_path, "pkg/auth.go", "package auth")
    _write(tmp_path, "pkg/auth_test.go", "package auth")

    cm = CoverageMapper().scan(str(tmp_path))
    assert "pkg/auth.go" in cm.covered_files


@pytest.mark.unit
def test_test_files_excluded_from_source(tmp_path):
    _write(tmp_path, "src/auth.py")
    _write(tmp_path, "tests/test_auth.py")

    cm = CoverageMapper().scan(str(tmp_path))
    assert not any("test_auth" in f for f in cm.covered_files)
    assert not any("test_auth" in f for f in cm.uncovered_files)
    assert any("test_auth" in f for f in cm.test_files)


@pytest.mark.unit
def test_node_modules_skipped(tmp_path):
    _write(tmp_path, "src/app.ts")
    _write(tmp_path, "node_modules/lib/index.ts")

    cm = CoverageMapper().scan(str(tmp_path))
    assert all("node_modules" not in f for f in cm.uncovered_files)


@pytest.mark.unit
def test_venv_skipped(tmp_path):
    _write(tmp_path, "src/app.py")
    _write(tmp_path, ".venv/lib/python3.11/site-packages/foo.py")

    cm = CoverageMapper().scan(str(tmp_path))
    assert all(".venv" not in f for f in cm.uncovered_files)


@pytest.mark.unit
def test_by_language_python(tmp_path):
    _write(tmp_path, "src/app.py")
    _write(tmp_path, "tests/test_app.py")

    cm = CoverageMapper().scan(str(tmp_path))
    assert "python" in cm.by_language
    assert cm.by_language["python"].total >= 1


@pytest.mark.unit
def test_by_language_typescript(tmp_path):
    _write(tmp_path, "src/app.ts")

    cm = CoverageMapper().scan(str(tmp_path))
    assert "typescript" in cm.by_language


@pytest.mark.unit
def test_coverage_map_to_dict(tmp_path):
    _write(tmp_path, "src/app.py")
    _write(tmp_path, "tests/test_app.py")

    cm = CoverageMapper().scan(str(tmp_path))
    d = cm.to_dict()

    assert "total_source_files" in d
    assert "covered_count" in d
    assert "uncovered_count" in d
    assert "coverage_pct" in d
    assert "by_language" in d
    assert "uncovered_files" in d
    assert "high_risk_uncovered" in d


@pytest.mark.unit
def test_high_risk_uncovered_default_empty(tmp_path):
    _write(tmp_path, "src/app.py")
    cm = CoverageMapper().scan(str(tmp_path))
    assert cm.high_risk_uncovered == []


@pytest.mark.unit
def test_high_risk_uncovered_set_by_caller(tmp_path):
    _write(tmp_path, "src/app.py")
    cm = CoverageMapper().scan(str(tmp_path))
    cm.high_risk_uncovered = ["src/app.py"]
    assert cm.to_dict()["high_risk_uncovered_count"] == 1


@pytest.mark.unit
def test_service_stem_stripped_and_matched(tmp_path):
    """Source AuthService.py should match test_auth.py."""
    _write(tmp_path, "src/authservice.py")
    _write(tmp_path, "tests/test_auth.py")

    cm = CoverageMapper().scan(str(tmp_path))
    assert "src/authservice.py" in cm.covered_files


@pytest.mark.unit
def test_coverage_pct_property(tmp_path):
    _write(tmp_path, "a.py")
    _write(tmp_path, "b.py")
    _write(tmp_path, "c.py")
    _write(tmp_path, "tests/test_a.py")

    cm = CoverageMapper().scan(str(tmp_path))
    assert abs(cm.coverage_pct - 33.3) < 0.2


@pytest.mark.unit
def test_language_coverage_ratio():
    lc = LanguageCoverage(language="python", total=10, covered=7, uncovered=3)
    assert abs(lc.ratio - 0.7) < 0.001


@pytest.mark.unit
def test_language_coverage_ratio_zero_total():
    lc = LanguageCoverage(language="go", total=0, covered=0, uncovered=0)
    assert lc.ratio == 0.0


@pytest.mark.unit
def test_ruby_test_file_recognised(tmp_path):
    _write(tmp_path, "lib/payment.rb")
    _write(tmp_path, "spec/payment_spec.rb")

    cm = CoverageMapper().scan(str(tmp_path))
    assert "lib/payment.rb" in cm.covered_files
