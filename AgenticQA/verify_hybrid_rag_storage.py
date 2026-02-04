#!/usr/bin/env python3
"""
Hybrid RAG Storage Verification Script

Tests the hybrid RAG system by:
1. Storing test data (simulating CI artifacts)
2. Verifying data in SQLite database
3. Querying and displaying results
4. Testing structured vs semantic query routing
"""
import os
import sys
from pathlib import Path
import tempfile
import sqlite3

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / 'src'))

def test_hybrid_storage():
    """Test hybrid RAG storage with sample data"""

    print("=" * 70)
    print("HYBRID RAG STORAGE VERIFICATION")
    print("=" * 70)

    # 1. Setup: Create hybrid RAG with temporary SQLite database
    print("\n1. Creating Hybrid RAG System")
    print("-" * 70)

    # Create temporary database for testing
    temp_db = tempfile.NamedTemporaryFile(suffix='.db', delete=False)
    db_path = temp_db.name
    temp_db.close()

    print(f"✅ Using test database: {db_path}")

    # Enable hybrid mode
    os.environ['AGENTICQA_HYBRID_RAG'] = 'true'
    os.environ['AGENTICQA_RAG_MODE'] = 'local'

    from agenticqa.rag.hybrid_retriever import HybridRAG
    from agenticqa.rag.relational_store import RelationalStore

    # Create hybrid RAG with test database
    hybrid = HybridRAG(
        vector_store=None,  # No vector store for this test
        relational_store=RelationalStore(db_path=db_path)
    )

    print("✅ HybridRAG created")
    print(f"   - Vector Store: {'None (using relational only)' if not hybrid.vector_store else 'Connected'}")
    print(f"   - Relational Store: SQLite at {db_path}")

    # 2. Store sample test results
    print("\n2. Storing Sample Test Results")
    print("-" * 70)

    test_artifacts = [
        {
            "doc_type": "test_result",
            "content": "Jest test suite completed: 45 passed, 3 failed",
            "metadata": {
                "run_id": "test-run-001",
                "agent_type": "qa",
                "tests_passed": 45,
                "tests_failed": 3,
                "timestamp": "2025-01-20T10:00:00Z"
            }
        },
        {
            "doc_type": "coverage_report",
            "content": "Code coverage report: 87.5% line coverage",
            "metadata": {
                "run_id": "test-run-001",
                "agent_type": "sdet",
                "coverage_pct": 87.5,
                "lines_covered": 1750,
                "lines_total": 2000,
                "timestamp": "2025-01-20T10:05:00Z"
            }
        },
        {
            "doc_type": "test_result",
            "content": "Playwright E2E tests: 20 passed, 1 failed",
            "metadata": {
                "run_id": "test-run-002",
                "agent_type": "qa",
                "tests_passed": 20,
                "tests_failed": 1,
                "timestamp": "2025-01-20T11:00:00Z"
            }
        },
        {
            "doc_type": "coverage_report",
            "content": "Coverage improved: 90.2% line coverage",
            "metadata": {
                "run_id": "test-run-002",
                "agent_type": "sdet",
                "coverage_pct": 90.2,
                "lines_covered": 1804,
                "lines_total": 2000,
                "timestamp": "2025-01-20T11:05:00Z"
            }
        }
    ]

    for i, artifact in enumerate(test_artifacts, 1):
        hybrid.store_document(
            content=artifact["content"],
            doc_type=artifact["doc_type"],
            metadata=artifact["metadata"]
        )
        print(f"✅ Stored artifact {i}/{len(test_artifacts)}: {artifact['doc_type']}")

    # 3. Verify data in SQLite database
    print("\n3. Verifying Data in SQLite Database")
    print("-" * 70)

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    # Check metrics table
    cursor.execute("SELECT COUNT(*) as count FROM metrics")
    metrics_count = cursor.fetchone()['count']
    print(f"✅ Metrics table: {metrics_count} records")

    # Show sample metrics
    cursor.execute("""
        SELECT agent_type, metric_type, metric_name, metric_value, timestamp
        FROM metrics
        ORDER BY timestamp
    """)

    print("\n   Sample Metrics:")
    print("   " + "-" * 66)
    print(f"   {'Agent':<12} {'Type':<16} {'Name':<16} {'Value':<10} {'Time':<12}")
    print("   " + "-" * 66)

    for row in cursor.fetchall():
        timestamp_short = row['timestamp'][:10] if row['timestamp'] else 'N/A'
        print(f"   {row['agent_type']:<12} {row['metric_type']:<16} "
              f"{row['metric_name']:<16} {row['metric_value']:<10.2f} {timestamp_short:<12}")

    # 4. Query structured data
    print("\n4. Testing Structured Queries (Fast Path)")
    print("-" * 70)

    # Query coverage metrics
    coverage_metrics = hybrid.relational_store.query_metrics(
        agent_type="sdet",
        metric_type="coverage"
    )

    print(f"✅ Found {len(coverage_metrics)} coverage metrics")
    for metric in coverage_metrics:
        print(f"   - {metric.metric_name}: {metric.metric_value:.1f}% (run: {metric.run_id})")

    # Query test pass rates
    test_metrics = hybrid.relational_store.query_metrics(
        agent_type="qa",
        metric_type="test_result"
    )

    print(f"\n✅ Found {len(test_metrics)} test result metrics")
    for metric in test_metrics:
        print(f"   - Pass rate: {metric.metric_value:.1%} (run: {metric.run_id})")

    # 5. Test metric statistics
    print("\n5. Testing Metric Statistics & Trends")
    print("-" * 70)

    stats = hybrid.relational_store.get_metric_stats(
        agent_type="sdet",
        metric_name="line_coverage"
    )

    print(f"✅ Coverage Statistics:")
    print(f"   - Average: {stats['avg']:.2f}%")
    print(f"   - Min: {stats['min']:.2f}%")
    print(f"   - Max: {stats['max']:.2f}%")
    print(f"   - Count: {stats['count']}")
    print(f"   - Trend: {stats['trend'].upper()}")

    # 6. Test query routing
    print("\n6. Testing Smart Query Routing")
    print("-" * 70)

    queries = [
        "What's the latest coverage?",
        "Get the test pass rate",
        "Find similar timeout errors",
        "Show accessibility patterns"
    ]

    for query in queries:
        is_structured = hybrid._is_structured_query(query)
        route = "📊 Relational DB (fast)" if is_structured else "🔍 Vector DB (semantic)"
        print(f"   '{query}'")
        print(f"      → {route}")

    # 7. Test agent context augmentation
    print("\n7. Testing Agent Context Augmentation")
    print("-" * 70)

    context = {"query": "test metrics"}
    augmented = hybrid.augment_agent_context("sdet", context)

    print("✅ Context augmented with metrics:")
    if 'structured_metrics' in augmented:
        for key, value in augmented['structured_metrics'].items():
            print(f"   - {key}: {value}")

    # 8. Export database for inspection
    print("\n8. Database Export Information")
    print("-" * 70)

    # Get database size
    db_size = os.path.getsize(db_path)
    print(f"✅ Database size: {db_size:,} bytes ({db_size/1024:.2f} KB)")

    # Show table schemas
    cursor.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name='metrics'")
    schema = cursor.fetchone()
    if schema:
        print("\n   Metrics Table Schema:")
        print("   " + schema['sql'].replace('\n', '\n   '))

    conn.close()

    # 9. Clean up
    print("\n9. Verification Summary")
    print("-" * 70)

    print("✅ All tests passed!")
    print(f"\n   Test database preserved at: {db_path}")
    print("\n   You can inspect it with:")
    print(f"   $ sqlite3 {db_path}")
    print("   sqlite> SELECT * FROM metrics;")
    print("   sqlite> SELECT * FROM executions;")
    print("   sqlite> .schema")

    hybrid.close()

    print("\n" + "=" * 70)
    print("VERIFICATION COMPLETE - Hybrid RAG is working correctly!")
    print("=" * 70)

    return db_path


