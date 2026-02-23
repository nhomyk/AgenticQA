import json
import sys
import types
from pathlib import Path

import pytest

from agenticqa import cli


class _FakeOrchestrator:
    def execute_all_agents(self, test_data):
        return {"received": test_data, "ok": True}


class _Store:
    def __init__(self):
        self.storage_dir = Path("/tmp/artifacts")
        self.master_index = {
            "a": {"timestamp": "2026-01-01T00:00:00"},
            "b": {"timestamp": "2026-01-02T00:00:00"},
        }


class _AnalyzerWithDetect:
    def __init__(self, store):
        self.store = store

    def detect_patterns(self):
        return {"pattern": "detected"}


class _AnalyzerLegacy:
    def __init__(self, store):
        self.store = store

    def analyze_failure_patterns(self):
        return {"errors": 1}

    def analyze_performance_patterns(self):
        return {"perf": 2}

    def analyze_flakiness(self):
        return {"flake": 3}


class _Args:
    def __init__(self, **kwargs):
        self.__dict__.update(kwargs)


def test_load_json_file_success(tmp_path):
    p = tmp_path / "input.json"
    p.write_text(json.dumps({"x": 1}))

    assert cli.load_json_file(str(p)) == {"x": 1}


def test_load_json_file_not_found_exits(capsys):
    with pytest.raises(SystemExit) as exc:
        cli.load_json_file("/definitely/missing.json")

    assert exc.value.code == 1
    assert "File not found" in capsys.readouterr().err


def test_load_json_file_invalid_json_exits(tmp_path, capsys):
    p = tmp_path / "bad.json"
    p.write_text("{not json")

    with pytest.raises(SystemExit) as exc:
        cli.load_json_file(str(p))

    assert exc.value.code == 1
    assert "Invalid JSON" in capsys.readouterr().err


def test_execute_command_prints_results(monkeypatch, capsys):
    monkeypatch.setattr(cli, "load_json_file", lambda _: {"tests": ["a"]})
    monkeypatch.setattr(cli, "_create_orchestrator", lambda: _FakeOrchestrator())

    cli.execute_command(_Args(test_data_file="unused.json"))

    out = capsys.readouterr().out
    assert "Executing AgenticQA agents" in out
    assert '"ok": true' in out


def test_patterns_command_detect_patterns_branch(monkeypatch, capsys):
    monkeypatch.setattr(cli, "_get_store_and_analyzer", lambda: (_Store, _AnalyzerWithDetect))

    cli.patterns_command(_Args())

    out = capsys.readouterr().out
    assert "Detected Patterns" in out
    assert '"pattern": "detected"' in out


def test_patterns_command_legacy_branch(monkeypatch, capsys):
    monkeypatch.setattr(cli, "_get_store_and_analyzer", lambda: (_Store, _AnalyzerLegacy))

    cli.patterns_command(_Args())

    out = capsys.readouterr().out
    assert '"errors"' in out
    assert '"perf"' in out
    assert '"flake"' in out


def test_stats_command_prints_summary(monkeypatch, capsys):
    monkeypatch.setattr(cli, "_get_store_and_analyzer", lambda: (_Store, _AnalyzerWithDetect))

    cli.stats_command(_Args())

    out = capsys.readouterr().out
    assert "Data Store Statistics" in out
    assert '"total_artifacts": 2' in out
    assert '"oldest_artifact": "2026-01-01T00:00:00"' in out


def test_bootstrap_doctor_and_ingest(monkeypatch, capsys, tmp_path):
    plugin = types.ModuleType("agenticqa.plugin_onboarding")

    class _BootstrapResult:
        def __init__(self):
            self.repo_root = tmp_path
            self.detected_stack = "python"
            self.created_files = [tmp_path / "a.txt"]

    class _DoctorResult:
        def __init__(self, healthy):
            self.healthy = healthy
            self.checks = {"db": True}

    plugin.bootstrap_project = lambda repo_root, force: _BootstrapResult()
    plugin.run_doctor = lambda repo_root: _DoctorResult(True)
    plugin.ingest_junit = lambda junit_file, output_path=None: {
        "source": str(junit_file),
        "out": str(output_path) if output_path else None,
    }

    monkeypatch.setitem(sys.modules, "agenticqa.plugin_onboarding", plugin)

    cli.bootstrap_command(_Args(repo=str(tmp_path), force=True))
    cli.doctor_command(_Args(repo=str(tmp_path)))
    cli.ingest_junit_command(_Args(junit_file=str(tmp_path / "junit.xml"), out=str(tmp_path / "out.json")))

    out = capsys.readouterr().out
    assert '"detected_stack": "python"' in out
    assert '"healthy": true' in out
    assert '"source"' in out


def test_doctor_unhealthy_exits(monkeypatch, tmp_path):
    plugin = types.ModuleType("agenticqa.plugin_onboarding")

    class _DoctorResult:
        healthy = False
        checks = {"db": False}

    plugin.run_doctor = lambda repo_root: _DoctorResult()
    monkeypatch.setitem(sys.modules, "agenticqa.plugin_onboarding", plugin)

    with pytest.raises(SystemExit) as exc:
        cli.doctor_command(_Args(repo=str(tmp_path)))

    assert exc.value.code == 2


def test_main_no_command_exits(monkeypatch):
    monkeypatch.setattr(sys, "argv", ["agenticqa"])

    with pytest.raises(SystemExit) as exc:
        cli.main()

    assert exc.value.code == 1


def test_main_dispatches_to_execute(monkeypatch):
    called = {"value": False}

    def _fake_execute(args):
        called["value"] = True
        assert args.test_data_file == "input.json"

    monkeypatch.setattr(cli, "execute_command", _fake_execute)
    monkeypatch.setattr(sys, "argv", ["agenticqa", "execute", "input.json"])

    cli.main()

    assert called["value"] is True
