"""Tests for TenantIsolationGuard — per-tenant namespace enforcement."""
import pytest

from agenticqa.security.tenant_isolation import TenantIsolationGuard, derive_tenant_id


pytestmark = pytest.mark.unit


class TestDeriveTenantId:
    """Tests for the derive_tenant_id helper."""

    def test_returns_hex_string(self):
        tid = derive_tenant_id("https://github.com/org/repo.git")
        assert len(tid) == 16
        assert all(c in "0123456789abcdef" for c in tid)

    def test_deterministic(self):
        a = derive_tenant_id("https://github.com/org/repo.git")
        b = derive_tenant_id("https://github.com/org/repo.git")
        assert a == b

    def test_different_repos_different_ids(self):
        a = derive_tenant_id("https://github.com/org/repo-a.git")
        b = derive_tenant_id("https://github.com/org/repo-b.git")
        assert a != b


class TestTenantIsolationGuard:
    """Unit tests for TenantIsolationGuard."""

    def test_init_with_tenant_id(self):
        guard = TenantIsolationGuard(tenant_id="abc123")
        assert guard.tenant_id == "abc123"
        assert guard.strict is False

    def test_init_strict_without_tenant_raises(self):
        with pytest.raises(ValueError, match="without a tenant_id"):
            TenantIsolationGuard(tenant_id="", strict=True)

    def test_init_permissive_without_tenant_warns(self, caplog):
        import logging
        with caplog.at_level(logging.WARNING):
            guard = TenantIsolationGuard(tenant_id="", strict=False)
        assert "without a tenant_id" in caplog.text

    # ── tag_document() ────────────────────────────────────────────────────

    def test_tag_document_adds_tenant_field(self):
        guard = TenantIsolationGuard(tenant_id="tenant-x")
        meta = {"title": "doc1", "source": "test"}
        tagged = guard.tag_document(meta)
        assert tagged["_tenant_id"] == "tenant-x"
        assert tagged["title"] == "doc1"
        # Original not mutated
        assert "_tenant_id" not in meta

    # ── check_document() ──────────────────────────────────────────────────

    def test_check_document_matching_tenant(self):
        guard = TenantIsolationGuard(tenant_id="t1")
        assert guard.check_document({"_tenant_id": "t1"}) is True

    def test_check_document_mismatched_tenant_permissive(self, caplog):
        import logging
        guard = TenantIsolationGuard(tenant_id="t1", strict=False)
        with caplog.at_level(logging.WARNING):
            result = guard.check_document({"_tenant_id": "t2"})
        assert result is False
        assert "mismatch" in caplog.text

    def test_check_document_mismatched_tenant_strict(self):
        guard = TenantIsolationGuard(tenant_id="t1", strict=True)
        with pytest.raises(PermissionError, match="mismatch"):
            guard.check_document({"_tenant_id": "t2"})

    def test_check_document_no_tenant_set_allows_all(self):
        guard = TenantIsolationGuard(tenant_id="")
        assert guard.check_document({"_tenant_id": "anything"}) is True
        assert guard.check_document({}) is True

    # ── filter_documents() ────────────────────────────────────────────────

    def test_filter_documents_keeps_matching(self):
        guard = TenantIsolationGuard(tenant_id="t1")
        docs = [
            {"_tenant_id": "t1", "text": "doc1"},
            {"_tenant_id": "t2", "text": "doc2"},
            {"_tenant_id": "t1", "text": "doc3"},
        ]
        filtered = guard.filter_documents(docs)
        assert len(filtered) == 2
        assert all(d["_tenant_id"] == "t1" for d in filtered)

    def test_filter_documents_no_tenant_returns_all(self):
        guard = TenantIsolationGuard(tenant_id="")
        docs = [{"_tenant_id": "t1"}, {"_tenant_id": "t2"}]
        assert len(guard.filter_documents(docs)) == 2

    # ── qdrant_filter() ───────────────────────────────────────────────────

    def test_qdrant_filter_with_tenant(self):
        guard = TenantIsolationGuard(tenant_id="abc")
        f = guard.qdrant_filter()
        assert f is not None
        assert f["must"][0]["key"] == "_tenant_id"
        assert f["must"][0]["match"]["value"] == "abc"

    def test_qdrant_filter_no_tenant_returns_none(self):
        guard = TenantIsolationGuard(tenant_id="")
        assert guard.qdrant_filter() is None

    # ── weaviate_where() ──────────────────────────────────────────────────

    def test_weaviate_where_with_tenant(self):
        guard = TenantIsolationGuard(tenant_id="def")
        w = guard.weaviate_where()
        assert w is not None
        assert w["path"] == ["_tenant_id"]
        assert w["operator"] == "Equal"
        assert w["valueText"] == "def"

    def test_weaviate_where_no_tenant_returns_none(self):
        guard = TenantIsolationGuard(tenant_id="")
        assert guard.weaviate_where() is None

    # ── validate_query_context() ──────────────────────────────────────────

    def test_validate_context_matching(self):
        guard = TenantIsolationGuard(tenant_id="t1")
        assert guard.validate_query_context({"tenant_id": "t1"}) is True

    def test_validate_context_with_underscore_field(self):
        guard = TenantIsolationGuard(tenant_id="t1")
        assert guard.validate_query_context({"_tenant_id": "t1"}) is True

    def test_validate_context_missing_tenant_permissive(self):
        guard = TenantIsolationGuard(tenant_id="t1", strict=False)
        assert guard.validate_query_context({}) is False

    def test_validate_context_missing_tenant_strict(self):
        guard = TenantIsolationGuard(tenant_id="t1", strict=True)
        with pytest.raises(ValueError, match="missing tenant_id"):
            guard.validate_query_context({})

    def test_validate_context_mismatched_strict(self):
        guard = TenantIsolationGuard(tenant_id="t1", strict=True)
        with pytest.raises(PermissionError):
            guard.validate_query_context({"tenant_id": "t2"})
