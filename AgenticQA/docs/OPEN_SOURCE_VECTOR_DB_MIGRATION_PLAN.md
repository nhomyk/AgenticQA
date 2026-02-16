# Open-Source Vector DB Migration + QA Plan

## Goal
Add an open-source vector database backend (recommended: **Qdrant**) without breaking current Weaviate support, dashboard behavior, or CI/CD pipeline reliability.

---

## Decision Summary

1. **Keep Weaviate integration code**
   - Keep existing Weaviate code path as a supported provider.
   - Introduce provider-based routing so future providers can be added without refactoring core logic.

2. **Use phased migration**
   - Phase A: one-time **backfill conversion** from Weaviate to Qdrant.
   - Phase B: temporary **dual-write replication** to both providers.
   - Phase C: cut over reads to Qdrant after validation gates pass.

3. **Do not touch dashboard/UI paths during migration**
   - Keep all migration work isolated to data and RAG layers.

---

## Provider Architecture (future-proof)

- Keep API compatibility with current vector store behavior:
  - `add_document(...)`
  - `search(...)`
  - `get_documents_by_type(...)`
  - `delete_document(...)`
  - `clear()`
  - `stats()`
- Add provider selection via env (example):
  - `AGENTICQA_VECTOR_PROVIDER=weaviate|qdrant|memory`
- Add a provider factory so future DB providers can be plugged in with minimal change.

---

## Canonical Migration Format

Use JSONL as the migration interchange format (idempotent and replayable):

- Required fields:
  - `id`
  - `content`
  - `embedding`
  - `metadata`
  - `timestamp`
  - `doc_type`

Migration rules:
- Preserve IDs when possible.
- Preserve embedding vectors exactly.
- Preserve `doc_type` and metadata keys/values.
- Normalize timestamps to ISO-8601.
- Re-runs must be idempotent (upsert semantics).

---

## QA & Validation Gates (Pipeline-Aligned)

### Gate 1: Structural parity
- Compare document counts by `doc_type`.
- Validate schema compliance (all required fields present and type-correct).
- Detect duplicates and key collisions.

### Gate 2: Content parity
- For sampled and full sets (if feasible), verify:
  - Hash of canonical payload per record
  - Metadata parity
  - Timestamp normalization parity

### Gate 3: Retrieval parity
- Run fixed query set on both providers.
- Compare top-k overlap and score deltas.
- Define pass threshold (example):
  - top-5 overlap >= 0.8 average
  - no severe rank inversions on critical queries

### Gate 4: Quality parity
- Run optional RAG quality evaluation (Ragas) before/after.
- Accept migration only if quality does not regress beyond tolerance.

### Gate 5: Pipeline stability
- Existing CI and validation workflows pass.
- No dashboard/UI test regressions.

---

## Existing Project Assets to Reuse

- Data quality pipeline:
  - `src/data_store/data_quality_pipeline.py`
  - `src/data_store/data_quality_tester.py`
- Great Expectations integration:
  - `src/data_store/great_expectations_validator.py`
- Data validation tests:
  - `tests/test_data_validation.py`
  - `tests/test_integration_verification.py`
- Optional RAG quality tests:
  - `tests/test_ragas_evaluation.py`
- Pipeline workflows:
  - `.github/workflows/pipeline-validation.yml`
  - `.github/workflows/ci.yml`

---

## Additional Open-Source Tooling (Recommended)

- **Qdrant** (new vector backend)
- **qdrant-client** (Python SDK)
- **DeepDiff** (record-level parity diffs)
- **Pandera** (schema contracts for migration datasets)

Project migration tooling now available:
- `src/agenticqa/rag/migration.py` (canonical export/import/schema/parity)
- `scripts/verify_vector_migration.py` (end-to-end verification runner)
- `tests/test_vector_migration.py` (pipeline-safe migration tests)

Optional:
- **pytest-benchmark** for retrieval latency parity
- Continue using **Great Expectations** where already established

---

## Cutover Strategy

1. **Prepare**
   - Add Qdrant provider and provider factory.
   - Add migration exporter/importer using canonical JSONL.

2. **Backfill**
   - Export Weaviate -> JSONL.
   - Import JSONL -> Qdrant.

3. **Dual-write window**
   - Write new documents to both providers.
   - Keep reads on Weaviate initially.

4. **Read switch (canary)**
   - Route a small % of read traffic/tests to Qdrant.
   - Monitor parity and quality metrics.

5. **Full switch**
   - Move reads to Qdrant after gates pass.
   - Keep Weaviate path for rollback.

6. **Stabilize**
   - End dual-write when confidence is high.
   - Keep documented rollback path.

---

## Rollback Plan

- Provider toggle via environment variable.
- If any gate fails:
  - Route reads back to Weaviate.
  - Keep dual-write active until issue is fixed.
  - Re-run migration idempotently.

---

## Acceptance Criteria

Migration is complete only when all are true:

- Structural parity checks pass.
- Content parity checks pass.
- Retrieval parity threshold is met.
- Optional Ragas quality is non-regressive.
- Pipeline validation workflows pass.
- Dashboard/UI-related tests remain green.
- Rollback procedure is tested and documented.

---

## Quick Verification Commands

- Unit-level migration checks:
  - `pytest tests/test_vector_migration.py -v`
- End-to-end provider migration verify (env-driven):
  - `SOURCE_VECTOR_PROVIDER=weaviate TARGET_VECTOR_PROVIDER=qdrant python scripts/verify_vector_migration.py`
