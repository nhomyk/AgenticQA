from pathlib import Path

from src.data_store.pattern_analyzer import PatternAnalyzer


class _Store:
    def __init__(self, tmp_path: Path):
        self.patterns_dir = tmp_path
        self._artifacts = {
            "a1": {"status": "success", "error_type": "ValueError", "message": "boom in file.py"},
            "a2": {"status": "failed", "error_type": "TypeError", "message": "oops in service.py"},
            "a3": {"status": "failed", "error_type": "TypeError", "message": "oops in service.py"},
        }

    def search_artifacts(self, artifact_type=None):
        rows = [
            {"artifact_id": "a1", "source": "QA_Agent", "timestamp": "2026-02-23T00:00:00"},
            {"artifact_id": "a2", "source": "QA_Agent", "timestamp": "2026-02-23T00:00:00+00:00"},
            {"artifact_id": "a3", "source": "QA_Agent", "timestamp": "2026-02-23T01:00:00+00:00"},
        ]
        if artifact_type == "error":
            return rows
        return rows

    def get_artifact(self, artifact_id):
        return self._artifacts[artifact_id]


def test_analyze_flakiness_handles_naive_and_aware_timestamps(tmp_path):
    analyzer = PatternAnalyzer(_Store(tmp_path))

    result = analyzer.analyze_flakiness(window_days=3650)

    assert "flaky_agents" in result
    assert (tmp_path / "flakiness.json").exists()


def test_get_error_signatures_handles_mixed_timestamps(tmp_path):
    analyzer = PatternAnalyzer(_Store(tmp_path))

    signatures = analyzer.get_error_signatures("QA_Agent", window_days=3650)

    assert len(signatures) >= 1
    assert signatures[0]["signature"].startswith("TypeError")
