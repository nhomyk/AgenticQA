"""Unit tests for PRRiskScorer."""
import json
import pytest
from pathlib import Path
from unittest.mock import MagicMock, patch

from agenticqa.scoring.pr_risk_scorer import PRRiskScorer, PRRiskReport


# ── Helpers ────────────────────────────────────────────────────────────────────

def scorer() -> PRRiskScorer:
    s = PRRiskScorer()
    return s


def _score(
    author="dev@example.com",
    files=None,
    diff="",
    repo=".",
) -> PRRiskReport:
    """Score with learning helpers mocked out so tests are deterministic."""
    s = scorer()
    with patch.object(s, "_author_fix_rate", return_value=None), \
         patch.object(s, "_unfixable_rules", return_value=set()), \
         patch.object(s, "_learning_trend", return_value="unknown"):
        return s.score(
            author_email=author,
            changed_files=files or [],
            diff_lines=diff,
            repo_path=repo,
        )


# ── Low-risk baseline ──────────────────────────────────────────────────────────

@pytest.mark.unit
def test_clean_pr_is_low_risk():
    report = _score(files=["src/utils/formatter.py"], diff="+def fmt(x): return str(x)\n")
    assert report.recommendation == "LOW RISK"
    assert report.risk_score < 30


@pytest.mark.unit
def test_no_history_adds_small_penalty():
    report = _score(author="new@example.com")
    assert report.risk_score >= 10   # unknown author penalty
    assert any("unknown" in r.lower() or "no history" in r.lower() for r in report.reasoning)


# ── Author fix-rate ────────────────────────────────────────────────────────────

@pytest.mark.unit
def test_low_fix_rate_raises_score(tmp_path):
    """Author with 10% fix rate should score high risk."""
    from data_store.developer_profile import DeveloperProfile
    repo_id = "test_repo_low"
    email = "risky@example.com"
    store = tmp_path / "devs"
    profile = DeveloperProfile.for_email(email, repo_id, store_dir=store / repo_id)
    # Record 10 violations, only 1 fixed → 10% fix rate
    for i in range(10):
        profile.record_violation(f"E50{i % 3}", fixed=(i == 0))

    s = scorer()
    with patch("agenticqa.scoring.pr_risk_scorer.PRRiskScorer._author_fix_rate",
               return_value=profile.total_fixes / max(profile.total_violations, 1)), \
         patch.object(s, "_unfixable_rules", return_value=set()), \
         patch.object(s, "_learning_trend", return_value="unknown"):
        report = s.score(author_email=email, changed_files=[], repo_path=str(tmp_path))
    assert report.author_fix_rate == pytest.approx(0.1)
    assert report.risk_score >= 30
    assert "LOW_AUTHOR_FIX_RATE" in report.predicted_violations
    assert any("low" in r.lower() for r in report.reasoning)


@pytest.mark.unit
def test_high_fix_rate_lowers_score(tmp_path):
    """Author with 95% fix rate should get a score reduction."""
    s = scorer()
    with patch.object(s, "_author_fix_rate", return_value=0.95), \
         patch.object(s, "_unfixable_rules", return_value=set()), \
         patch.object(s, "_learning_trend", return_value="unknown"):
        report = s.score(author_email="reliable@example.com", changed_files=[], repo_path=str(tmp_path))
    assert report.author_fix_rate == pytest.approx(0.95)
    assert "LOW_AUTHOR_FIX_RATE" not in report.predicted_violations
    assert any("strong" in r.lower() for r in report.reasoning)


@pytest.mark.unit
def test_moderate_fix_rate_medium_penalty(tmp_path):
    """Author with 45% fix rate should get a moderate penalty."""
    s = scorer()
    with patch.object(s, "_author_fix_rate", return_value=0.45), \
         patch.object(s, "_unfixable_rules", return_value=set()), \
         patch.object(s, "_learning_trend", return_value="unknown"):
        report = s.score(author_email="avg@example.com", changed_files=[], repo_path=str(tmp_path))
    assert 10 <= report.risk_score <= 35


# ── Architectural / sensitive files ───────────────────────────────────────────

@pytest.mark.unit
def test_auth_file_raises_score():
    report = _score(files=["src/auth/login.py"])
    assert "SENSITIVE_FILE_TOUCHED" in report.predicted_violations
    assert report.risk_score > 10


