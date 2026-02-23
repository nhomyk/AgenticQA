from types import SimpleNamespace

import pytest

from agenticqa.factory.agent_factory import AgentFactory, _install_hint
from agenticqa.data_store.snapshot_pipeline import SnapshotValidatingPipeline
import data_store.great_expectations_validator as gev


def test_agent_factory_wrap_scaffold_and_register(monkeypatch):
    factory = AgentFactory()

    class _WrapAdapter:
        @staticmethod
        def wrap(agent_obj, agent_name, capabilities, framework=None):
            return SimpleNamespace(agent_name=agent_name, framework=framework or "wrapped", capabilities=capabilities)

        @staticmethod
        def scaffold(agent_name, capabilities, framework=None):
            return f"scaffold:{agent_name}:{framework or 'none'}"

    class _SandboxAdapter:
        @staticmethod
        def scaffold(agent_name, capabilities):
            return f"sandbox:{agent_name}:{len(capabilities)}"

    monkeypatch.setitem(
        __import__("agenticqa.factory.agent_factory", fromlist=["SUPPORTED_FRAMEWORKS"]).SUPPORTED_FRAMEWORKS,
        "langgraph",
        _WrapAdapter,
    )
    monkeypatch.setitem(
        __import__("agenticqa.factory.agent_factory", fromlist=["SUPPORTED_FRAMEWORKS"]).SUPPORTED_FRAMEWORKS,
        "custom",
        _WrapAdapter,
    )
    monkeypatch.setattr("agenticqa.factory.agent_factory.GenericAdapter", _WrapAdapter)
    monkeypatch.setattr("agenticqa.factory.agent_factory.SandboxedAgentAdapter", _SandboxAdapter)

    wrapped_known = factory.wrap("langgraph", "A1", object(), ["x"])
    wrapped_unknown = factory.wrap("unknown", "A2", object(), ["y"])
    assert wrapped_known.agent_name == "A1"
    assert wrapped_unknown.framework == "unknown"

    sc_langgraph = factory.scaffold("langgraph", "S1", ["deploy"])
    sc_sandbox = factory.scaffold("sandboxed", "S2", ["safe"])
    sc_custom = factory.scaffold("custom", "S3", ["lint"])
    assert "generated_code" in sc_langgraph
    assert sc_sandbox["generated_code"].startswith("sandbox:")
    assert sc_custom["generated_code"].startswith("scaffold:")

    class _Graph:
        def __init__(self, fail=False):
            self.fail = fail
            self.calls = 0

        def create_or_update_agent(self, name, framework):
            self.calls += 1
            if self.fail:
                raise RuntimeError("no graph")

    class _Registry:
        def __init__(self, fail=False):
            self.fail = fail
            self.calls = 0

        def register_agent(self, wrapper):
            self.calls += 1
            if self.fail:
                raise RuntimeError("no registry")

    out_ok = factory.register(SimpleNamespace(agent_name="X", framework="f"), graph_store=_Graph(), registry=_Registry())
    out_partial = factory.register(
        SimpleNamespace(agent_name="Y", framework="f"),
        graph_store=_Graph(fail=True),
        registry=_Registry(),
    )

    assert out_ok["registered_in"] == ["neo4j", "agent_registry"]
    assert out_partial["registered_in"] == ["agent_registry"]
    assert _install_hint("langgraph") == "pip install langgraph"
    assert _install_hint("unknown") == ""


def test_snapshot_pipeline_validate_and_report(monkeypatch):
    class _Orchestrator:
        def execute_all_agents(self, test_data):
            return {
                "qa_agent": {"status": "ok"},
                "performance_agent": {"status": "ok"},
                "compliance_agent": {"status": "drift"},
                "devops_agent": {"status": "ok"},
            }

    class _SnapshotMgr:
        def __init__(self):
            self.created = []

        def compare_snapshot(self, name, output):
            if name == "qa_agent_snapshot":
                return {"status": "new", "matches": True}
            if name == "compliance_agent_snapshot":
                return {
                    "status": "mismatch",
                    "matches": False,
                    "differences": {"changed_values": {"status": ["ok", "drift"]}},
                }
            return {"status": "match", "matches": True}

        def create_snapshot(self, name, output):
            self.created.append(name)

    class _Quality:
        def run_all_tests(self):
            return {"passed_tests": 3, "failed_tests": 1}

    monkeypatch.setattr("agenticqa.AgentOrchestrator", _Orchestrator)

    pipeline = SnapshotValidatingPipeline(snapshot_dir="/tmp/snap")
    pipeline.snapshot_mgr = _SnapshotMgr()
    pipeline.quality_tester = _Quality()

    results = pipeline.validate_with_snapshots({"x": 1})
    report = pipeline.generate_validation_report(results)

    assert results["all_validations_passed"] is False
    assert results["quality_checks_failed"] == 1
    assert "qa_agent_snapshot" in pipeline.snapshot_mgr.created
    assert "RECOMMENDATION: Do not deploy" in report


def test_great_expectations_validator_branches(monkeypatch):
    monkeypatch.setattr(gev, "GREAT_EXPECTATIONS_AVAILABLE", False)
    with pytest.raises(ImportError):
        gev.AgentDataValidator()

    class _PD:
        @staticmethod
        def DataFrame(rows):
            return {"rows": rows}

    class _ValidationResult:
        def __init__(self, payload):
            self.payload = payload

        def to_dict(self):
            return self.payload

    class _Validator:
        def __init__(self):
            self.expectation_suite_name = None

        def expect_table_columns_to_match_ordered_list(self, **kwargs):
            return None

        def expect_column_values_to_not_be_null(self, **kwargs):
            return None

        def expect_column_values_to_be_in_set(self, **kwargs):
            return None

        def validate(self):
            return _ValidationResult({"success": True})

    class _Context:
        def __init__(self):
            self.validator = _Validator()

        def get_validator(self, **kwargs):
            return self.validator

    class _RuntimeBatchRequest:
        def __init__(self, **kwargs):
            self.kwargs = kwargs

    monkeypatch.setattr(gev, "GREAT_EXPECTATIONS_AVAILABLE", True)
    monkeypatch.setattr(gev, "pd", _PD)
    monkeypatch.setattr(gev, "RuntimeBatchRequest", _RuntimeBatchRequest, raising=False)
    monkeypatch.setattr(gev, "DataContext", lambda context_root_dir=None: _Context(), raising=False)

    validator = gev.AgentDataValidator(context_root_dir="ge")
    exec_out = validator.validate_agent_execution(
        "qa_agent",
        {
            "run_id": "r1",
            "timestamp": "2026-01-01T00:00:00",
            "agent_name": "qa_agent",
            "status": "success",
            "output": "done",
        },
    )

    schema_out = validator.validate_data_schema({"rows": [{"x": 1}]}, "suite-a")

    assert exec_out["success"] is True
    assert schema_out["success"] is True
