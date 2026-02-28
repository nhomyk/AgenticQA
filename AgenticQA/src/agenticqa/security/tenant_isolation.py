"""
TenantIsolationGuard — enforces per-tenant namespace in vector store queries.

Problem
-------
AgenticQA's Qdrant and Weaviate stores are shared across all repositories.
Without tenant isolation:
- Repo A's confidential code review insights can surface in Repo B's RAG results
- One client's "failing tests" could be returned as similar patterns for another client
- Developer risk profiles could bleed across organizational boundaries

Solution
--------
Every vector store query and write carries a ``tenant_id`` derived from the
repository identifier (git remote URL hash).  The guard:

1. Tags every document payload with ``_tenant_id`` before writing.
2. Adds a ``must`` filter for ``_tenant_id`` to every query.
3. Warns (in permissive mode) or raises (in strict mode) when a
   query is attempted without a tenant_id.

This is a middleware/wrapper layer — it does not modify the underlying
VectorStore implementation; callers pass the guard into their retrieval
logic.

Usage
-----
    from agenticqa.security.tenant_isolation import TenantIsolationGuard

    guard = TenantIsolationGuard(tenant_id="repo-abc123", strict=False)

    # Wrap a metadata dict before writing
    safe_meta = guard.tag_document(metadata)

    # Build a tenant filter to add to Qdrant/Weaviate queries
    tenant_filter = guard.qdrant_filter()    # → Qdrant Filter object (or dict)
    weaviate_where = guard.weaviate_where()  # → Weaviate where clause dict

    # Validate a retrieved document belongs to this tenant
    ok = guard.check_document(doc_metadata)
"""

from __future__ import annotations

import hashlib
import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

_TENANT_FIELD = "_tenant_id"


def derive_tenant_id(repo_identifier: str) -> str:
    """
    Derive a stable tenant ID from a repository identifier (git URL, path, etc.).
    Returns the first 16 hex chars of SHA-256(repo_identifier).
    """
    return hashlib.sha256(repo_identifier.encode()).hexdigest()[:16]


class TenantIsolationGuard:
    """
    Guards vector store operations with per-tenant namespace enforcement.

    Args:
        tenant_id:  explicit tenant ID string (use derive_tenant_id() to get one).
        strict:     if True, raise ValueError when tenant_id is missing/mismatched.
                    if False (default), log a warning and continue.
    """

    def __init__(self, tenant_id: str = "", strict: bool = False) -> None:
        self.tenant_id = tenant_id
        self.strict = strict

        if not tenant_id:
            msg = (
                "TenantIsolationGuard created without a tenant_id — "
                "all queries will be unscoped; cross-tenant data leakage is possible"
            )
            if strict:
                raise ValueError(msg)
            logger.warning(msg)

    # ── Document tagging ─────────────────────────────────────────────────

    def tag_document(self, metadata: Dict[str, Any]) -> Dict[str, Any]:
        """Return a copy of metadata with _tenant_id added."""
        return {**metadata, _TENANT_FIELD: self.tenant_id}

    def check_document(self, metadata: Dict[str, Any]) -> bool:
        """
        Return True if metadata belongs to this tenant.

        If no tenant_id is configured, always returns True (permissive mode).
        """
        if not self.tenant_id:
            return True
        doc_tenant = metadata.get(_TENANT_FIELD, "")
        if doc_tenant == self.tenant_id:
            return True
        msg = (
            f"Document tenant mismatch: expected '{self.tenant_id}' "
            f"got '{doc_tenant}' — possible cross-tenant data leak"
        )
        if self.strict:
            raise PermissionError(msg)
        logger.warning(msg)
        return False

    def filter_documents(
        self, docs: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Filter a list of retrieved documents to only those matching this tenant."""
        if not self.tenant_id:
            return docs
        return [d for d in docs if d.get(_TENANT_FIELD, "") == self.tenant_id]

    # ── Query filter builders ─────────────────────────────────────────────

    def qdrant_filter(self) -> Optional[Dict[str, Any]]:
        """
        Return a Qdrant-compatible filter dict that restricts results to
        this tenant.  Pass to QdrantClient.search(..., query_filter=...).

        Returns None if no tenant_id is set (no filtering applied).
        """
        if not self.tenant_id:
            return None
        return {
            "must": [
                {
                    "key": _TENANT_FIELD,
                    "match": {"value": self.tenant_id},
                }
            ]
        }

    def weaviate_where(self) -> Optional[Dict[str, Any]]:
        """
        Return a Weaviate-compatible where clause dict.
        Pass to weaviate.query.get(...).with_where(...).

        Returns None if no tenant_id is set.
        """
        if not self.tenant_id:
            return None
        return {
            "path": [_TENANT_FIELD],
            "operator": "Equal",
            "valueText": self.tenant_id,
        }

    def validate_query_context(self, context: Dict[str, Any]) -> bool:
        """
        Check that a query context dict contains a tenant_id field and it
        matches this guard's tenant.  Useful for validating API call payloads.
        """
        ctx_tenant = context.get("tenant_id", context.get(_TENANT_FIELD, ""))
        if not ctx_tenant:
            msg = "Query context missing tenant_id — query will be unscoped"
            if self.strict:
                raise ValueError(msg)
            logger.warning(msg)
            return False
        if ctx_tenant != self.tenant_id:
            msg = f"Query tenant '{ctx_tenant}' ≠ guard tenant '{self.tenant_id}'"
            if self.strict:
                raise PermissionError(msg)
            logger.warning(msg)
            return False
        return True
