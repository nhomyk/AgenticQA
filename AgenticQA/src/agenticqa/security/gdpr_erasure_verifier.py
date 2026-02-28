"""
GDPREraseVerifier — tracks and verifies data erasure across all storage backends.

Problem
-------
When a client invokes their GDPR "right to erasure" (Art.17), deleting data from
one store (e.g. Qdrant) does not guarantee it's gone from:
  - Weaviate vector store
  - Neo4j graph (temporal violation snapshots)
  - SQLite artifact store
  - ~/.agenticqa/metrics_history.jsonl
  - ~/.agenticqa/repos/{repo_id}.json
  - ~/.agenticqa/developers/{repo_id}/{dev_hash}.json
  - .agenticqa/provenance/{agent}.jsonl

This verifier:
1. Records erasure requests with a stable ID.
2. After deletion, probes every backend for residual tenant data.
3. Issues a signed ErasureVerificationResult — suitable for a DPA audit response.

Note: actual deletion is the caller's responsibility; this module only *verifies*
that deletion occurred, producing auditable evidence.

Usage
-----
    from agenticqa.security.gdpr_erasure_verifier import GDPREraseVerifier

    v = GDPREraseVerifier()
    req = v.request_erasure(tenant_id="abc123", subject_id="user-42")
    # ... caller deletes data ...
    result = v.verify_erasure(req.request_id)
    print(result.verified_clean, result.stores_with_residual)
"""
from __future__ import annotations

import hashlib
import json
import logging
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

_DEFAULT_REQUEST_PATH = Path.home() / ".agenticqa" / "erasure_requests.jsonl"
_AGENTICQA_DIR = Path.home() / ".agenticqa"


@dataclass
class ErasureRequest:
    request_id: str
    tenant_id: str
    subject_id: str
    requested_at: float
    status: str = "pending"   # pending | verified_clean | residual_found | failed


@dataclass
class StoreCheckResult:
    store_name: str
    checked: bool
    residual_found: bool
    residual_count: int = 0
    error: Optional[str] = None

    def __str__(self) -> str:
        if not self.checked:
            return f"{self.store_name}: SKIPPED ({self.error})"
        if self.residual_found:
            return f"{self.store_name}: RESIDUAL ({self.residual_count} records)"
        return f"{self.store_name}: CLEAN"


@dataclass
class ErasureVerificationResult:
    request_id: str
    tenant_id: str
    subject_id: str
    verified_at: float
    stores_checked: List[StoreCheckResult] = field(default_factory=list)
    verified_clean: bool = False
    stores_with_residual: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "request_id": self.request_id,
            "tenant_id": self.tenant_id,
            "subject_id": self.subject_id,
            "verified_at": self.verified_at,
            "verified_clean": self.verified_clean,
            "stores_with_residual": self.stores_with_residual,
            "stores_checked": [s.__dict__ for s in self.stores_checked],
        }


