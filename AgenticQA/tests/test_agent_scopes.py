"""Tests for Agent File Scope enforcement (T1-006).

Covers:
- check_file_scope(): ALLOW and DENY for all 7 agents
- Pattern matching: directory globs, extension globs, exact files, deny overrides
- check_action() integration: scope fires when agent + target_path in context
- API: GET /api/system/agent-scopes, POST /api/system/agent-scopes/check
- agent_scopes.yaml structure validation
"""

import sys
import os

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))


# ------------------------------------------------------------------ #
# Helpers
# ------------------------------------------------------------------ #

def _scope(agent, action, path):
    from agenticqa.constitutional_gate import check_file_scope
    return check_file_scope(agent, action, path)


def _check(action, context):
    from agenticqa.constitutional_gate import check_action
    return check_action(action, context)


# ------------------------------------------------------------------ #
# Unit: SDET_Agent
# ------------------------------------------------------------------ #

@pytest.mark.unit
class TestSDETScope:

    def test_allow_write_to_tests(self):
        assert _scope("SDET_Agent", "write", "tests/test_api.py")["verdict"] == "ALLOW"

    def test_allow_write_conftest(self):
        assert _scope("SDET_Agent", "write", "conftest.py")["verdict"] == "ALLOW"

    def test_allow_read_src(self):
        assert _scope("SDET_Agent", "read", "src/agents.py")["verdict"] == "ALLOW"

    def test_deny_write_github_workflow(self):
        r = _scope("SDET_Agent", "write", ".github/workflows/ci.yml")
        assert r["verdict"] == "DENY"
        assert r["law"] == "T1-006"
        assert r["name"] == "agent_file_scope_violation"

    def test_deny_write_yml_at_root(self):
        r = _scope("SDET_Agent", "write", "docker-compose.yml")
        assert r["verdict"] == "DENY"

    def test_deny_write_dockerfile(self):
        assert _scope("SDET_Agent", "write", "Dockerfile")["verdict"] == "DENY"

    def test_deny_write_makefile(self):
        assert _scope("SDET_Agent", "write", "Makefile")["verdict"] == "DENY"

    def test_deny_write_src_file(self):
        # SDET can read src but not write it
        assert _scope("SDET_Agent", "write", "src/main.py")["verdict"] == "DENY"

    def test_deny_write_shell_script(self):
        assert _scope("SDET_Agent", "write", "scripts/deploy.sh")["verdict"] == "DENY"


# ------------------------------------------------------------------ #
# Unit: SRE_Agent
# ------------------------------------------------------------------ #

@pytest.mark.unit
class TestSREScope:

    def test_allow_write_github_workflow(self):
        assert _scope("SRE_Agent", "write", ".github/workflows/deploy.yml")["verdict"] == "ALLOW"

    def test_allow_write_dockerfile(self):
        assert _scope("SRE_Agent", "write", "Dockerfile")["verdict"] == "ALLOW"

    def test_allow_write_shell_script(self):
        assert _scope("SRE_Agent", "write", "scripts/setup.sh")["verdict"] == "ALLOW"

    def test_allow_write_makefile(self):
        assert _scope("SRE_Agent", "write", "Makefile")["verdict"] == "ALLOW"

    def test_allow_read_src(self):
        assert _scope("SRE_Agent", "read", "src/agents.py")["verdict"] == "ALLOW"

    def test_deny_write_src(self):
        r = _scope("SRE_Agent", "write", "src/main.py")
        assert r["verdict"] == "DENY"
        assert r["law"] == "T1-006"

    def test_deny_write_tests(self):
        assert _scope("SRE_Agent", "write", "tests/test_api.py")["verdict"] == "DENY"

    def test_deny_write_frontend(self):
        # Not in write patterns — implicitly denied
        assert _scope("SRE_Agent", "write", "frontend/app.js")["verdict"] == "DENY"

    def test_deny_write_dashboard(self):
        # Not in write patterns — implicitly denied
        assert _scope("SRE_Agent", "write", "dashboard/app.py")["verdict"] == "DENY"


