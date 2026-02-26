"""Unit tests for OutputProvenanceLogger — @pytest.mark.unit"""
import json
import pytest
from pathlib import Path

from agenticqa.provenance.output_provenance import (
    OutputProvenanceLogger,
    ProvenanceRecord,
    VerifyResult,
)


def make_logger(tmp_path: Path) -> OutputProvenanceLogger:
    return OutputProvenanceLogger(
        provenance_dir=str(tmp_path / "provenance"),
        secret="test-secret-key",
    )


# ---------------------------------------------------------------------------
# sign_and_log
# ---------------------------------------------------------------------------

@pytest.mark.unit
class TestSignAndLog:
    def test_returns_provenance_record(self, tmp_path):
        logger = make_logger(tmp_path)
        rec = logger.sign_and_log("qa_agent", "claude-sonnet-4-6", "output text", run_id="r1")
        assert isinstance(rec, ProvenanceRecord)
        assert rec.agent_name == "qa_agent"
        assert rec.model_id == "claude-sonnet-4-6"
        assert rec.run_id == "r1"
        assert len(rec.output_hash) == 64   # sha256 hex
        assert len(rec.signature) == 64

    def test_output_hash_is_sha256_of_text(self, tmp_path):
        import hashlib
        logger = make_logger(tmp_path)
        text = "hello provenance"
        rec = logger.sign_and_log("qa", "m1", text)
        expected = hashlib.sha256(text.encode()).hexdigest()
        assert rec.output_hash == expected

    def test_record_appended_to_jsonl(self, tmp_path):
        logger = make_logger(tmp_path)
        logger.sign_and_log("sre_agent", "m1", "output one")
        logger.sign_and_log("sre_agent", "m1", "output two")
        log_path = Path(tmp_path) / "provenance" / "sre_agent.jsonl"
        lines = [l for l in log_path.read_text().splitlines() if l.strip()]
        assert len(lines) == 2

    def test_output_length_recorded(self, tmp_path):
        logger = make_logger(tmp_path)
        text = "x" * 500
        rec = logger.sign_and_log("qa", "m1", text)
        assert rec.output_length == 500

    def test_different_outputs_different_hashes(self, tmp_path):
        logger = make_logger(tmp_path)
        r1 = logger.sign_and_log("qa", "m1", "output A")
        r2 = logger.sign_and_log("qa", "m1", "output B")
        assert r1.output_hash != r2.output_hash
        assert r1.signature != r2.signature


# ---------------------------------------------------------------------------
# verify
# ---------------------------------------------------------------------------

@pytest.mark.unit
class TestVerify:
    def test_verify_valid_output(self, tmp_path):
        logger = make_logger(tmp_path)
        text = "agent produced this output"
        logger.sign_and_log("qa", "m1", text)
        result = logger.verify(text, "qa")
        assert result.valid is True
        assert result.reason == "valid"
        assert result.record is not None

    def test_verify_not_found(self, tmp_path):
        logger = make_logger(tmp_path)
        result = logger.verify("never logged this", "qa")
        assert result.valid is False
        assert result.reason == "not_found"
        assert result.record is None

    def test_verify_tampered_signature(self, tmp_path):
        logger = make_logger(tmp_path)
        text = "original output"
        logger.sign_and_log("qa", "m1", text)
        # Tamper: flip a character in the signature in the JSONL file
        log_path = Path(tmp_path) / "provenance" / "qa.jsonl"
        data = json.loads(log_path.read_text().strip())
        data["signature"] = "0" * 64
        log_path.write_text(json.dumps(data) + "\n")
        result = logger.verify(text, "qa")
        assert result.valid is False
        assert result.reason == "signature_mismatch"

    def test_verify_by_hash(self, tmp_path):
        logger = make_logger(tmp_path)
        text = "some output"
        rec = logger.sign_and_log("qa", "m1", text)
        result = logger.verify_by_hash(rec.output_hash, "qa")
        assert result.valid is True

    def test_verify_unknown_hash(self, tmp_path):
        logger = make_logger(tmp_path)
        result = logger.verify_by_hash("a" * 64, "qa")
        assert result.valid is False
        assert result.reason == "not_found"


# ---------------------------------------------------------------------------
# get_chain
# ---------------------------------------------------------------------------

@pytest.mark.unit
class TestGetChain:
    def test_chain_returns_records(self, tmp_path):
        logger = make_logger(tmp_path)
        for i in range(5):
            logger.sign_and_log("sre", "m1", f"output {i}")
        chain = logger.get_chain("sre")
        assert len(chain) == 5

    def test_chain_respects_limit(self, tmp_path):
        logger = make_logger(tmp_path)
        for i in range(10):
            logger.sign_and_log("sre", "m1", f"output {i}")
        chain = logger.get_chain("sre", limit=3)
        assert len(chain) == 3

    def test_empty_chain_no_file(self, tmp_path):
        logger = make_logger(tmp_path)
        chain = logger.get_chain("nonexistent_agent")
        assert chain == []


# ---------------------------------------------------------------------------
# Different secrets
# ---------------------------------------------------------------------------

@pytest.mark.unit
class TestSecretIsolation:
    def test_different_secret_fails_verify(self, tmp_path):
        logger1 = OutputProvenanceLogger(
            provenance_dir=str(tmp_path / "p"), secret="secret-A"
        )
        logger2 = OutputProvenanceLogger(
            provenance_dir=str(tmp_path / "p"), secret="secret-B"
        )
        text = "shared output text"
        logger1.sign_and_log("qa", "m1", text)
        result = logger2.verify(text, "qa")
        assert result.valid is False
        assert result.reason == "signature_mismatch"
