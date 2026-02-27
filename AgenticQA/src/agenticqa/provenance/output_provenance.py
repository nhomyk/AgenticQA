"""
AI Output Provenance — cryptographic chain of custody for LLM outputs.

Every agent execution is signed with HMAC-SHA256 and appended to a JSONL
provenance log. This provides:
  - Auditability: prove what the AI said, when, and with which model
  - Integrity: detect if outputs were tampered with post-generation
  - Chain of custody: link CI run → agent → model → output hash
  - SARIF finding: UNATTESTED_OUTPUT if a deployed model run has no provenance record

Storage: .agenticqa/provenance/{agent_name}.jsonl (one record per line)
Secret:  AGENTICQA_PROVENANCE_SECRET env var (falls back to a deterministic local key)

Subprocess-free. No external deps beyond stdlib.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import logging
import os
import warnings
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

_PROVENANCE_DIR = Path(".agenticqa") / "provenance"
_DEFAULT_SECRET = "agenticqa-provenance-dev-key-change-in-prod"


# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------

@dataclass
class ProvenanceRecord:
    output_hash: str        # sha256 of raw output text
    model_id: str
    agent_name: str
    timestamp: str          # ISO 8601 UTC
    run_id: str             # GITHUB_RUN_ID or "local"
    input_hash: str         # sha256[:16] of serialised input (for linkage)
    signature: str          # HMAC-SHA256(output_hash|model_id|timestamp|agent_name, secret)
    output_length: int      # character count (not the raw text — keeps log compact)


@dataclass
class VerifyResult:
    valid: bool
    record: Optional[ProvenanceRecord]
    reason: str             # "valid", "signature_mismatch", "not_found", "hash_mismatch"


# ---------------------------------------------------------------------------
# Signer / Verifier
# ---------------------------------------------------------------------------

class OutputProvenanceLogger:
    """
    Signs and logs every agent output to a per-agent JSONL file.

    Usage (called automatically from BaseAgent._record_execution):
        logger = OutputProvenanceLogger()
        record = logger.sign_and_log(agent_name, model_id, output_text, run_id)

    Verification:
        result = logger.verify(output_text, agent_name)
    """

    def __init__(
        self,
        provenance_dir: Optional[str] = None,
        secret: Optional[str] = None,
    ):
        self._dir = Path(provenance_dir) if provenance_dir else _PROVENANCE_DIR
        resolved_secret = secret or os.getenv("AGENTICQA_PROVENANCE_SECRET")
        if resolved_secret is None:
            # Warn in CI — dev default produces weak, shared signatures
            if os.getenv("CI") or os.getenv("GITHUB_RUN_ID"):
                warnings.warn(
                    "AGENTICQA_PROVENANCE_SECRET is not set. "
                    "Provenance signatures are using the default dev key and are NOT production-grade. "
                    "Set AGENTICQA_PROVENANCE_SECRET as a CI secret.",
                    UserWarning,
                    stacklevel=2,
                )
            resolved_secret = _DEFAULT_SECRET
        self._secret = resolved_secret.encode()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def sign_and_log(
        self,
        agent_name: str,
        model_id: str,
        output_text: str,
        run_id: str = "local",
        input_data: object = None,
    ) -> ProvenanceRecord:
        """Sign output_text and append to the provenance JSONL log."""
        output_hash = self._hash_output(output_text)
        input_hash = self._hash_input(input_data)
        timestamp = datetime.now(timezone.utc).isoformat()
        signature = self._sign(output_hash, model_id, timestamp, agent_name)

        record = ProvenanceRecord(
            output_hash=output_hash,
            model_id=model_id,
            agent_name=agent_name,
            timestamp=timestamp,
            run_id=run_id,
            input_hash=input_hash,
            signature=signature,
            output_length=len(output_text),
        )
        self._append(agent_name, record)
        return record

    def verify(self, output_text: str, agent_name: str) -> VerifyResult:
        """
        Verify that output_text appears in the provenance log and its signature is valid.
        Returns the most-recent matching record.
        """
        output_hash = self._hash_output(output_text)
        records = self._load(agent_name)
        for record in reversed(records):
            if record.output_hash == output_hash:
                expected_sig = self._sign(
                    record.output_hash, record.model_id,
                    record.timestamp, record.agent_name,
                )
                if hmac.compare_digest(record.signature, expected_sig):
                    return VerifyResult(valid=True, record=record, reason="valid")
                return VerifyResult(valid=False, record=record, reason="signature_mismatch")
        return VerifyResult(valid=False, record=None, reason="not_found")

    def verify_by_hash(self, output_hash: str, agent_name: str) -> VerifyResult:
        """Verify by output hash alone (without the original text)."""
        records = self._load(agent_name)
        for record in reversed(records):
            if record.output_hash == output_hash:
                expected_sig = self._sign(
                    record.output_hash, record.model_id,
                    record.timestamp, record.agent_name,
                )
                if hmac.compare_digest(record.signature, expected_sig):
                    return VerifyResult(valid=True, record=record, reason="valid")
                return VerifyResult(valid=False, record=record, reason="signature_mismatch")
        return VerifyResult(valid=False, record=None, reason="not_found")

    def get_chain(self, agent_name: str, limit: int = 50) -> List[ProvenanceRecord]:
        """Return the most-recent N provenance records for an agent."""
        return self._load(agent_name)[-limit:]

    # ------------------------------------------------------------------
    # Crypto helpers
    # ------------------------------------------------------------------

    def _sign(self, output_hash: str, model_id: str, timestamp: str, agent_name: str) -> str:
        payload = f"{output_hash}|{model_id}|{timestamp}|{agent_name}".encode()
        return hmac.new(self._secret, payload, hashlib.sha256).hexdigest()

    @staticmethod
    def _hash_output(text: str) -> str:
        return hashlib.sha256(text.encode("utf-8", errors="replace")).hexdigest()

    @staticmethod
    def _hash_input(input_data: object) -> str:
        try:
            serialised = json.dumps(input_data, sort_keys=True, default=str)
        except Exception:
            serialised = str(input_data)
        return hashlib.sha256(serialised.encode()).hexdigest()[:16]

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------

    def _log_path(self, agent_name: str) -> Path:
        safe = agent_name.replace(" ", "_").lower()
        return self._dir / f"{safe}.jsonl"

    def _append(self, agent_name: str, record: ProvenanceRecord) -> None:
        path = self._log_path(agent_name)
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            with open(path, "a", encoding="utf-8") as f:
                f.write(json.dumps(asdict(record)) + "\n")
        except OSError:
            pass  # non-blocking

    def _load(self, agent_name: str) -> List[ProvenanceRecord]:
        path = self._log_path(agent_name)
        if not path.exists():
            return []
        records: List[ProvenanceRecord] = []
        try:
            for line in path.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if not line:
                    continue
                try:
                    d = json.loads(line)
                    records.append(ProvenanceRecord(**d))
                except Exception:
                    continue
        except OSError:
            pass
        return records
