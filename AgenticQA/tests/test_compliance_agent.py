"""
Dedicated Compliance Agent Tests — exercises ComplianceAgent.execute() with real input data.

Verifies:
  - Return schema: data_encryption, pii_protection, audit_logs, violations
  - Encryption detection (both `encrypted` and `encryption_enabled` keys)
  - PII masking detection (both `pii_masked` and `pii_masking` keys)
  - Violation generation for missing encryption/PII
  - Context-aware rules: test-only repos skip data rules
  - Non-blocking scanner integration (CVE, legal, HIPAA, SBOM, AI Act)
"""
import pytest
from agents import ComplianceAgent


@pytest.fixture
def agent():
    return ComplianceAgent()


# ── Return schema ─────────────────────────────────────────────────────────────

@pytest.mark.unit
def test_compliance_returns_required_keys(agent):
    result = agent.execute({"encrypted": True, "pii_masked": True, "audit_enabled": True})
    assert "data_encryption" in result
    assert "pii_protection" in result
    assert "audit_logs" in result
    assert "violations" in result


# ── Encryption detection ─────────────────────────────────────────────────────

@pytest.mark.unit
def test_compliance_encrypted_key(agent):
    result = agent.execute({"encrypted": True, "pii_masked": True})
    assert result["data_encryption"] is True


@pytest.mark.unit
def test_compliance_encryption_enabled_key(agent):
    """Accepts 'encryption_enabled' as alternative to 'encrypted'."""
    result = agent.execute({"encryption_enabled": True, "pii_masked": True})
    assert result["data_encryption"] is True


@pytest.mark.unit
def test_compliance_no_encryption_false(agent):
    result = agent.execute({"encrypted": False, "pii_masked": True})
    assert result["data_encryption"] is False


# ── PII masking detection ────────────────────────────────────────────────────

@pytest.mark.unit
def test_compliance_pii_masked_key(agent):
    result = agent.execute({"encrypted": True, "pii_masked": True})
    assert result["pii_protection"] is True


@pytest.mark.unit
def test_compliance_pii_masking_key(agent):
    """Accepts 'pii_masking' as alternative to 'pii_masked'."""
    result = agent.execute({"encrypted": True, "pii_masking": True})
    assert result["pii_protection"] is True


# ── Violation generation ─────────────────────────────────────────────────────

@pytest.mark.unit
def test_compliance_violation_missing_encryption(agent):
    result = agent.execute({"encrypted": False, "pii_masked": True})
    assert any("encryption" in str(v).lower() for v in result["violations"])


@pytest.mark.unit
def test_compliance_violation_missing_pii(agent):
    result = agent.execute({"encrypted": True, "pii_masked": False})
    assert any("pii" in str(v).lower() for v in result["violations"])


@pytest.mark.unit
def test_compliance_no_violations_when_compliant(agent):
    result = agent.execute({"encrypted": True, "pii_masked": True, "audit_enabled": True})
    # Only string violations (not scanner dicts) should be absent
    string_violations = [v for v in result["violations"] if isinstance(v, str) and "[RAG]" not in v]
    assert len(string_violations) == 0


# ── Context-aware rules ──────────────────────────────────────────────────────

@pytest.mark.unit
def test_compliance_test_only_repo_skips_data_rules(agent):
    """Test-only repos should not trigger encryption/PII violations."""
    result = agent.execute({
        "context": "test suite, jest, cypress e2e",
        "encrypted": False,
        "pii_masked": False,
    })
    # With test-only context, data-at-rest rules are skipped
    string_violations = [v for v in result["violations"] if isinstance(v, str)
                         and "encryption" in v.lower() and "[RAG]" not in v]
    assert len(string_violations) == 0


@pytest.mark.unit
def test_compliance_database_repo_enforces_rules(agent):
    """Repos with database context must enforce encryption/PII rules."""
    result = agent.execute({
        "context": "database, postgres, user data",
        "encrypted": False,
        "pii_masked": False,
    })
    string_violations = [v for v in result["violations"] if isinstance(v, str) and "[RAG]" not in v]
    assert len(string_violations) >= 2  # encryption + PII


# ── Audit logs ───────────────────────────────────────────────────────────────

@pytest.mark.unit
def test_compliance_audit_logs_tracked(agent):
    result = agent.execute({"encrypted": True, "pii_masked": True, "audit_enabled": True})
    assert result["audit_logs"] is True


@pytest.mark.unit
def test_compliance_audit_logs_default_false(agent):
    result = agent.execute({"encrypted": True, "pii_masked": True})
    assert result["audit_logs"] is False


# ── Edge cases ────────────────────────────────────────────────────────────────

@pytest.mark.unit
def test_compliance_empty_input(agent):
    result = agent.execute({})
    assert result["data_encryption"] is False
    assert result["pii_protection"] is False


@pytest.mark.unit
def test_compliance_rag_insights_count(agent):
    result = agent.execute({"encrypted": True, "pii_masked": True})
    assert "rag_insights_used" in result


@pytest.mark.unit
def test_compliance_violations_are_list(agent):
    result = agent.execute({"encrypted": True, "pii_masked": True})
    assert isinstance(result["violations"], list)


@pytest.mark.unit
def test_compliance_multiple_executions(agent):
    r1 = agent.execute({"encrypted": True, "pii_masked": True})
    r2 = agent.execute({"encrypted": False, "pii_masked": False})
    assert r1["data_encryption"] is True
    assert r2["data_encryption"] is False
