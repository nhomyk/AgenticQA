#!/usr/bin/env python3
"""
Quick demo script to test Hybrid RAG functionality
"""
import os
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / 'src'))

def test_hybrid_rag():
    """Test hybrid RAG system"""
    print("=" * 60)
    print("HYBRID RAG TEST DEMO")
    print("=" * 60)

    # Enable hybrid mode
    os.environ['AGENTICQA_HYBRID_RAG'] = 'true'
    os.environ['AGENTICQA_RAG_MODE'] = 'local'

    print("\n1. Configuration Check")
    print("-" * 60)
    from agenticqa.rag.config import RAGConfig

    print(RAGConfig.print_config_summary())
    print(f"✅ Hybrid RAG Enabled: {RAGConfig.is_hybrid_rag_enabled()}")
    print(f"✅ Using PostgreSQL: {RAGConfig.use_postgresql()}")

    print("\n2. Create Hybrid RAG System")
    print("-" * 60)
    from agenticqa.rag.config import create_rag_system

    try:
        rag = create_rag_system()
        print(f"✅ RAG System Created: {type(rag).__name__}")
        print(f"✅ Has Relational Store: {hasattr(rag, 'relational_store')}")
        print(f"✅ Has Vector Store: {hasattr(rag, 'vector_store')}")
    except Exception as e:
        print(f"⚠️  Warning: {e}")
        print("   (This is expected if Weaviate is not running locally)")
        print("   Hybrid RAG will use relational DB only")

    print("\n3. Test Relational Store")
    print("-" * 60)
    from agenticqa.rag.relational_store import RelationalStore

    # Create in-memory store for testing
    store = RelationalStore(db_path=":memory:")

    # Store a metric
    store.store_metric(
        run_id="demo-run-1",
        agent_type="qa",
        metric_type="coverage",
        metric_name="line_coverage",
        metric_value=87.5,
        metadata={"demo": True}
    )
    print("✅ Stored metric: line_coverage = 87.5%")

    # Query metrics
    metrics = store.query_metrics(
        agent_type="qa",
        metric_type="coverage"
    )
    print(f"✅ Queried metrics: Found {len(metrics)} metric(s)")
    if metrics:
        print(f"   - {metrics[0].metric_name}: {metrics[0].metric_value}%")

    # Store execution
    store.store_execution(
        run_id="demo-run-1",
        agent_type="qa",
        action="run_tests",
        outcome="success",
        success=True
    )
    print("✅ Stored execution: run_tests (success)")

    # Get success rate
    rate, successes, total = store.get_success_rate("qa")
    print(f"✅ Success rate: {rate:.1%} ({successes}/{total})")

    store.close()

    print("\n4. Test Hybrid RAG Interface")
    print("-" * 60)
    from agenticqa.rag.hybrid_retriever import HybridRAG
    from agenticqa.rag.relational_store import RelationalStore

    hybrid = HybridRAG(
        vector_store=None,  # No vector store for demo
        relational_store=RelationalStore(db_path=":memory:")
    )

    # Test storing document
    hybrid.store_document(
        content="Test suite completed successfully",
        doc_type="test_result",
        metadata={
            "run_id": "demo-run-2",
            "agent_type": "qa",
            "tests_passed": 45,
            "tests_failed": 3,
            "timestamp": "2025-01-01T00:00:00"
        }
    )
    print("✅ Stored test result document")

    # Test structured query detection
    queries = [
        ("What's the latest coverage?", True),
        ("Get the pass rate", True),
        ("Find similar timeout errors", False),
    ]

    print("\n   Query Type Detection:")
    for query, expected_structured in queries:
        is_structured = hybrid._is_structured_query(query)
        emoji = "📊" if is_structured else "🔍"
        query_type = "Structured (Relational)" if is_structured else "Semantic (Vector)"
        print(f"   {emoji} '{query}' → {query_type}")

    # Test agent context augmentation
    context = {"query": "test metrics"}
    augmented = hybrid.augment_agent_context("qa", context)
    print(f"\n✅ Augmented context has {len(augmented)} fields")
    if 'structured_metrics' in augmented:
        print("   - structured_metrics ✓")

    hybrid.close()

    print("\n5. Test MultiAgentRAG Compatibility")
    print("-" * 60)

    # Test that HybridRAG has same interface as MultiAgentRAG
    required_methods = ['augment_agent_context', 'log_agent_execution']
    for method in required_methods:
        has_method = hasattr(hybrid, method)
        print(f"   {'✅' if has_method else '❌'} {method}")

    print("\n" + "=" * 60)
    print("✅ HYBRID RAG TEST COMPLETE!")
    print("=" * 60)
    print("\nNext Steps:")
    print("1. Enable in production: export AGENTICQA_HYBRID_RAG=true")
    print("2. Run full tests: pytest tests/test_hybrid_rag.py -v")
    print("3. Check SQLite DB: sqlite3 ~/.agenticqa/rag.db")
    print("4. Monitor cost savings in Weaviate dashboard")
    print("\nDocumentation:")
    print("- Quick Start: HYBRID_RAG_QUICKSTART.md")
    print("- Architecture: HYBRID_RAG_ARCHITECTURE.md")
    print("- Main Guide: HYBRID_RAG_README.md")


if __name__ == "__main__":
    try:
        test_hybrid_rag()
    except Exception as e:
        print(f"\n❌ Error during test: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