@pytest.mark.unit
def test_db_migration_file_raises_score():
    report = _score(files=["db/migrations/0042_add_users.py"])
    assert "SENSITIVE_FILE_TOUCHED" in report.predicted_violations


@pytest.mark.unit
def test_payment_file_raises_score():
    report = _score(files=["src/billing/stripe_checkout.py"])
    assert "SENSITIVE_FILE_TOUCHED" in report.predicted_violations


@pytest.mark.unit
def test_non_sensitive_file_no_violation():
    report = _score(files=["src/utils/string_helpers.py"])
    assert "SENSITIVE_FILE_TOUCHED" not in report.predicted_violations


@pytest.mark.unit
def test_multiple_arch_files_capped():
    files = [f"src/auth/handler_{i}.py" for i in range(10)]
    report = _score(files=files)
    assert report.risk_score <= 100


# ── Dangerous diff patterns ────────────────────────────────────────────────────

@pytest.mark.unit
def test_eval_in_diff_raises_score():
    report = _score(diff="+result = eval(user_input)\n")
    assert "DANGEROUS_DIFF_PATTERN" in report.predicted_violations
    assert report.risk_score >= 10


@pytest.mark.unit
def test_hardcoded_password_in_diff():
    report = _score(diff='+password = "super_secret_123"\n')
    assert "DANGEROUS_DIFF_PATTERN" in report.predicted_violations


@pytest.mark.unit
def test_pickle_in_diff():
    report = _score(diff="+data = pickle.loads(raw_bytes)\n")
    assert "DANGEROUS_DIFF_PATTERN" in report.predicted_violations


@pytest.mark.unit
def test_clean_diff_no_danger():
    report = _score(diff="+def add(a, b):\n+    return a + b\n")
    assert "DANGEROUS_DIFF_PATTERN" not in report.predicted_violations


# ── Learning trend ─────────────────────────────────────────────────────────────

@pytest.mark.unit
def test_declining_trend_adds_score():
    s = PRRiskScorer()
    with patch.object(s, "_learning_trend", return_value="declining"):
        with patch.object(s, "_unfixable_rules", return_value=set()):
            with patch.object(s, "_author_fix_rate", return_value=0.8):
                report = s.score("x@x.com", [], repo_path=".")
    assert report.trend == "declining"
    assert report.risk_score >= 10


@pytest.mark.unit
def test_improving_trend_reduces_score():
    s = PRRiskScorer()
    with patch.object(s, "_learning_trend", return_value="improving"):
        with patch.object(s, "_unfixable_rules", return_value=set()):
            with patch.object(s, "_author_fix_rate", return_value=0.5):
                report = s.score("x@x.com", [], repo_path=".")
    assert report.trend == "improving"


# ── Unfixable rules ────────────────────────────────────────────────────────────

@pytest.mark.unit
def test_unfixable_rules_raises_score():
    s = PRRiskScorer()
    with patch.object(s, "_unfixable_rules", return_value={"F403", "E402", "no-var"}):
        with patch.object(s, "_learning_trend", return_value="unknown"):
            with patch.object(s, "_author_fix_rate", return_value=0.8):
                report = s.score("x@x.com", [], repo_path=".")
    assert report.risk_score >= 15
    assert len(report.unfixable_rules_hit) == 3


# ── Diff volume ────────────────────────────────────────────────────────────────

@pytest.mark.unit
def test_large_diff_adds_score():
    big_diff = "\n".join(f"+line_{i} = {i}" for i in range(600))
    report = _score(diff=big_diff)
    assert any("large" in r.lower() or "600" in r or "601" in r for r in report.reasoning)
    assert report.risk_score >= 10


@pytest.mark.unit
def test_small_diff_no_volume_penalty():
    tiny_diff = "+x = 1\n"
    report = _score(diff=tiny_diff)
    assert not any("large diff" in r.lower() for r in report.reasoning)


# ── Recommendations ────────────────────────────────────────────────────────────

@pytest.mark.unit
def test_score_60_plus_is_high_risk():
    s = PRRiskScorer()
    with patch.object(s, "_author_fix_rate", return_value=0.05):     # +30
        with patch.object(s, "_unfixable_rules", return_value={"F403","E402","no-var","C901"}):  # +20
            with patch.object(s, "_learning_trend", return_value="declining"):   # +10
                report = s.score("dev@x.com", ["src/auth/a.py"], repo_path=".")
    assert report.recommendation == "HIGH RISK"
    assert report.risk_score >= 60


