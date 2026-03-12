"""
Tests for the K8s failure taxonomy loader and query system.

These tests verify that the taxonomy YAML loads correctly, all scenarios
are well-formed, and filtering/querying works as expected.
"""

import os

import pytest
import yaml

from agenticqa.k8s.taxonomy import FailureTaxonomy, Scenario


@pytest.fixture
def taxonomy():
    """Load the built-in failure taxonomy."""
    return FailureTaxonomy.load()


class TestTaxonomyLoad:
    """Test taxonomy YAML loading and parsing."""

    @pytest.mark.unit
    def test_loads_successfully(self, taxonomy):
        assert len(taxonomy) > 0

    @pytest.mark.unit
    def test_has_all_seven_categories(self, taxonomy):
        expected = {
            "pod_failures",
            "scheduling",
            "network",
            "storage",
            "control_plane",
            "scaling_updates",
            "config_drift",
        }
        assert set(taxonomy.categories) == expected

    @pytest.mark.unit
    def test_total_scenario_count(self, taxonomy):
        """Taxonomy should have ~46 base scenarios."""
        assert len(taxonomy) >= 40
        assert len(taxonomy) <= 60

    @pytest.mark.unit
    def test_all_scenarios_have_required_fields(self, taxonomy):
        for scenario in taxonomy:
            assert scenario.id, f"Missing ID"
            assert scenario.name, f"Missing name for {scenario.id}"
            assert scenario.category, f"Missing category for {scenario.id}"
            assert scenario.severity in (
                "critical", "high", "medium", "low"
            ), f"Invalid severity for {scenario.id}: {scenario.severity}"
            assert scenario.k8s_concept, f"Missing k8s_concept for {scenario.id}"
            assert scenario.description, f"Missing description for {scenario.id}"

    @pytest.mark.unit
    def test_ids_are_unique(self, taxonomy):
        ids = [s.id for s in taxonomy]
        assert len(ids) == len(set(ids)), "Duplicate scenario IDs found"

    @pytest.mark.unit
    def test_id_format(self, taxonomy):
        """IDs should be CATEGORY-NNN format."""
        for scenario in taxonomy:
            parts = scenario.id.split("-")
            assert len(parts) == 2, f"Bad ID format: {scenario.id}"
            assert parts[1].isdigit(), f"Bad ID number: {scenario.id}"

    @pytest.mark.unit
    def test_summary(self, taxonomy):
        summary = taxonomy.summary()
        assert summary["total_scenarios"] > 0
        assert summary["total_with_variants"] > summary["total_scenarios"]
        assert "by_category" in summary
        assert "by_severity" in summary


class TestTaxonomyFilter:
    """Test filtering scenarios by category, severity, tier."""

    @pytest.mark.unit
    def test_filter_by_category(self, taxonomy):
        pods = taxonomy.filter(category="pod_failures")
        assert len(pods) >= 10
        assert all(s.category == "pod_failures" for s in pods)

    @pytest.mark.unit
    def test_filter_by_severity(self, taxonomy):
        critical = taxonomy.filter(severity="critical")
        assert len(critical) > 0
        assert all(s.severity == "critical" for s in critical)

    @pytest.mark.unit
    def test_filter_combined(self, taxonomy):
        critical_pods = taxonomy.filter(category="pod_failures", severity="critical")
        assert all(
            s.category == "pod_failures" and s.severity == "critical"
            for s in critical_pods
        )

    @pytest.mark.unit
    def test_filter_no_results(self, taxonomy):
        result = taxonomy.filter(category="nonexistent")
        assert result == []


class TestTaxonomyLookup:
    """Test individual scenario lookup."""

    @pytest.mark.unit
    def test_get_by_id(self, taxonomy):
        scenario = taxonomy.get("POD-001")
        assert scenario is not None
        assert scenario.name == "OOMKilled"
        assert scenario.category == "pod_failures"
        assert scenario.severity == "critical"

    @pytest.mark.unit
    def test_get_nonexistent(self, taxonomy):
        assert taxonomy.get("FAKE-999") is None

    @pytest.mark.unit
    def test_scenario_severity_rank(self):
        s = Scenario(
            id="TEST-001", name="test", category="test",
            severity="critical", k8s_concept="", description="",
            detection="", test_method="",
        )
        assert s.severity_rank == 0

        s2 = Scenario(
            id="TEST-002", name="test", category="test",
            severity="low", k8s_concept="", description="",
            detection="", test_method="",
        )
        assert s2.severity_rank == 3


class TestStudyGuide:
    """Test interview study guide generation."""

    @pytest.mark.unit
    def test_study_guide_full(self, taxonomy):
        guide = taxonomy.study_guide()
        assert "POD FAILURES" in guide
        assert "NETWORK" in guide
        assert "OOMKilled" in guide

    @pytest.mark.unit
    def test_study_guide_category(self, taxonomy):
        guide = taxonomy.study_guide(category="pod_failures")
        assert "OOMKilled" in guide
        # Should NOT contain other categories
        assert "SCHEDULING" not in guide


class TestTaxonomyCustomLoad:
    """Test loading from custom YAML."""

    @pytest.mark.unit
    def test_load_custom_yaml(self, tmp_path):
        custom = {
            "categories": {
                "custom": {
                    "description": "Custom category",
                    "scenarios": [
                        {
                            "id": "CUSTOM-001",
                            "name": "Custom scenario",
                            "severity": "high",
                            "k8s_concept": "custom concept",
                            "description": "A custom test scenario",
                            "detection": "custom detection",
                            "test_method": "custom method",
                        }
                    ],
                }
            }
        }
        path = tmp_path / "custom.yaml"
        path.write_text(yaml.dump(custom))

        taxonomy = FailureTaxonomy.load(str(path))
        assert len(taxonomy) == 1
        assert taxonomy.get("CUSTOM-001") is not None
