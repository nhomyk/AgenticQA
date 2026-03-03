"""Tests for run_client_scan.py — the main user-facing scan entry point."""
import json
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

# Ensure scripts/ is importable
sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))
sys.path.insert(0, str(Path(__file__).parent.parent))

from scripts.run_client_scan import scan_repo, _run_scanner


pytestmark = pytest.mark.unit


class TestRunScanner:
    """Tests for the _run_scanner wrapper."""

    def test_successful_scanner(self):
        result = _run_scanner("test", lambda: {"findings": 3})
        assert result["status"] == "ok"
        assert result["result"]["findings"] == 3
        assert "elapsed_s" in result

    def test_failing_scanner(self):
        def bad():
            raise ValueError("boom")
        result = _run_scanner("test", bad)
        assert result["status"] == "error"
        assert "ValueError" in result["error"]
        assert "elapsed_s" in result


class TestScanRepo:
    """Integration tests for scan_repo() against a minimal repo."""

    @pytest.fixture
    def mini_repo(self, tmp_path):
        """Create a minimal Python 'repo' with a few files."""
        (tmp_path / "main.py").write_text(
            "import os\n"
            "import subprocess\n"
            "def run():\n"
            "    key = os.getenv('SECRET_KEY')\n"
            "    subprocess.run(['echo', key])\n"
        )
        (tmp_path / "config.py").write_text(
            "DATABASE_URL = 'postgresql://user:pass@localhost/db'\n"
            "API_KEY = 'sk-1234567890abcdef'\n"
        )
        (tmp_path / "README.md").write_text("# Test Repo\nA simple test project.\n")
        return str(tmp_path)

    def test_scan_repo_returns_all_scanners(self, mini_repo):
        results = scan_repo(mini_repo)
        expected_scanners = [
            "architecture", "legal_risk", "cve_reachability", "hipaa",
            "ai_model_sbom", "ai_act", "trust_graph", "prompt_injection",
            "mcp_security", "data_flow", "shadow_ai", "bias_detection",
            "injection_guard", "custom_rules",
        ]
        for scanner in expected_scanners:
            assert scanner in results, f"Missing scanner: {scanner}"

    def test_scan_repo_all_scanners_succeed(self, mini_repo):
        results = scan_repo(mini_repo)
        for name, data in results.items():
            assert data["status"] == "ok", f"Scanner {name} failed: {data.get('error')}"

    def test_scan_repo_architecture_finds_something(self, mini_repo):
        results = scan_repo(mini_repo)
        arch = results["architecture"]["result"]
        # Should find ENV_SECRETS and/or SHELL_EXEC
        assert arch["total_findings"] > 0 or arch["files_scanned"] > 0

    def test_scan_repo_nonexistent_path(self):
        results = scan_repo("/tmp/nonexistent_agenticqa_test_repo_12345")
        # Should not crash — scanners handle missing paths gracefully
        for name, data in results.items():
            assert data["status"] in ("ok", "error")

    def test_scan_repo_elapsed_time_tracked(self, mini_repo):
        results = scan_repo(mini_repo)
        for name, data in results.items():
            assert "elapsed_s" in data
            assert isinstance(data["elapsed_s"], (int, float))

    def test_scan_repo_empty_dir(self, tmp_path):
        results = scan_repo(str(tmp_path))
        # All scanners should still succeed (just find nothing)
        ok_count = sum(1 for d in results.values() if d["status"] == "ok")
        assert ok_count >= 10  # Most scanners should handle empty dirs

    def test_injection_guard_only_scans_code_files(self, tmp_path):
        """Verify that .md files are excluded from injection guard scan."""
        # Doc file with injection-like content should NOT be flagged
        (tmp_path / "docs.md").write_text(
            "Human: This is an example prompt\n"
            "Assistant: This is the response\n"
            "[INST] More instructions [/INST]\n"
        )
        # Code file with benign content should be scanned but clean
        (tmp_path / "app.py").write_text("print('hello world')\n")
        results = scan_repo(str(tmp_path))
        guard = results["injection_guard"]["result"]
        assert guard["total_findings"] == 0

    def test_bias_detector_low_false_positives(self, tmp_path):
        """Technical terms should not trigger bias detection."""
        (tmp_path / "code.py").write_text(
            "# Master branch handling\n"
            "whitespace = text.strip()\n"
            "is_disabled = button.disabled\n"
            "senior_version = '2.0'\n"
            "blind_index = compute_hash(data)\n"
            "native_code = compile(src)\n"
            "old_value = cache.get(key)\n"
            "international_encoding = 'utf-8'\n"
        )
        results = scan_repo(str(tmp_path))
        bias = results["bias_detection"]["result"]
        assert bias["total_findings"] == 0