# ------------------------------------------------------------------ #
# Unit: Compliance_Agent (read-only enforced)
# ------------------------------------------------------------------ #

@pytest.mark.unit
class TestComplianceScope:

    def test_allow_read_everything(self):
        for path in ["src/main.py", ".github/workflows/ci.yml", "tests/test_api.py", "Dockerfile"]:
            assert _scope("Compliance_Agent", "read", path)["verdict"] == "ALLOW", f"Failed for {path}"

    def test_deny_write_anything(self):
        for path in ["src/main.py", "tests/test.py", "README.md", "reports/out.txt"]:
            r = _scope("Compliance_Agent", "write", path)
            assert r["verdict"] == "DENY", f"Expected DENY for write to {path}"
            assert r["law"] == "T1-006"

    def test_deny_delete_anything(self):
        assert _scope("Compliance_Agent", "delete", "src/main.py")["verdict"] == "DENY"


# ------------------------------------------------------------------ #
# Unit: Fullstack_Agent
# ------------------------------------------------------------------ #

@pytest.mark.unit
class TestFullstackScope:

    def test_allow_write_src(self):
        assert _scope("Fullstack_Agent", "write", "src/api/routes.py")["verdict"] == "ALLOW"

    def test_allow_write_frontend(self):
        assert _scope("Fullstack_Agent", "write", "frontend/components/Button.tsx")["verdict"] == "ALLOW"

    def test_deny_write_github(self):
        assert _scope("Fullstack_Agent", "write", ".github/workflows/ci.yml")["verdict"] == "DENY"

    def test_deny_write_tests(self):
        assert _scope("Fullstack_Agent", "write", "tests/test_routes.py")["verdict"] == "DENY"

    def test_deny_write_dockerfile(self):
        assert _scope("Fullstack_Agent", "write", "Dockerfile")["verdict"] == "DENY"

    def test_deny_write_makefile(self):
        assert _scope("Fullstack_Agent", "write", "Makefile")["verdict"] == "DENY"


# ------------------------------------------------------------------ #
# Unit: DevOps_Agent
# ------------------------------------------------------------------ #

@pytest.mark.unit
class TestDevOpsScope:

    def test_allow_write_k8s(self):
        assert _scope("DevOps_Agent", "write", "k8s/deployment.yaml")["verdict"] == "ALLOW"

    def test_allow_write_dockerfile(self):
        assert _scope("DevOps_Agent", "write", "Dockerfile")["verdict"] == "ALLOW"

    def test_allow_write_github_workflow(self):
        assert _scope("DevOps_Agent", "write", ".github/workflows/deploy.yml")["verdict"] == "ALLOW"

    def test_deny_write_src(self):
        assert _scope("DevOps_Agent", "write", "src/main.py")["verdict"] == "DENY"

    def test_deny_write_tests(self):
        assert _scope("DevOps_Agent", "write", "tests/test_api.py")["verdict"] == "DENY"

    def test_deny_write_frontend(self):
        assert _scope("DevOps_Agent", "write", "frontend/index.html")["verdict"] == "DENY"


# ------------------------------------------------------------------ #
# Unit: QA_Agent and Performance_Agent
# ------------------------------------------------------------------ #

@pytest.mark.unit
class TestQAAndPerfScope:

    def test_qa_allow_write_reports(self):
        assert _scope("QA_Agent", "write", "reports/summary.json")["verdict"] == "ALLOW"

    def test_qa_deny_write_src(self):
        assert _scope("QA_Agent", "write", "src/main.py")["verdict"] == "DENY"

    def test_perf_allow_write_benchmarks(self):
        assert _scope("Performance_Agent", "write", "benchmarks/results.json")["verdict"] == "ALLOW"

    def test_perf_deny_write_src(self):
        assert _scope("Performance_Agent", "write", "src/main.py")["verdict"] == "DENY"

    def test_perf_deny_write_tests(self):
        assert _scope("Performance_Agent", "write", "tests/test_api.py")["verdict"] == "DENY"


