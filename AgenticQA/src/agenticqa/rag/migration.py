"""
Vector Store Migration Utilities

Canonical JSONL export/import and parity validation utilities for migrating
between vector providers (e.g., Weaviate -> Qdrant).
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from hashlib import sha256
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple
import json


DEFAULT_DOC_TYPES = [
    "test_result",
    "error",
    "compliance_rule",
    "performance_pattern",
]


@dataclass
class CanonicalVectorRecord:
    """Canonical migration schema for vector records."""

    id: str
    content: str
    embedding: List[float]
    metadata: Dict[str, Any]
    timestamp: str
    doc_type: str


class MigrationValidationError(ValueError):
    """Raised when migration records are invalid."""



def _to_canonical_record(document: Any) -> CanonicalVectorRecord:
    metadata = document.metadata or {}
    return CanonicalVectorRecord(
        id=str(document.id),
        content=document.content,
        embedding=list(document.embedding or []),
        metadata=metadata,
        timestamp=document.timestamp,
        doc_type=document.doc_type,
    )



def _record_key(record: Dict[str, Any]) -> str:
    metadata = record.get("metadata") or {}
    return str(metadata.get("source_id") or record["id"])



def _record_hash(record: Dict[str, Any]) -> str:
    metadata = dict(record.get("metadata") or {})
    # Ignore migration bookkeeping fields when comparing content parity.
    metadata.pop("source_id", None)
    metadata.pop("id", None)

    payload = {
        "id": record.get("id"),
        "content": record.get("content"),
        "embedding": record.get("embedding") or [],
        "metadata": metadata,
        "timestamp": record.get("timestamp"),
        "doc_type": record.get("doc_type"),
    }
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return sha256(encoded).hexdigest()



def iter_store_documents(
    vector_store: Any,
    doc_types: Optional[List[str]] = None,
    include_vectors: bool = True,
) -> Iterable[CanonicalVectorRecord]:
    """
    Iterate all documents from a vector store and return canonical records.

    Supports stores that implement either:
    - `list_documents(doc_type=None, include_vectors=True)`
    - `get_documents_by_type(doc_type)`
    """
    selected_types = doc_types or DEFAULT_DOC_TYPES

    if hasattr(vector_store, "list_documents"):
        docs = vector_store.list_documents(doc_type=None, include_vectors=include_vectors)
        for doc in docs:
            if doc.doc_type in selected_types:
                yield _to_canonical_record(doc)
        return

    if not hasattr(vector_store, "get_documents_by_type"):
        raise AttributeError(
            "Vector store must implement list_documents(...) or get_documents_by_type(...)"
        )

    for doc_type in selected_types:
        for doc in vector_store.get_documents_by_type(doc_type):
            yield _to_canonical_record(doc)



def validate_jsonl_schema(jsonl_path: str) -> Dict[str, Any]:
    """Validate canonical JSONL schema and return validation summary."""
    required = {"id", "content", "embedding", "metadata", "timestamp", "doc_type"}
    path = Path(jsonl_path)

    errors: List[str] = []
    records = 0

    with path.open("r", encoding="utf-8") as f:
        for line_number, line in enumerate(f, start=1):
            text = line.strip()
            if not text:
                continue

            records += 1
            try:
                row = json.loads(text)
            except json.JSONDecodeError as exc:
                errors.append(f"line {line_number}: invalid JSON ({exc})")
                continue

            missing = required - set(row.keys())
            if missing:
                errors.append(f"line {line_number}: missing required fields {sorted(missing)}")
                continue

            if not isinstance(row["embedding"], list):
                errors.append(f"line {line_number}: embedding must be a list")
            if not isinstance(row["metadata"], dict):
                errors.append(f"line {line_number}: metadata must be an object")

    return {
        "path": str(path),
        "records_checked": records,
        "is_valid": len(errors) == 0,
        "errors": errors,
    }



def export_vector_store_to_jsonl(
    vector_store: Any,
    output_path: str,
    doc_types: Optional[List[str]] = None,
    require_embeddings: bool = True,
) -> Dict[str, Any]:
    """Export all selected vector documents to canonical JSONL."""
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)

    total = 0
    missing_embeddings = 0
    by_type: Dict[str, int] = {}

    with path.open("w", encoding="utf-8") as f:
        for record in iter_store_documents(vector_store, doc_types=doc_types, include_vectors=True):
            if require_embeddings and not record.embedding:
                missing_embeddings += 1
                continue

            total += 1
            by_type[record.doc_type] = by_type.get(record.doc_type, 0) + 1
            f.write(json.dumps(asdict(record), sort_keys=True) + "\n")

    if require_embeddings and missing_embeddings > 0:
        raise MigrationValidationError(
            f"Export skipped {missing_embeddings} records with missing embeddings. "
            "Ensure provider supports vector export before migration."
        )

    return {
        "path": str(path),
        "records_exported": total,
        "records_missing_embeddings": missing_embeddings,
        "records_by_type": by_type,
    }



def import_jsonl_to_vector_store(vector_store: Any, input_path: str) -> Dict[str, Any]:
    """Import canonical JSONL records into target vector store."""
    validation = validate_jsonl_schema(input_path)
    if not validation["is_valid"]:
        raise MigrationValidationError(
            "Invalid canonical JSONL input:\n" + "\n".join(validation["errors"])
        )

    path = Path(input_path)
    imported = 0
    by_type: Dict[str, int] = {}

    with path.open("r", encoding="utf-8") as f:
        for line in f:
            text = line.strip()
            if not text:
                continue
            record = json.loads(text)

            metadata = dict(record["metadata"] or {})
            metadata.setdefault("source_id", record["id"])
            metadata.setdefault("id", record["id"])
            metadata.setdefault("timestamp", record["timestamp"])

            vector_store.add_document(
                content=record["content"],
                embedding=record["embedding"],
                metadata=metadata,
                doc_type=record["doc_type"],
            )
            imported += 1
            by_type[record["doc_type"]] = by_type.get(record["doc_type"], 0) + 1

    return {
        "path": str(path),
        "records_imported": imported,
        "records_by_type": by_type,
    }



def parity_report(
    source_store: Any,
    target_store: Any,
    doc_types: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """Generate structural/content parity report between two vector stores."""
    source_records = [asdict(r) for r in iter_store_documents(source_store, doc_types=doc_types)]
    target_records = [asdict(r) for r in iter_store_documents(target_store, doc_types=doc_types)]

    source_map = {_record_key(r): _record_hash(r) for r in source_records}
    target_map = {_record_key(r): _record_hash(r) for r in target_records}

    source_keys = set(source_map.keys())
    target_keys = set(target_map.keys())

    missing_in_target = sorted(source_keys - target_keys)
    extra_in_target = sorted(target_keys - source_keys)

    mismatched_hashes = sorted(
        key for key in (source_keys & target_keys) if source_map[key] != target_map[key]
    )

    return {
        "source_count": len(source_records),
        "target_count": len(target_records),
        "missing_in_target": missing_in_target,
        "extra_in_target": extra_in_target,
        "mismatched_hashes": mismatched_hashes,
        "is_parity": not missing_in_target and not extra_in_target and not mismatched_hashes,
    }
