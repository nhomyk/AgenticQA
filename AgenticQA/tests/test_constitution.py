"""Tests for the Agent Constitution and ConstitutionalGate.

Covers:
- constitution.yaml loads and has expected structure
- ConstitutionalGate: ALLOW, DENY (T1), REQUIRE_APPROVAL (T2)
- REST: GET /api/system/constitution
- REST: POST /api/system/constitution/check
"""

import sys
import os

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))


# ------------------------------------------------------------------ #
# Unit: ConstitutionalGate                                            #
# ------------------------------------------------------------------ #

@pytest.mark.unit
class TestConstitutionalGate:

    def _check(self, action_type, context=None):
        from agenticqa.constitutional_gate import check_action
        return check_action(action_type, context or {})

    # --- ALLOW cases ---

    def test_allow_safe_read_action(self):
        result = self._check("read", {"trace_id": "tr-001"})
        assert result["verdict"] == "ALLOW"
        assert result["law"] is None

    def test_allow_delete_with_ci_passed(self):
        result = self._check("delete", {
            "ci_status": "PASSED",
            "trace_id": "tr-001",
        })
        assert result["verdict"] == "ALLOW"

    def test_allow_delegate_below_depth_limit(self):
        result = self._check("delegate", {"delegation_depth": 2, "trace_id": "tr-001"})
        assert result["verdict"] == "ALLOW"

    def test_allow_write_with_trace(self):
        result = self._check("write", {
            "trace_id": "tr-001",
            "target_path": "/tmp/output.txt",
        })
        assert result["verdict"] == "ALLOW"

    # --- DENY cases (Tier 1) ---

    def test_deny_delete_without_ci_passed(self):
        result = self._check("delete", {"ci_status": "FAILED", "trace_id": "tr-001"})
        assert result["verdict"] == "DENY"
        assert result["law"] == "T1-001"
        assert result["name"] == "no_destructive_without_ci"
        assert result["reason"]

    def test_deny_delete_when_ci_status_missing(self):
        """Missing ci_status defaults to no-pass → should be DENY."""
        result = self._check("delete", {"trace_id": "tr-001"})
        assert result["verdict"] == "DENY"
        assert result["law"] == "T1-001"

    def test_deny_delegation_at_depth_3(self):
        result = self._check("delegate", {"delegation_depth": 3})
        assert result["verdict"] == "DENY"
        assert result["law"] == "T1-002"
        assert result["name"] == "delegation_depth_limit"

    def test_deny_delegation_at_depth_greater_than_3(self):
        result = self._check("delegate", {"delegation_depth": 5})
        assert result["verdict"] == "DENY"
        assert result["law"] == "T1-002"

    def test_deny_log_event_with_pii(self):
        result = self._check("log_event", {"contains_pii": True, "trace_id": "tr-001"})
        assert result["verdict"] == "DENY"
        assert result["law"] == "T1-003"
        assert result["name"] == "no_pii_in_decision_logs"

    def test_allow_log_event_without_pii(self):
        result = self._check("log_event", {"contains_pii": False, "trace_id": "tr-001"})
        assert result["verdict"] == "ALLOW"

    def test_deny_write_without_trace_id(self):
        result = self._check("write", {"target_path": "/tmp/out.txt"})
        assert result["verdict"] == "DENY"
        assert result["law"] == "T1-004"
        assert result["name"] == "no_external_write_without_trace"

    def test_deny_write_with_empty_trace_id(self):
        result = self._check("write", {"trace_id": "", "target_path": "/tmp/out.txt"})
        assert result["verdict"] == "DENY"
        assert result["law"] == "T1-004"

    def test_deny_modify_constitutional_gate(self):
        result = self._check("write", {
            "trace_id": "tr-001",
            "target_path": "/path/to/constitutional_gate.py",
        })
        assert result["verdict"] == "DENY"
        assert result["law"] == "T1-005"
        assert result["name"] == "no_self_modification"

    def test_deny_delete_constitution_yaml(self):
        result = self._check("delete", {
            "ci_status": "PASSED",
            "trace_id": "tr-001",
            "target_path": "/app/src/agenticqa/constitution.yaml",
        })
        # T1-005 is checked first for write/delete/modify
        assert result["verdict"] == "DENY"
        assert result["law"] == "T1-005"

    # --- REQUIRE_APPROVAL cases (Tier 2) ---

    def test_require_approval_production_deploy(self):
        result = self._check("deploy", {
            "environment": "production",
            "ci_status": "PASSED",
            "trace_id": "tr-001",
        })
        assert result["verdict"] == "REQUIRE_APPROVAL"
        assert result["law"] == "T2-001"
        assert result["name"] == "production_deployment_requires_approval"

    def test_allow_staging_deploy(self):
        result = self._check("deploy", {
            "environment": "staging",
            "ci_status": "PASSED",
            "trace_id": "tr-001",
        })
        assert result["verdict"] == "ALLOW"

    def test_require_approval_infra_modify(self):
        result = self._check("modify_infra", {"trace_id": "tr-001"})
        assert result["verdict"] == "REQUIRE_APPROVAL"
        assert result["law"] == "T2-002"

    def test_require_approval_bulk_delete_over_threshold(self):
        result = self._check("bulk_delete", {
            "record_count": 5000,
            "trace_id": "tr-001",
        })
        assert result["verdict"] == "REQUIRE_APPROVAL"
        assert result["law"] == "T2-003"

    def test_allow_bulk_delete_under_threshold(self):
        result = self._check("bulk_delete", {
            "record_count": 999,
            "trace_id": "tr-001",
        })
        assert result["verdict"] == "ALLOW"

    # --- Context edge cases ---

    def test_empty_context_defaults_safely(self):
        """Completely empty context should still produce a verdict."""
        result = self._check("read", {})
        assert result["verdict"] in {"ALLOW", "DENY", "REQUIRE_APPROVAL"}

    def test_none_context_treated_as_empty(self):
        from agenticqa.constitutional_gate import check_action
        result = check_action("read", None)
        assert result["verdict"] == "ALLOW"


