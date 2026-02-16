"""Tests for canonical vector migration utilities."""

from dataclasses import dataclass
from typing import Dict, List, Optional
import json

from src.agenticqa.rag.migration import (
    export_vector_store_to_jsonl,
    import_jsonl_to_vector_store,
    parity_report,
    validate_jsonl_schema,
)


@dataclass
class _Doc:
    id: str
    content: str
    embedding: List[float]
    metadata: Dict
    timestamp: str
    doc_type: str


class _FakeVectorStore:
    def __init__(self, docs: Optional[List[_Doc]] = None):
        self.docs = docs or []

    def add_document(self, content, embedding, metadata, doc_type):
        doc_id = metadata.get("id") or f"id-{len(self.docs)+1}"
        self.docs.append(
            _Doc(
                id=doc_id,
                content=content,
                embedding=embedding,
                metadata=metadata,
                timestamp=metadata.get("timestamp", ""),
                doc_type=doc_type,
            )
        )
        return doc_id

    def list_documents(self, doc_type=None, include_vectors=True):
        docs = self.docs
        if doc_type:
            docs = [d for d in docs if d.doc_type == doc_type]
        if include_vectors:
            return docs
        return [
            _Doc(
                id=d.id,
                content=d.content,
                embedding=[],
                metadata=d.metadata,
                timestamp=d.timestamp,
                doc_type=d.doc_type,
            )
            for d in docs
        ]


class TestVectorMigration:
    def test_export_import_roundtrip(self, tmp_path):
        source = _FakeVectorStore(
            docs=[
                _Doc(
                    id="doc-1",
                    content="timeout error",
                    embedding=[0.1, 0.2, 0.3],
                    metadata={"run_id": "1", "timestamp": "2026-02-16T00:00:00"},
                    timestamp="2026-02-16T00:00:00",
                    doc_type="error",
                ),
                _Doc(
                    id="doc-2",
                    content="all tests passed",
                    embedding=[0.4, 0.5, 0.6],
                    metadata={"run_id": "2", "timestamp": "2026-02-16T00:01:00"},
                    timestamp="2026-02-16T00:01:00",
                    doc_type="test_result",
                ),
            ]
        )
        target = _FakeVectorStore()

        jsonl = tmp_path / "export.jsonl"
        export_stats = export_vector_store_to_jsonl(source, str(jsonl))
        import_stats = import_jsonl_to_vector_store(target, str(jsonl))
        report = parity_report(source, target)

        assert export_stats["records_exported"] == 2
        assert import_stats["records_imported"] == 2
        assert report["is_parity"] is True

    def test_validate_jsonl_schema_invalid(self, tmp_path):
        jsonl = tmp_path / "bad.jsonl"
        with jsonl.open("w", encoding="utf-8") as f:
            f.write(json.dumps({"id": "only-id"}) + "\n")

        result = validate_jsonl_schema(str(jsonl))
        assert result["is_valid"] is False
        assert len(result["errors"]) > 0

    def test_parity_detects_missing(self, tmp_path):
        source = _FakeVectorStore(
            docs=[
                _Doc(
                    id="doc-1",
                    content="a",
                    embedding=[0.1],
                    metadata={"timestamp": "2026-02-16T00:00:00"},
                    timestamp="2026-02-16T00:00:00",
                    doc_type="error",
                )
            ]
        )
        target = _FakeVectorStore()

        report = parity_report(source, target)
        assert report["is_parity"] is False
        assert report["missing_in_target"] == ["doc-1"]
