#!/usr/bin/env python3
"""Run end-to-end vector migration verification (export/import/parity)."""

import os
import tempfile
from pathlib import Path

from src.agenticqa.rag.config import RAGConfig, VectorProvider
from src.agenticqa.rag.weaviate_store import WeaviateVectorStore
from src.agenticqa.rag.qdrant_store import QdrantVectorStore
from src.agenticqa.rag.migration import (
    export_vector_store_to_jsonl,
    import_jsonl_to_vector_store,
    parity_report,
)


def _create_store(provider: str):
    selected = VectorProvider(provider)
    if selected == VectorProvider.QDRANT:
        return QdrantVectorStore(**RAGConfig.get_qdrant_config().to_dict())
    return WeaviateVectorStore(**RAGConfig.get_weaviate_config().to_dict())


if __name__ == "__main__":
    source_provider = os.getenv("SOURCE_VECTOR_PROVIDER", "weaviate")
    target_provider = os.getenv("TARGET_VECTOR_PROVIDER", "qdrant")

    source_store = _create_store(source_provider)
    target_store = _create_store(target_provider)

    try:
        with tempfile.TemporaryDirectory(prefix="vector-migration-") as tmp:
            jsonl_path = Path(tmp) / "canonical-export.jsonl"

            export_stats = export_vector_store_to_jsonl(source_store, str(jsonl_path))
            import_stats = import_jsonl_to_vector_store(target_store, str(jsonl_path))
            report = parity_report(source_store, target_store)

            print("\n=== Vector Migration Verification ===")
            print(f"Source provider: {source_provider}")
            print(f"Target provider: {target_provider}")
            print(f"Export stats: {export_stats}")
            print(f"Import stats: {import_stats}")
            print(f"Parity report: {report}")

            if not report["is_parity"]:
                raise SystemExit("Migration verification failed: parity check did not pass")

            print("✅ Migration verification passed")
    finally:
        source_store.close()
        target_store.close()
