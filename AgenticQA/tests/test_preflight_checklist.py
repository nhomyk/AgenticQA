"""Unit tests for PreflightChecklistGenerator — @pytest.mark.unit"""
import pytest

from agenticqa.security.preflight_checklist import (
    ChecklistItem,
    PreflightChecklist,
    PreflightChecklistGenerator,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def gen() -> PreflightChecklistGenerator:
    return PreflightChecklistGenerator()


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

@pytest.mark.unit
class TestPreflightChecklistGenerator:

    def test_auth_file_triggers_auth_items(self):
        result = gen().generate(["src/auth/login.py"])
        categories = result.categories_triggered
        assert "AUTH" in categories
        items_text = [i.item for i in result.items]
        assert "Verify MFA/2FA flows still work end-to-end" in items_text

    def test_database_migration_triggers_db_items(self):
        result = gen().generate(["migrations/0042_add_users.py"])
        assert "DATABASE" in result.categories_triggered
        items_text = [i.item for i in result.items]
        assert "Verify migration is reversible (test rollback)" in items_text

    def test_api_route_triggers_api_items(self):
        result = gen().generate(["src/api/user_endpoint.py"])
        assert "API" in result.categories_triggered
        items_text = [i.item for i in result.items]
        assert "Verify all new endpoints require authentication" in items_text

    def test_security_file_triggers_security_items(self):
        result = gen().generate(["src/security/crypto_utils.py"])
        assert "SECURITY" in result.categories_triggered
        items_text = [i.item for i in result.items]
        assert "Run OWASP Top 10 scan against changed code" in items_text

    def test_mcp_tool_triggers_mcp_items(self):
        result = gen().generate(["src/mcp/tool_runner.py"])
        assert "MCP_AGENT" in result.categories_triggered
        items_text = [i.item for i in result.items]
        assert "Verify new tools have input validation" in items_text

    def test_empty_changed_files_returns_empty_checklist(self):
        result = gen().generate([])
        assert result.items == []
        assert result.categories_triggered == []

    def test_no_duplicates_on_multiple_matches(self):
        # auth + login both trigger AUTH; items should only appear once
        result = gen().generate(["auth_login_session.py"])
        item_texts = [i.item for i in result.items]
        assert len(item_texts) == len(set(item_texts))

    def test_must_items_property(self):
        result = gen().generate(["src/auth/login.py"])
        must = result.must_items
        assert all(i.priority == "MUST" for i in must)
        assert len(must) > 0

    def test_should_items_property(self):
        result = gen().generate(["src/auth/login.py"])
        should = result.should_items
        assert all(i.priority == "SHOULD" for i in should)

    def test_markdown_report_format(self):
        result = gen().generate(["src/auth/login.py"])
        md = result.markdown_report()
        assert "# Pre-flight Deploy Checklist" in md
        assert "## MUST" in md
        assert "- [ ]" in md

    def test_to_dict_fields(self):
        result = gen().generate(["src/api/routes.py"])
        d = result.to_dict()
        assert "changed_files" in d
        assert "items" in d
        assert "categories_triggered" in d
        assert "must_items" in d
        assert "should_items" in d

    def test_triggered_by_populated(self):
        result = gen().generate(["src/auth/login.py"])
        auth_items = [i for i in result.items if i.category == "AUTH"]
        assert len(auth_items) > 0
        assert all(i.triggered_by != "" for i in auth_items)

    def test_categories_triggered_list(self):
        result = gen().generate(["auth_service.py", "api_routes.py"])
        assert "AUTH" in result.categories_triggered
        assert "API" in result.categories_triggered

    def test_diff_content_triggers_items_not_just_filename(self):
        # File name is boring, but diff mentions 'session'
        result = gen().generate(
            ["utils/helpers.py"],
            diff_content="+ session = create_session(user)\n+ session.expire_at = ...",
        )
        assert "AUTH" in result.categories_triggered

    def test_compliance_pattern_triggers_compliance_items(self):
        result = gen().generate(["src/users/pii_handler.py"])
        assert "COMPLIANCE" in result.categories_triggered
        items_text = [i.item for i in result.items]
        assert "Verify PII is not logged in plaintext" in items_text

    def test_performance_pattern_triggers_perf_items(self):
        result = gen().generate(["src/cache/redis_client.py"])
        assert "PERFORMANCE" in result.categories_triggered
        items_text = [i.item for i in result.items]
        assert "Run load test against changed endpoints" in items_text

    def test_clean_unrelated_files_empty_checklist(self):
        result = gen().generate(["README.md", "setup.cfg", "pyproject.toml"])
        assert result.items == []

    def test_checklist_item_to_dict(self):
        item = ChecklistItem(
            category="AUTH",
            item="Check MFA",
            priority="MUST",
            triggered_by="auth",
        )
        d = item.to_dict()
        assert d["category"] == "AUTH"
        assert d["item"] == "Check MFA"
        assert d["priority"] == "MUST"
        assert d["triggered_by"] == "auth"