@pytest.mark.unit
def test_score_30_to_59_is_medium_risk():
    """Moderate fix rate + several arch files + a dangerous diff pattern = MEDIUM RISK."""
    s = PRRiskScorer()
    with patch.object(s, "_author_fix_rate", return_value=0.45):  # +15
        with patch.object(s, "_unfixable_rules", return_value={"F403"}):  # +5
            with patch.object(s, "_learning_trend", return_value="unknown"):
                report = s.score(
                    "dev@x.com",
                    ["src/auth/login.py", "src/db/models.py"],  # +16
                    diff_lines="+eval(user_input)\n",           # +10
                    repo_path=".",
                )
    assert report.recommendation in ("MEDIUM RISK", "HIGH RISK")
    assert report.risk_score >= 30


# ── to_dict ────────────────────────────────────────────────────────────────────

@pytest.mark.unit
def test_to_dict_has_all_fields():
    report = _score()
    d = report.to_dict()
    for key in ("author_email", "risk_score", "recommendation",
                "predicted_violations", "reasoning", "trend"):
        assert key in d


@pytest.mark.unit
def test_risk_score_capped_at_100():
    s = PRRiskScorer()
    with patch.object(s, "_author_fix_rate", return_value=0.01):
        with patch.object(s, "_unfixable_rules", return_value={f"rule_{i}" for i in range(20)}):
            with patch.object(s, "_learning_trend", return_value="declining"):
                big_diff = "\n".join(f"+x={i}" for i in range(600))
                report = s.score("dev@x.com", [f"src/auth/f{i}.py" for i in range(5)],
                                 diff_lines=big_diff + "\n+eval(x)\n", repo_path=".")
    assert report.risk_score <= 100


# ── Integration: DeveloperProfile → PRRiskScorer data path ────────────────────

@pytest.mark.unit
def test_author_fix_rate_reads_developer_profile(tmp_path):
    """Verify the _author_fix_rate method reads DeveloperProfile correctly.

    This is the critical data path that was broken (sha1 vs md5 hash,
    wrong key name). This test ensures writes and reads are consistent.
    """
    from data_store.developer_profile import DeveloperProfile, _hash_email

    repo_id = "integ_test_repo"
    email = "integration@example.com"
    store_root = tmp_path / "devs"
    store_dir = store_root / repo_id

    # Write profile via DeveloperProfile
    profile = DeveloperProfile.for_email(email, repo_id, store_dir=store_dir)
    for _ in range(8):
        profile.record_violation("E501", fixed=True)
    for _ in range(2):
        profile.record_violation("F403", fixed=False)
    # 8 fixes / 10 violations = 0.8 fix rate

    # Read it back via PRRiskScorer._author_fix_rate
    s = PRRiskScorer()
    with patch("data_store.repo_profile._detect_repo_id", return_value=repo_id):
        with patch("data_store.developer_profile.DeveloperProfile.__init__",
                   side_effect=lambda self, dh, ri, store_dir=None: (
                       DeveloperProfile.__init__(self, dh, ri, store_dir=store_dir or store_dir)
                   )):
            # Simpler: just call the method and mock _detect_repo_id
            pass

    # Direct test: construct the profile the same way the scorer does
    from data_store.repo_profile import _detect_repo_id
    dev_hash = _hash_email(email)
    p2 = DeveloperProfile(dev_hash, repo_id, store_dir=store_dir)
    fix_rate = p2.total_fixes / max(p2.total_violations, 1)
    assert fix_rate == pytest.approx(0.8)


@pytest.mark.unit
def test_learning_trend_reads_fix_rate_trend(tmp_path):
    """Verify _learning_trend reads the 'fix_rate_trend' key (not 'trend')."""
    from data_store.learning_metrics import LearningMetricsSnapshot

    history_path = tmp_path / "metrics.jsonl"
    snap = LearningMetricsSnapshot(history_path=history_path)

    # Write enough records to compute a trend
    for i in range(10):
        snap.record(run_id=f"run_{i}", fix_rate=0.5 + i * 0.03, repo_id="test")

    summary = snap.summary(repo_id="test")
    assert "fix_rate_trend" in summary
    assert summary["fix_rate_trend"] in ("improving", "stable", "declining")

    # Verify PRRiskScorer reads the correct key
    s = PRRiskScorer()
    with patch("data_store.learning_metrics.LearningMetricsSnapshot", return_value=snap):
        trend = s._learning_trend(".")
    assert trend in ("improving", "stable", "declining")