# ------------------------------------------------------------------ #
# Unit: Edge cases
# ------------------------------------------------------------------ #

@pytest.mark.unit
class TestScopeEdgeCases:

    def test_unknown_agent_allow(self):
        """Agents not declared in scopes default to ALLOW (open-world)."""
        r = _scope("UnknownAgent", "write", "src/main.py")
        assert r["verdict"] == "ALLOW"
        assert r["law"] is None

    def test_deny_takes_precedence_over_read(self):
        """Deny patterns beat read patterns for Compliance_Agent."""
        r = _scope("Compliance_Agent", "write", "reports/out.txt")
        assert r["verdict"] == "DENY"

    def test_nested_path_matched_by_glob(self):
        assert _scope("SDET_Agent", "write", "tests/unit/sub/test_foo.py")["verdict"] == "ALLOW"

    def test_dotgithub_nested_denied_for_sdet(self):
        assert _scope("SDET_Agent", "write", ".github/workflows/build/ci.yml")["verdict"] == "DENY"

    def test_reason_contains_agent_name(self):
        r = _scope("SDET_Agent", "write", ".github/workflows/ci.yml")
        assert "SDET_Agent" in r["reason"]

    def test_reason_contains_file_path(self):
        r = _scope("SDET_Agent", "write", ".github/workflows/ci.yml")
        assert ".github/workflows/ci.yml" in r["reason"]


# ------------------------------------------------------------------ #
# Unit: check_action integration
# ------------------------------------------------------------------ #

@pytest.mark.unit
class TestCheckActionScopeIntegration:

    def test_scope_fires_via_check_action(self):
        """check_action with agent + target_path triggers T1-006."""
        r = _check("write", {
            "agent": "SDET_Agent",
            "target_path": ".github/workflows/ci.yml",
            "trace_id": "tr-001",
        })
        assert r["verdict"] == "DENY"
        assert r["law"] == "T1-006"

    def test_scope_passes_via_check_action(self):
        r = _check("write", {
            "agent": "SDET_Agent",
            "target_path": "tests/test_new.py",
            "trace_id": "tr-001",
        })
        assert r["verdict"] == "ALLOW"

    def test_no_scope_check_without_agent(self):
        """Missing agent key → scope check skipped."""
        r = _check("write", {"target_path": ".github/workflows/ci.yml", "trace_id": "tr-001"})
        assert r["verdict"] == "ALLOW"

    def test_no_scope_check_without_target_path(self):
        """Missing target_path → scope check skipped."""
        r = _check("write", {"agent": "SDET_Agent", "trace_id": "tr-001"})
        assert r["verdict"] == "ALLOW"

    def test_t1_laws_still_fire_before_scope(self):
        """Existing T1 laws evaluated before scope check."""
        r = _check("delete", {
            "agent": "SRE_Agent",
            "target_path": ".github/workflows/deploy.yml",
            "ci_status": "FAILED",
            "trace_id": "tr-001",
        })
        # T1-001 fires first (destructive without CI pass)
        assert r["verdict"] == "DENY"
        assert r["law"] == "T1-001"

    def test_compliance_deny_via_check_action(self):
        r = _check("write", {
            "agent": "Compliance_Agent",
            "target_path": "reports/audit.json",
            "trace_id": "tr-001",
        })
        assert r["verdict"] == "DENY"
        assert r["law"] == "T1-006"


# ------------------------------------------------------------------ #
# Unit: agent_scopes.yaml structure
# ------------------------------------------------------------------ #

