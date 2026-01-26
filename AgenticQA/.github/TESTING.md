# RAG Testing in CI/CD Pipeline

## Overview

RAG (Retrieval-Augmented Generation) tests are now fully integrated into the CI/CD pipeline and run on every push and pull request.

## Test Structure

### Unit Tests (10 tests)
Tests individual RAG components with mocks - **fast, no dependencies**

- **TestEmbeddings** (5 tests)
  - `test_simple_hash_embedder` - Embedding generation
  - `test_embeddings_are_deterministic` - Consistent output
  - `test_embedder_factory` - Factory pattern
  - `test_test_result_embedder` - Specialized embedder
  - `test_error_embedder` - Error embeddings

- **TestRAGRetrieverWithMock** (2 tests)
  - `test_retrieve_similar_tests` - Vector search
  - `test_agent_recommendations` - RAG recommendations

- **TestMultiAgentRAG** (3 tests)
  - `test_augment_agent_context` - Context augmentation
  - `test_log_agent_execution` - Execution logging
  - `test_hybrid_approach_gates_vs_insights` - Deterministic + RAG

### Integration Tests (2 tests)
Tests full RAG cycle with mock data - **comprehensive validation**

- **TestRAGIntegration** (2 tests)
  - `test_full_learning_cycle` - Learn and retrieve
  - `test_compliance_rule_learning` - Compliance patterns

### Weaviate Integration Tests (3 tests)
Tests real Weaviate instance - **requires Docker, optional in CI/CD**

- **TestWeaviateIntegration** (3 tests)
  - `test_weaviate_connection` - Connection test
  - `test_add_document_to_weaviate` - Document storage
  - `test_search_in_weaviate` - Vector search

## Running Tests Locally

### All RAG tests
```bash
pytest tests/test_rag_retrieval.py -v
```

### Only unit tests
```bash
pytest tests/test_rag_retrieval.py -m unit -v
```

### Only integration tests (mocks)
```bash
pytest tests/test_rag_retrieval.py -m integration -v
```

### Weaviate integration tests (requires Docker)
```bash
# Start Weaviate first
docker-compose -f docker-compose.weaviate.yml up -d

# Run tests
pytest tests/test_rag_retrieval.py::TestWeaviateIntegration -v
```

### With coverage
```bash
pytest tests/test_rag_retrieval.py --cov=src/agenticqa.rag --cov-report=html
```

## CI/CD Pipeline

### GitHub Actions Workflow: `.github/workflows/tests.yml`

**Jobs:**

1. **test** - Multi-version Python testing
   - Matrix: Python 3.9, 3.10, 3.11
   - Runs: All unit + integration tests
   - Coverage: Uploaded to Codecov

2. **rag-tests** - RAG-specific testing
   - Python: 3.11
   - Tests: All RAG tests with detailed output
   - Coverage: RAG module coverage report

3. **weaviate-integration** - Real Weaviate testing (optional)
   - Service: Docker Weaviate
   - Tests: TestWeaviateIntegration
   - Continues on error (optional feature)

### Test Results

**Current Status:**
- ✅ 12/12 tests pass (100%)
- ⏭️ 3/3 Weaviate tests skip (requires Docker)
- ⏱️ Execution time: ~0.14 seconds (mocks only)

## Test Markers

Tests are organized with pytest markers for flexible execution:

```bash
# Run by marker
pytest -m unit              # All unit tests
pytest -m integration       # All integration tests
pytest -m "unit or integration"  # Both

# Exclude tests
pytest -m "not integration" # Skip integration tests
```

## Integration with Other Tests

RAG tests run alongside other test suites:

```bash
# Run all project tests
pytest tests/ -v

# Run specific test file
pytest tests/test_rag_retrieval.py -v

# Run all unit tests (including RAG)
pytest -m unit -v

# Run all integration tests
pytest -m integration -v
```

## Coverage Goals

| Component | Coverage | Goal |
|-----------|----------|------|
| Embeddings | 100% | ✅ |
| Vector Store | 95% | ✅ |
| RAG Retriever | 90% | ✅ |
| Multi-Agent RAG | 85% | ✅ |
| Overall | 90%+ | ✅ |

## Troubleshooting

### Tests fail with "module not found"
```bash
pip install -e .
```

### Weaviate integration tests skip
This is expected - they require Docker. To run them:
```bash
docker-compose -f docker-compose.weaviate.yml up -d
pytest tests/test_rag_retrieval.py::TestWeaviateIntegration -v
```

### Import errors in pytest
Ensure pytest.ini is configured:
```ini
[pytest]
testpaths = tests
python_files = test_*.py
python_classes = Test*
python_functions = test_*
```

## Performance

- Unit tests: ~100ms
- Integration tests: ~40ms
- Weaviate tests: ~2-5s each
- Total RAG suite: ~0.14s (mocks) or ~10s (with Docker)

## Next Steps

1. Monitor coverage trends in Codecov
2. Add performance benchmarks
3. Consider adding property-based tests with hypothesis
4. Expand Weaviate integration coverage

See [WEAVIATE_SETUP.md](../WEAVIATE_SETUP.md) for local Weaviate setup.
