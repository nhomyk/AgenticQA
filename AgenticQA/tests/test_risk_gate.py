"""Unit tests for DeveloperRiskGate."""
import json
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

from agenticqa.gates.risk_gate import DeveloperRiskGate


def _write_profile(store_dir: Path, repo_id: str, dev_hash: str, risk_score: float):
    # DeveloperProfile(store_dir=store_dir) sets _dir = Path(store_dir),
    # so the file lives directly at store_dir/{dev_hash}.json (no repo_id subdir).
    store_dir.mkdir(parents=True, exist_ok=True)
    (store_dir / f"{dev_hash}.json").write_text(json.dumps({
        "dev_hash": dev_hash,
        "repo_id": repo_id,
        "risk_score": risk_score,
        "total_violations": 5,
        "total_fixes": 1,
        "violations_by_rule": {},
        "run_history": [],
        "created_at": "2025-01-01T00:00:00+00:00",
    }))


@pytest.mark.unit
class TestDeveloperRiskGate:
    def test_pass_when_no_files(self, tmp_path):
        gate = DeveloperRiskGate(threshold=0.7, store_dir=tmp_path)
        result = gate.evaluate([], repo_id="abc123", cwd=".")
        assert result["gate"] == "pass"
        assert result["files_checked"] == 0

    def test_pass_when_blame_fails(self, tmp_path):
        gate = DeveloperRiskGate(threshold=0.7, store_dir=tmp_path)
        with patch("data_store.developer_profile._get_primary_author", return_value=None):
            result = gate.evaluate(["src/foo.py"], repo_id="abc123", cwd=".")
        assert result["gate"] == "pass"
        assert result["files_checked"] == 0

    def test_block_high_risk_author(self, tmp_path):
        dev_hash = "aabbcc112233"
        _write_profile(tmp_path, "repo01", dev_hash, risk_score=0.95)
        gate = DeveloperRiskGate(threshold=0.7, store_dir=tmp_path)
        with patch("data_store.developer_profile._get_primary_author", return_value="dev@example.com"), \
             patch("data_store.developer_profile._hash_email", return_value=dev_hash):
            result = gate.evaluate(["src/foo.py"], repo_id="repo01", cwd=".")
        assert result["gate"] == "block"
        assert result["high_risk_files"][0]["dev_hash"] == dev_hash
        assert result["max_risk"] == 0.95

    def test_pass_low_risk_author(self, tmp_path):
        dev_hash = "aabbcc112233"
        _write_profile(tmp_path, "repo01", dev_hash, risk_score=0.20)
        gate = DeveloperRiskGate(threshold=0.7, store_dir=tmp_path)
        with patch("data_store.developer_profile._get_primary_author", return_value="dev@example.com"), \
             patch("data_store.developer_profile._hash_email", return_value=dev_hash):
            result = gate.evaluate(["src/foo.py"], repo_id="repo01", cwd=".")
        assert result["gate"] == "pass"
        assert result["max_risk"] == 0.20

    def test_custom_threshold(self, tmp_path):
        dev_hash = "aabbcc112233"
        _write_profile(tmp_path, "repo01", dev_hash, risk_score=0.50)
        gate = DeveloperRiskGate(threshold=0.40, store_dir=tmp_path)
        with patch("data_store.developer_profile._get_primary_author", return_value="dev@example.com"), \
             patch("data_store.developer_profile._hash_email", return_value=dev_hash):
            result = gate.evaluate(["src/foo.py"], repo_id="repo01", cwd=".")
        assert result["gate"] == "block"

    def test_high_risk_files_sorted_desc(self, tmp_path):
        hashes = ["aaa000000001", "bbb000000002"]
        for h, score in zip(hashes, [0.75, 0.95]):
            _write_profile(tmp_path, "repo01", h, risk_score=score)
        gate = DeveloperRiskGate(threshold=0.7, store_dir=tmp_path)
        emails = ["a@x.com", "b@x.com"]
        call_count = [-1]

        def fake_author(file_path, cwd=None):
            call_count[0] += 1
            return emails[call_count[0]]

        def fake_hash(email):
            return hashes[emails.index(email)]

        with patch("data_store.developer_profile._get_primary_author", side_effect=fake_author), \
             patch("data_store.developer_profile._hash_email", side_effect=fake_hash):
            result = gate.evaluate(["f1.py", "f2.py"], repo_id="repo01", cwd=".")
        assert result["high_risk_files"][0]["risk_score"] == 0.95
        assert result["high_risk_files"][1]["risk_score"] == 0.75