@pytest.mark.unit
class TestAgentScopesYAML:

    def test_all_7_agents_declared(self):
        from agenticqa.constitutional_gate import get_agent_scopes
        scopes = get_agent_scopes()
        expected = {"SDET_Agent", "SRE_Agent", "Fullstack_Agent",
                    "Compliance_Agent", "DevOps_Agent", "QA_Agent", "Performance_Agent"}
        assert expected.issubset(set(scopes.keys())), f"Missing agents: {expected - set(scopes.keys())}"

    def test_each_agent_has_required_keys(self):
        from agenticqa.constitutional_gate import get_agent_scopes
        for agent, scope in get_agent_scopes().items():
            assert "read" in scope, f"{agent} missing 'read'"
            assert "write" in scope, f"{agent} missing 'write'"
            assert "deny" in scope, f"{agent} missing 'deny'"

    def test_compliance_has_no_write_patterns(self):
        from agenticqa.constitutional_gate import get_agent_scopes
        scopes = get_agent_scopes()
        assert scopes["Compliance_Agent"]["write"] == [], "Compliance must be read-only"

    def test_sdet_cannot_write_github(self):
        from agenticqa.constitutional_gate import get_agent_scopes
        scopes = get_agent_scopes()
        deny = scopes["SDET_Agent"]["deny"]
        assert any(".github" in p for p in deny), "SDET must deny .github/**"


# ------------------------------------------------------------------ #
# API: agent-scopes endpoints
# ------------------------------------------------------------------ #

import agent_api

@pytest.fixture
def client():
    return TestClient(agent_api.app)


@pytest.mark.unit
class TestAgentScopesEndpoints:

    def test_get_agent_scopes_returns_all_agents(self, client):
        response = client.get("/api/system/agent-scopes")
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["agent_count"] >= 7
        agent_names = [a["agent"] for a in data["agents"]]
        assert "SDET_Agent" in agent_names
        assert "Compliance_Agent" in agent_names

    def test_get_agent_scopes_compliance_is_readonly(self, client):
        response = client.get("/api/system/agent-scopes")
        data = response.json()
        compliance = next(a for a in data["agents"] if a["agent"] == "Compliance_Agent")
        assert compliance["read_only"] is True
        assert compliance["write_patterns"] == []

    def test_scope_check_deny_sdet_github(self, client):
        response = client.post("/api/system/agent-scopes/check", json={
            "agent": "SDET_Agent",
            "action": "write",
            "file_path": ".github/workflows/ci.yml",
        })
        assert response.status_code == 200
        data = response.json()
        assert data["verdict"] == "DENY"
        assert data["law"] == "T1-006"
        assert data["reason"]

    def test_scope_check_allow_sdet_tests(self, client):
        response = client.post("/api/system/agent-scopes/check", json={
            "agent": "SDET_Agent",
            "action": "write",
            "file_path": "tests/test_new_feature.py",
        })
        assert response.status_code == 200
        assert response.json()["verdict"] == "ALLOW"

    def test_scope_check_deny_compliance_write(self, client):
        response = client.post("/api/system/agent-scopes/check", json={
            "agent": "Compliance_Agent",
            "action": "write",
            "file_path": "reports/audit.json",
        })
        assert response.status_code == 200
        assert response.json()["verdict"] == "DENY"

    def test_scope_check_allow_sre_workflow(self, client):
        response = client.post("/api/system/agent-scopes/check", json={
            "agent": "SRE_Agent",
            "action": "write",
            "file_path": ".github/workflows/deploy.yml",
        })
        assert response.status_code == 200
        assert response.json()["verdict"] == "ALLOW"

    def test_constitution_now_has_t1_006(self, client):
        response = client.get("/api/system/constitution")
        assert response.status_code == 200
        tier1 = response.json()["constitution"]["tier_1"]
        ids = [law["id"] for law in tier1]
        assert "T1-006" in ids

    def test_constitution_tier1_count_updated(self, client):
        response = client.get("/api/system/constitution")
        assert response.json()["tier_1_count"] >= 6
