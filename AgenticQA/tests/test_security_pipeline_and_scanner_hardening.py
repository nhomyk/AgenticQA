from pathlib import Path

import pytest

from data_store.security_validator import DataSecurityValidator
from data_store.secure_pipeline import SecureDataPipeline
from agenticqa.repo_scanner import RepoScanner


class _ObjWithEmail:
    def __str__(self):
        return "contact me at hidden.user@example.com"


class _FakeStore:
    def __init__(self):
        self.stored = 0

    def store_artifact(self, artifact_data, artifact_type, source, tags):
        self.stored += 1
        return "artifact-1"

    def verify_artifact_integrity(self, artifact_id):
        return True


class _FailingGE:
    def validate_agent_execution(self, agent_name, execution_result):
        raise RuntimeError("GE validation failure")


def _valid_payload():
    return {
        "timestamp": "2026-02-23T00:00:00Z",
        "agent_name": "qa_agent",
        "status": "success",
        "output": {"ok": True},
    }


def test_schema_validation_rejects_eval_like_type_spec_without_execution(monkeypatch):
    called = {"system": False}

    def _fake_system(cmd):
        called["system"] = True
        return 0

    import os

    monkeypatch.setattr(os, "system", _fake_system)

    ok, errors = DataSecurityValidator.validate_schema_compliance(
        {"field": "x"}, {"field": "__import__('os').system('echo pwned')"}
    )

    assert ok is False
    assert any("Invalid type specification" in e for e in errors)
    assert called["system"] is False


def test_pii_detection_handles_non_serializable_values():
    ok, findings = DataSecurityValidator.validate_no_pii_leakage({"payload": _ObjWithEmail()})
    assert ok is False
    assert any("email" in f.lower() for f in findings)


def test_secure_pipeline_normalizes_signatures_and_rejects_invalid_shape():
    pipeline = SecureDataPipeline(use_great_expectations=False)

    ok1, result1 = pipeline.validate_input_data(_valid_payload())
    ok2, result2 = pipeline.validate_input_data(_valid_payload(), "sre_agent")

    assert ok1 is True
    assert result1["agent"] == "unknown"
    assert ok2 is True
    assert result2["agent"] == "sre_agent"

    with pytest.raises(TypeError):
        pipeline.validate_input_data(["not", "a", "dict"])


def test_secure_pipeline_handles_ge_failure_and_keeps_artifact_integrity_flow():
    pipeline = SecureDataPipeline(use_great_expectations=False)
    pipeline.ge_validator = _FailingGE()
    pipeline.artifact_store = _FakeStore()

    success, result = pipeline.execute_with_validation("qa_agent", _valid_payload())

    assert success is False
    assert result["stages"]["great_expectations"] is False
    assert "ge_error" in result
    # artifact still stored so evidence is preserved
    assert pipeline.artifact_store.stored == 1


def test_secure_pipeline_short_circuits_on_pii_failure_before_storage():
    pipeline = SecureDataPipeline(use_great_expectations=False)
    pipeline.artifact_store = _FakeStore()

    bad = _valid_payload()
    bad["output"] = {"contact": "admin@example.com"}

    success, result = pipeline.execute_with_validation("qa_agent", bad)

    assert success is False
    assert result["stages"]["pii_check"] is False
    assert pipeline.artifact_store.stored == 0


def test_repo_scanner_detects_private_temp_aws_and_github_tokens(tmp_path: Path):
    (tmp_path / "secrets.txt").write_text(
        """
-----BEGIN PRIVATE KEY-----
abc
-----END PRIVATE KEY-----
TEMP=ASIA1234567890ABCDEF
GITHUB=ghp_ABCDEFGHIJKLMNOPQRSTUVWXYZ1234567890
""".strip()
    )

    scanner = RepoScanner()
    result = scanner._scan_pii_secrets(tmp_path)

    types = {f["type"] for f in result.pii_findings}
    assert result.has_pii is True
    assert result.has_secrets is True
    assert "private_key" in types
    assert "aws_temp_access_key" in types
    assert "github_pat" in types
