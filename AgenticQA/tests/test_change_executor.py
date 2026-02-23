from types import SimpleNamespace

import agenticqa.data_store.change_executor as change_executor


class _Analysis:
    def __init__(self, safe=True, reason="ok"):
        self.safe_to_deploy = safe
        self.reason = reason

    def to_dict(self):
        return {"safe_to_deploy": self.safe_to_deploy, "reason": self.reason}


class _Tracker:
    def __init__(self, analysis=None):
        self.analysis = analysis or _Analysis(True)
        self.started = []

    def start_change(self, name, before_metrics):
        self.started.append((name, before_metrics))
        return "chg-1"

    def end_change(self, after_metrics, change_id):
        return self.analysis

    def list_changes(self):
        return ["1", "2", "3"]

    def get_change_analysis(self, change_id):
        mapping = {
            "1": {"safe_to_deploy": True, "quality_delta": 5},
            "2": {"safe_to_deploy": False, "quality_delta": -2},
            "3": {"safe_to_deploy": True, "quality_delta": 3},
        }
        return mapping[change_id]


class _Orchestrator:
    def __init__(self):
        self.calls = 0

    def execute_all_agents(self, test_data):
        self.calls += 1
        if self.calls == 1:
            return {
                "execution_time_ms": 100,
                "qa_agent": {"tests_passed": 8, "tests_failed": 2, "quality_score": 80},
                "performance_agent": {"status": "passed"},
                "compliance_agent": {"compliance_score": 90},
            }
        return {
            "execution_time_ms": 95,
            "qa_agent": {"tests_passed": 9, "tests_failed": 1, "quality_score": 85},
            "performance_agent": {"status": "failed"},
            "compliance_agent": {"compliance_score": 95},
        }


class _Pipeline:
    pass


class _Report:
    @staticmethod
    def generate_report(analysis):
        return f"safe={analysis.safe_to_deploy}"


def _patch_dependencies(monkeypatch, tracker):
    monkeypatch.setattr(change_executor, "CodeChangeTracker", lambda: tracker)
    monkeypatch.setattr(change_executor, "AgentOrchestrator", _Orchestrator)
    monkeypatch.setattr(change_executor, "DataQualityValidatedPipeline", _Pipeline)
    monkeypatch.setattr(change_executor, "ChangeImpactReport", _Report)


def test_execute_safe_change_success(monkeypatch):
    tracker = _Tracker(analysis=_Analysis(True, "good"))
    _patch_dependencies(monkeypatch, tracker)

    executor = change_executor.SafeCodeChangeExecutor()

    called = {"change": 0, "rollback": 0}

    def change_fn():
        called["change"] += 1

    def rollback_fn():
        called["rollback"] += 1

    result = executor.execute_safe_change("test-change", {"x": 1}, change_fn, rollback_fn)

    assert result["safe_to_deploy"] is True
    assert result["reason"] == "good"
    assert result["change_id"] == "chg-1"
    assert called["change"] == 1
    assert called["rollback"] == 0


def test_execute_safe_change_triggers_rollback_when_unsafe(monkeypatch):
    tracker = _Tracker(analysis=_Analysis(False, "regression"))
    _patch_dependencies(monkeypatch, tracker)

    executor = change_executor.SafeCodeChangeExecutor()

    called = {"rollback": 0}

    def rollback_fn():
        called["rollback"] += 1

    result = executor.execute_safe_change("unsafe-change", {}, lambda: None, rollback_fn)

    assert result["safe_to_deploy"] is False
    assert called["rollback"] == 1


def test_execute_safe_change_change_function_failure(monkeypatch):
    tracker = _Tracker()
    _patch_dependencies(monkeypatch, tracker)

    executor = change_executor.SafeCodeChangeExecutor()

    def change_fn():
        raise RuntimeError("boom")

    result = executor.execute_safe_change("bad-change", {}, change_fn)

    assert result["status"] == "failed"
    assert "boom" in result["error"]


def test_calculate_quality_score_paths(monkeypatch):
    tracker = _Tracker()
    _patch_dependencies(monkeypatch, tracker)

    executor = change_executor.SafeCodeChangeExecutor()

    score = executor._calculate_quality_score(
        {
            "qa_agent": {"quality_score": 80},
            "performance_agent": {"status": "passed"},
            "compliance_agent": {"compliance_score": 90},
        }
    )
    assert score == (80 + 100 + 90) / 3

    assert executor._calculate_quality_score({}) == 0.0


def test_change_history_analyzer_stats_and_report():
    analyzer = change_executor.ChangeHistoryAnalyzer(_Tracker())

    stats = analyzer.get_change_statistics()
    report = analyzer.generate_summary_report()

    assert stats["total_changes"] == 3
    assert stats["successful_changes"] == 2
    assert stats["failed_changes"] == 1
    assert stats["success_rate"] == (2 / 3) * 100
    assert "CODE CHANGE HISTORY SUMMARY" in report