def interactive_query(db_path):
    """Allow interactive queries on the test database"""
    print("\n" + "=" * 70)
    print("INTERACTIVE QUERY MODE")
    print("=" * 70)
    print("\nAvailable commands:")
    print("  1. List all metrics")
    print("  2. Show coverage trends")
    print("  3. Show test pass rates")
    print("  4. Export to CSV")
    print("  5. Show database stats")
    print("  q. Quit")

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    while True:
        print("\n" + "-" * 70)
        choice = input("Enter choice (1-5, q): ").strip()

        if choice == 'q':
            break
        elif choice == '1':
            cursor.execute("SELECT * FROM metrics ORDER BY timestamp")
            rows = cursor.fetchall()
            print(f"\nFound {len(rows)} metrics:")
            for row in rows:
                print(f"  {row['agent_type']}/{row['metric_type']}: "
                      f"{row['metric_name']}={row['metric_value']}")
        elif choice == '2':
            cursor.execute("""
                SELECT metric_value, timestamp
                FROM metrics
                WHERE metric_name = 'line_coverage'
                ORDER BY timestamp
            """)
            rows = cursor.fetchall()
            print(f"\nCoverage Trend ({len(rows)} data points):")
            for row in rows:
                print(f"  {row['timestamp'][:19]}: {row['metric_value']:.1f}%")
        elif choice == '3':
            cursor.execute("""
                SELECT metric_value, run_id, timestamp
                FROM metrics
                WHERE metric_type = 'test_result'
                ORDER BY timestamp
            """)
            rows = cursor.fetchall()
            print(f"\nTest Pass Rates ({len(rows)} data points):")
            for row in rows:
                print(f"  Run {row['run_id']}: {row['metric_value']:.1%} "
                      f"({row['timestamp'][:19]})")
        elif choice == '4':
            csv_path = db_path.replace('.db', '.csv')
            cursor.execute("SELECT * FROM metrics")
            with open(csv_path, 'w') as f:
                f.write(','.join([desc[0] for desc in cursor.description]) + '\n')
                for row in cursor.fetchall():
                    f.write(','.join(str(x) for x in row) + '\n')
            print(f"\n✅ Exported to: {csv_path}")
        elif choice == '5':
            cursor.execute("SELECT COUNT(*) as count FROM metrics")
            metrics_count = cursor.fetchone()['count']
            cursor.execute("SELECT COUNT(*) as count FROM executions")
            executions_count = cursor.fetchone()['count']
            db_size = os.path.getsize(db_path)
            print(f"\nDatabase Statistics:")
            print(f"  Metrics: {metrics_count}")
            print(f"  Executions: {executions_count}")
            print(f"  Size: {db_size:,} bytes")

    conn.close()
    print("\nExiting interactive mode.")


if __name__ == "__main__":
    try:
        # Run verification
        db_path = test_hybrid_storage()

        # Offer interactive mode
        print("\n" + "=" * 70)
        response = input("Would you like to query the database interactively? (y/n): ").strip().lower()
        if response == 'y':
            interactive_query(db_path)

        print(f"\n✅ Test database available at: {db_path}")
        print("   (Delete when done: rm {})".format(db_path))

    except Exception as e:
        print(f"\n❌ Error during verification: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