# ------------------------------------------------------------------ #
# Unit: constitution.yaml structure                                   #
# ------------------------------------------------------------------ #

@pytest.mark.unit
class TestConstitutionYAML:

    def test_constitution_loads(self):
        from agenticqa.constitutional_gate import get_constitution
        c = get_constitution()
        assert c, "Constitution must not be empty"

    def test_constitution_has_required_keys(self):
        from agenticqa.constitutional_gate import get_constitution
        c = get_constitution()
        assert "version" in c
        assert "tier_1" in c
        assert "tier_2" in c
        assert "tier_3" in c

    def test_tier1_laws_have_required_fields(self):
        from agenticqa.constitutional_gate import get_constitution
        c = get_constitution()
        for law in c["tier_1"]:
            assert "id" in law, f"Missing 'id' in tier_1 law: {law}"
            assert "name" in law, f"Missing 'name' in tier_1 law: {law}"
            assert "description" in law, f"Missing 'description' in {law['id']}"
            assert "verdict" in law, f"Missing 'verdict' in {law['id']}"
            assert law["verdict"] == "DENY"

    def test_tier2_laws_have_required_fields(self):
        from agenticqa.constitutional_gate import get_constitution
        c = get_constitution()
        for law in c["tier_2"]:
            assert "id" in law
            assert "name" in law
            assert law.get("verdict") == "REQUIRE_APPROVAL"

    def test_minimum_law_counts(self):
        from agenticqa.constitutional_gate import get_constitution
        c = get_constitution()
        assert len(c["tier_1"]) >= 5, "Expected at least 5 Tier 1 laws"
        assert len(c["tier_2"]) >= 2, "Expected at least 2 Tier 2 laws"
        assert len(c["tier_3"]) >= 1, "Expected at least 1 Tier 3 escalation trigger"

    def test_agent_rights_present(self):
        from agenticqa.constitutional_gate import get_constitution
        c = get_constitution()
        assert "agent_rights" in c
        assert len(c["agent_rights"]) >= 1


# ------------------------------------------------------------------ #
# API: constitution endpoints                                         #
# ------------------------------------------------------------------ #

import agent_api

@pytest.fixture
def client():
    return TestClient(agent_api.app)


@pytest.mark.unit
class TestConstitutionEndpoints:

    def test_get_constitution_returns_structure(self, client):
        response = client.get("/api/system/constitution")
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["version"] is not None
        assert data["tier_1_count"] >= 5
        assert data["tier_2_count"] >= 2
        assert "constitution" in data
        assert "tier_1" in data["constitution"]
        assert "tier_2" in data["constitution"]

    def test_get_constitution_includes_agent_rights(self, client):
        response = client.get("/api/system/constitution")
        assert response.status_code == 200
        data = response.json()
        rights = data["constitution"].get("agent_rights", [])
        assert len(rights) >= 1

    def test_constitutional_check_allow(self, client):
        response = client.post("/api/system/constitution/check", json={
            "action_type": "read",
            "context": {"trace_id": "tr-test"},
        })
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["verdict"] == "ALLOW"
        assert data["law"] is None

    def test_constitutional_check_deny_destructive(self, client):
        response = client.post("/api/system/constitution/check", json={
            "action_type": "delete",
            "context": {"ci_status": "FAILED", "trace_id": "tr-test"},
        })
        assert response.status_code == 200
        data = response.json()
        assert data["verdict"] == "DENY"
        assert data["law"] == "T1-001"
        assert data["reason"]

    def test_constitutional_check_require_approval(self, client):
        response = client.post("/api/system/constitution/check", json={
            "action_type": "deploy",
            "context": {
                "environment": "production",
                "ci_status": "PASSED",
                "trace_id": "tr-test",
            },
        })
        assert response.status_code == 200
        data = response.json()
        assert data["verdict"] == "REQUIRE_APPROVAL"
        assert data["law"] == "T2-001"

    def test_constitutional_check_delegation_denied_at_depth_3(self, client):
        response = client.post("/api/system/constitution/check", json={
            "action_type": "delegate",
            "context": {"delegation_depth": 3, "trace_id": "tr-test"},
        })
        assert response.status_code == 200
        data = response.json()
        assert data["verdict"] == "DENY"
        assert data["law"] == "T1-002"

    def test_constitutional_check_empty_context_returns_verdict(self, client):
        response = client.post("/api/system/constitution/check", json={
            "action_type": "read",
        })
        assert response.status_code == 200
        assert "verdict" in response.json()
