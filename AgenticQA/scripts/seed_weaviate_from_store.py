#!/usr/bin/env python3
"""
Seed Weaviate from local artifact store.

Reads every artifact from .test-artifact-store/ and ingests it into Weaviate
so that the RAG system has real historical data to retrieve from.

Usage:
    python scripts/seed_weaviate_from_store.py
    python scripts/seed_weaviate_from_store.py --dry-run
    python scripts/seed_weaviate_from_store.py --store-path /path/to/store --limit 500
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

# Map artifact source names → RAG agent types
_AGENT_TYPE_MAP = {
    "QA_Assistant":       "qa",
    "SDET_Agent":         "qa",
    "Performance_Agent":  "performance",
    "Compliance_Agent":   "compliance",
    "DevOps_Agent":       "devops",
    "SRE_Agent":          "devops",
    "Fullstack_Agent":    "devops",
    "compliance":         "compliance",
    "qa":                 "qa",
    "sre":                "devops",
    "sdet":               "qa",
}

_SEEDED = 0
_SKIPPED = 0
_FAILED = 0


def _resolve_agent_type(source: str) -> str:
    return _AGENT_TYPE_MAP.get(source, "qa")


def _ingest_artifact(rag, artifact: dict, meta: dict, dry_run: bool) -> bool:
    global _SEEDED, _SKIPPED, _FAILED
    agent_type = _resolve_agent_type(meta.get("source", ""))

    if not artifact:
        _SKIPPED += 1
        return False

    # Enrich with metadata fields RAG log methods expect
    artifact.setdefault("artifact_type", meta.get("artifact_type", "execution"))
    artifact.setdefault("status", "success")

    if dry_run:
        print(f"  [dry-run] would ingest {meta['artifact_id']} as {agent_type}")
        _SEEDED += 1
        return True

    try:
        rag.log_agent_execution(agent_type, artifact)
        _SEEDED += 1
        return True
    except Exception as e:
        print(f"  ⚠  failed {meta['artifact_id']}: {e}")
        _FAILED += 1
        return False


def main():
    parser = argparse.ArgumentParser(description="Seed Weaviate from artifact store")
    parser.add_argument("--store-path", default=".test-artifact-store",
                        help="Path to artifact store directory (default: .test-artifact-store)")
    parser.add_argument("--limit", type=int, default=0,
                        help="Max artifacts to ingest (0 = all)")
    parser.add_argument("--dry-run", action="store_true",
                        help="Print what would be ingested without writing to Weaviate")
    args = parser.parse_args()

    # ── Connect to RAG ──────────────────────────────────────────────────────
    print("Connecting to RAG system...")
    try:
        from agenticqa.rag.config import create_rag_system
        rag = create_rag_system()
        print("✅ RAG system ready")
    except Exception as e:
        print(f"❌ Cannot connect to RAG system: {e}")
        print("   Is Weaviate running? (docker compose -f docker-compose.weaviate.yml up -d)")
        sys.exit(1)

    # ── Load artifact store ─────────────────────────────────────────────────
    from data_store.artifact_store import TestArtifactStore
    store = TestArtifactStore(args.store_path)
    all_meta = store.search_artifacts()
    print(f"Found {len(all_meta)} artifacts in {args.store_path}")

    if args.limit:
        all_meta = all_meta[: args.limit]
        print(f"Limiting to {args.limit} artifacts")

    if args.dry_run:
        print("DRY RUN — no data will be written to Weaviate\n")

    # ── Ingest ──────────────────────────────────────────────────────────────
    for i, meta in enumerate(all_meta, 1):
        artifact = store.get_artifact(meta["artifact_id"])
        _ingest_artifact(rag, artifact, meta, args.dry_run)

        if i % 100 == 0:
            print(f"  Progress: {i}/{len(all_meta)} "
                  f"(seeded={_SEEDED}, skipped={_SKIPPED}, failed={_FAILED})")

    # ── Close ───────────────────────────────────────────────────────────────
    try:
        if hasattr(rag, "close"):
            rag.close()
    except Exception:
        pass

    print(f"\n{'DRY RUN ' if args.dry_run else ''}Seeding complete:")
    print(f"  ✅ Seeded:  {_SEEDED}")
    print(f"  ⏭  Skipped: {_SKIPPED}")
    print(f"  ❌ Failed:  {_FAILED}")

    if _FAILED > 0:
        sys.exit(1)


if __name__ == "__main__":
    main()