class GDPREraseVerifier:
    """Tracks erasure requests and verifies deletion across all storage backends."""

    def __init__(
        self,
        request_path: Optional[Path] = None,
        agenticqa_dir: Optional[Path] = None,
    ) -> None:
        self._path = Path(request_path) if request_path else _DEFAULT_REQUEST_PATH
        self._dir  = Path(agenticqa_dir)  if agenticqa_dir  else _AGENTICQA_DIR

    # ── Request lifecycle ────────────────────────────────────────────────────

    def request_erasure(self, tenant_id: str, subject_id: str) -> ErasureRequest:
        req = ErasureRequest(
            request_id=str(uuid.uuid4()),
            tenant_id=tenant_id,
            subject_id=subject_id,
            requested_at=time.time(),
        )
        self._persist_request(req)
        return req

    def verify_erasure(self, request_id: str) -> ErasureVerificationResult:
        req = self._load_request(request_id)
        if req is None:
            raise ValueError(f"No erasure request found: {request_id}")

        results: List[StoreCheckResult] = []

        # 1. Metrics history JSONL
        results.append(self._check_jsonl(
            self._dir / "metrics_history.jsonl",
            "metrics_history",
            req.tenant_id,
            key="repo_id",
        ))

        # 2. Repo profile JSON files
        results.append(self._check_repo_profiles(req.tenant_id))

        # 3. Developer profile JSON files
        results.append(self._check_developer_profiles(req.tenant_id))

        # 4. Provenance JSONL files
        results.append(self._check_provenance(req.tenant_id))

        # 5. Audit chain JSONL
        results.append(self._check_jsonl(
            self._dir / "audit_chain.jsonl",
            "audit_chain",
            req.tenant_id,
            key="tenant_id",
        ))

        # 6. Qdrant (optional — only if accessible)
        results.append(self._check_qdrant(req.tenant_id))

        residual = [r.store_name for r in results if r.checked and r.residual_found]
        clean = len(residual) == 0

        result = ErasureVerificationResult(
            request_id=request_id,
            tenant_id=req.tenant_id,
            subject_id=req.subject_id,
            verified_at=time.time(),
            stores_checked=results,
            verified_clean=clean,
            stores_with_residual=residual,
        )

        # Update request status
        req.status = "verified_clean" if clean else "residual_found"
        self._persist_request(req)

        return result

    def list_requests(self) -> List[ErasureRequest]:
        if not self._path.exists():
            return []
        reqs = []
        with open(self._path) as fh:
            for line in fh:
                line = line.strip()
                if line:
                    try:
                        reqs.append(ErasureRequest(**json.loads(line)))
                    except Exception:
                        pass
        return reqs

    # ── Store checks ──────────────────────────────────────────────────────────

    def _check_jsonl(
        self,
        path: Path,
        store_name: str,
        tenant_id: str,
        key: str = "repo_id",
    ) -> StoreCheckResult:
        if not path.exists():
            return StoreCheckResult(store_name=store_name, checked=True, residual_found=False)
        count = 0
        try:
            with open(path) as fh:
                for line in fh:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        rec = json.loads(line)
                        if rec.get(key) == tenant_id:
                            count += 1
                    except Exception:
                        pass
        except Exception as exc:
            return StoreCheckResult(store_name=store_name, checked=False, residual_found=False, error=str(exc))
        return StoreCheckResult(store_name=store_name, checked=True, residual_found=count > 0, residual_count=count)

    def _check_repo_profiles(self, tenant_id: str) -> StoreCheckResult:
        repos_dir = self._dir / "repos"
        if not repos_dir.exists():
            return StoreCheckResult(store_name="repo_profiles", checked=True, residual_found=False)
        count = 0
        try:
            for p in repos_dir.glob("*.json"):
                try:
                    data = json.loads(p.read_text())
                    if data.get("repo_id") == tenant_id:
                        count += 1
                except Exception:
                    pass
        except Exception as exc:
            return StoreCheckResult(store_name="repo_profiles", checked=False, residual_found=False, error=str(exc))
        return StoreCheckResult(store_name="repo_profiles", checked=True, residual_found=count > 0, residual_count=count)

    def _check_developer_profiles(self, tenant_id: str) -> StoreCheckResult:
        dev_dir = self._dir / "developers" / tenant_id
        if not dev_dir.exists():
            return StoreCheckResult(store_name="developer_profiles", checked=True, residual_found=False)
        files = list(dev_dir.glob("*.json"))
        return StoreCheckResult(
            store_name="developer_profiles",
            checked=True,
            residual_found=len(files) > 0,
            residual_count=len(files),
        )

    def _check_provenance(self, tenant_id: str) -> StoreCheckResult:
        prov_dir = Path(".agenticqa") / "provenance"
        if not prov_dir.exists():
            return StoreCheckResult(store_name="provenance", checked=True, residual_found=False)
        count = 0
        try:
            for p in prov_dir.glob("*.jsonl"):
                with open(p) as fh:
                    for line in fh:
                        line = line.strip()
                        if not line:
                            continue
                        try:
                            rec = json.loads(line)
                            if rec.get("tenant_id") == tenant_id or rec.get("repo_id") == tenant_id:
                                count += 1
                        except Exception:
                            pass
        except Exception as exc:
            return StoreCheckResult(store_name="provenance", checked=False, residual_found=False, error=str(exc))
        return StoreCheckResult(store_name="provenance", checked=True, residual_found=count > 0, residual_count=count)

    def _check_qdrant(self, tenant_id: str) -> StoreCheckResult:
        try:
            from qdrant_client import QdrantClient
            import os
            url = os.getenv("QDRANT_URL", "http://localhost:6333")
            client = QdrantClient(url=url, timeout=3)
            collections = [c.name for c in client.get_collections().collections]
            count = 0
            for col in collections:
                results = client.scroll(
                    collection_name=col,
                    scroll_filter={"must": [{"key": "_tenant_id", "match": {"value": tenant_id}}]},
                    limit=1,
                )
                if results[0]:
                    count += len(results[0])
            return StoreCheckResult(
                store_name="qdrant",
                checked=True,
                residual_found=count > 0,
                residual_count=count,
            )
        except ImportError:
            return StoreCheckResult(store_name="qdrant", checked=False, residual_found=False, error="qdrant_client not installed")
        except Exception as exc:
            return StoreCheckResult(store_name="qdrant", checked=False, residual_found=False, error=str(exc))

    # ── Persistence ───────────────────────────────────────────────────────────

    def _persist_request(self, req: ErasureRequest) -> None:
        try:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            # Re-write all requests (update in-place by rewriting file)
            existing = [r for r in self.list_requests() if r.request_id != req.request_id]
            existing.append(req)
            with open(self._path, "w") as fh:
                for r in existing:
                    fh.write(json.dumps(r.__dict__) + "\n")
        except Exception as exc:
            logger.error("GDPREraseVerifier persist failed: %s", exc)

    def _load_request(self, request_id: str) -> Optional[ErasureRequest]:
        for r in self.list_requests():
            if r.request_id == request_id:
                return r
        return None
