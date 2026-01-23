"""Example usage of the secure data pipeline"""

from src.data_store import SecureDataPipeline
from datetime import datetime


def example_usage():
    """Example: Store agent execution with full validation"""

    pipeline = SecureDataPipeline(use_great_expectations=False)

    # Simulate agent execution result
    execution_result = {
        "timestamp": datetime.utcnow().isoformat(),
        "agent_name": "QA_Assistant",
        "status": "success",
        "output": {
            "test_count": 42,
            "passed": 40,
            "failed": 2,
            "duration_ms": 1250,
        },
        "run_id": "run-2026-01-23-001",
    }

    # Execute full pipeline with validation
    success, result = pipeline.execute_with_validation("QA_Assistant", execution_result)

    print(f"Pipeline Success: {success}")
    print(f"Artifact ID: {result.get('artifact_id')}")
    print(f"Validation Stages: {result['stages']}")

    # Analyze patterns
    if success:
        patterns = pipeline.analyze_patterns()
        print(f"\nPattern Analysis:")
        print(f"  Error Patterns: {patterns['errors']}")
        print(f"  Performance: {patterns['performance']}")
        print(f"  Flakiness: {patterns['flakiness']}")


if __name__ == "__main__":
    example_usage()
