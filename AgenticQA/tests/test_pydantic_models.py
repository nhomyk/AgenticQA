"""
Pydantic Model Validation Tests

Edge-case validation tests for all Pydantic models in agent_api.py
and dataclass models in the RAG subsystem.
"""

import pytest
from pydantic import ValidationError


class TestExecutionRequest:
    """Tests for ExecutionRequest model"""

    def get_model(self):
        from agent_api import ExecutionRequest
        return ExecutionRequest

    def test_all_fields_none_by_default(self):
        model = self.get_model()()
        assert model.test_results is None
        assert model.execution_data is None
        assert model.compliance_data is None
        assert model.deployment_config is None

    def test_all_fields_populated(self):
        model = self.get_model()(
            test_results={"total": 10, "passed": 9},
            execution_data={"duration_ms": 500},
            compliance_data={"violations": []},
            deployment_config={"target": "prod"},
        )
        assert model.test_results["total"] == 10
        assert model.deployment_config["target"] == "prod"

    def test_partial_fields(self):
        model = self.get_model()(test_results={"total": 5})
        assert model.test_results == {"total": 5}
        assert model.execution_data is None

    def test_empty_dicts_accepted(self):
        model = self.get_model()(
            test_results={},
            execution_data={},
            compliance_data={},
            deployment_config={},
        )
        assert model.test_results == {}

    def test_nested_dict_values(self):
        model = self.get_model()(
            test_results={"nested": {"deep": {"value": 42}}}
        )
        assert model.test_results["nested"]["deep"]["value"] == 42

    def test_dict_serialization(self):
        model = self.get_model()(test_results={"key": "value"})
        data = model.model_dump()
        assert isinstance(data, dict)
        assert data["test_results"] == {"key": "value"}
        assert data["execution_data"] is None

    def test_invalid_type_for_dict_field(self):
        with pytest.raises(ValidationError):
            self.get_model()(test_results="not a dict")

    def test_list_rejected_for_dict_field(self):
        with pytest.raises(ValidationError):
            self.get_model()(test_results=[1, 2, 3])

    def test_integer_rejected_for_dict_field(self):
        with pytest.raises(ValidationError):
            self.get_model()(test_results=42)


class TestArtifactSearchRequest:
    """Tests for ArtifactSearchRequest model"""

    def get_model(self):
        from agent_api import ArtifactSearchRequest
        return ArtifactSearchRequest

    def test_all_fields_none_by_default(self):
        model = self.get_model()()
        assert model.artifact_type is None
        assert model.source is None
        assert model.tags is None

    def test_all_fields_populated(self):
        model = self.get_model()(
            artifact_type="test_result",
            source="qa_agent",
            tags=["regression", "smoke"],
        )
        assert model.artifact_type == "test_result"
        assert model.source == "qa_agent"
        assert model.tags == ["regression", "smoke"]

    def test_empty_tags_list(self):
        model = self.get_model()(tags=[])
        assert model.tags == []

    def test_single_tag(self):
        model = self.get_model()(tags=["critical"])
        assert model.tags == ["critical"]

    def test_invalid_tags_type(self):
        with pytest.raises(ValidationError):
            self.get_model()(tags="not a list")

    def test_tags_with_non_string_elements(self):
        with pytest.raises(ValidationError):
            self.get_model()(tags=[1, 2, 3])

    def test_json_serialization_roundtrip(self):
        Model = self.get_model()
        original = Model(artifact_type="report", source="sdet", tags=["a", "b"])
        json_str = original.model_dump_json()
        restored = Model.model_validate_json(json_str)
        assert original == restored


class TestDataStoreStats:
    """Tests for DataStoreStats model"""

    def get_model(self):
        from agent_api import DataStoreStats
        return DataStoreStats

    def test_required_fields(self):
        model = self.get_model()(
            total_artifacts=100,
            by_type={"test_result": 60, "report": 40},
            by_source={"qa": 70, "compliance": 30},
        )
        assert model.total_artifacts == 100
        assert model.last_updated is None

    def test_all_fields(self):
        model = self.get_model()(
            total_artifacts=50,
            by_type={"report": 50},
            by_source={"sdet": 50},
            last_updated="2025-01-01T00:00:00Z",
        )
        assert model.last_updated == "2025-01-01T00:00:00Z"

    def test_missing_required_total_artifacts(self):
        with pytest.raises(ValidationError):
            self.get_model()(by_type={}, by_source={})

    def test_missing_required_by_type(self):
        with pytest.raises(ValidationError):
            self.get_model()(total_artifacts=0, by_source={})

    def test_missing_required_by_source(self):
        with pytest.raises(ValidationError):
            self.get_model()(total_artifacts=0, by_type={})

    def test_zero_artifacts(self):
        model = self.get_model()(total_artifacts=0, by_type={}, by_source={})
        assert model.total_artifacts == 0

    def test_negative_total_accepted(self):
        """Pydantic doesn't enforce non-negative by default."""
        model = self.get_model()(total_artifacts=-1, by_type={}, by_source={})
        assert model.total_artifacts == -1

    def test_invalid_by_type_value(self):
        with pytest.raises(ValidationError):
            self.get_model()(
                total_artifacts=1,
                by_type={"key": "not_an_int"},
                by_source={},
            )

    def test_large_numbers(self):
        model = self.get_model()(
            total_artifacts=999_999_999,
            by_type={"a": 999_999_999},
            by_source={"b": 999_999_999},
        )
        assert model.total_artifacts == 999_999_999


class TestStructuredMetricDataclass:
    """Tests for StructuredMetric dataclass in relational_store.py"""

    def get_dataclass(self):
        from agenticqa.rag.relational_store import StructuredMetric
        return StructuredMetric

    def test_create_metric(self):
        Metric = self.get_dataclass()
        m = Metric(
            id=1,
            run_id="run-123",
            agent_type="qa",
            metric_type="coverage",
            metric_name="line_coverage",
            metric_value=85.5,
            metadata={"branch": "main"},
            timestamp="2025-01-01T00:00:00Z",
        )
        assert m.id == 1
        assert m.metric_value == 85.5
        assert m.metadata["branch"] == "main"

    def test_optional_id(self):
        Metric = self.get_dataclass()
        m = Metric(
            id=None,
            run_id="run-456",
            agent_type="sdet",
            metric_type="test_result",
            metric_name="pass_rate",
            metric_value=0.95,
            metadata={},
            timestamp="2025-01-01T00:00:00Z",
        )
        assert m.id is None

    def test_empty_metadata(self):
        Metric = self.get_dataclass()
        m = Metric(
            id=1, run_id="r", agent_type="qa", metric_type="t",
            metric_name="n", metric_value=0.0, metadata={},
            timestamp="2025-01-01T00:00:00Z",
        )
        assert m.metadata == {}

    def test_float_metric_value(self):
        Metric = self.get_dataclass()
        m = Metric(
            id=1, run_id="r", agent_type="qa", metric_type="t",
            metric_name="n", metric_value=3.14159, metadata={},
            timestamp="2025-01-01T00:00:00Z",
        )
        assert abs(m.metric_value - 3.14159) < 1e-5
