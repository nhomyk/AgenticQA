"""Data Quality Testing Examples and Integration Tests"""

from src.data_store.data_quality_pipeline import DataQualityValidatedPipeline
from src.agents import QAAssistantAgent, AgentOrchestrator
from datetime import datetime


def example_pre_execution_quality_check():
    """Example: Pre-execution data quality validation"""
    print("\n" + "=" * 70)
    print("EXAMPLE 1: PRE-EXECUTION DATA QUALITY CHECK")
    print("=" * 70)

    pipeline = DataQualityValidatedPipeline()

    # Simulate input data
    input_data = {
        "timestamp": datetime.utcnow().isoformat(),
        "data": {
            "test_count": 150,
            "pass_count": 145,
            "fail_count": 5,
        },
    }

    print("\nValidating input data before agent execution...")
    is_valid, result = pipeline.validate_input_data("QA_Assistant", input_data)

    print(f"Input validation result: {'PASS' if is_valid else 'FAIL'}")
    if "quality_tests" in result:
        quality = result["quality_tests"]
        print(f"Quality tests: {quality['summary']['passed']}/{quality['summary']['total_tests']} passed")


def example_post_execution_quality_check():
    """Example: Post-execution data quality validation"""
    print("\n" + "=" * 70)
    print("EXAMPLE 2: POST-EXECUTION DATA QUALITY CHECK")
    print("=" * 70)

    pipeline = DataQualityValidatedPipeline()

    # Simulate execution result
    execution_result = {
        "timestamp": datetime.utcnow().isoformat(),
        "agent_name": "QA_Assistant",
        "status": "success",
        "output": {
            "total_tests": 150,
            "passed": 145,
            "failed": 5,
            "recommendations": ["Stabilize flaky tests"],
        },
        "metadata": {},
    }

    print("\nValidating output data after agent execution...")
    is_valid, result = pipeline.execute_with_validation("QA_Assistant", execution_result)

    print(f"Execution validation result: {'PASS' if is_valid else 'FAIL'}")
    if "post_execution_quality" in result:
        quality = result["post_execution_quality"]
        print(f"Quality tests: {quality['summary']['passed']}/{quality['summary']['total_tests']} passed")
        print(f"All quality tests passed: {quality['summary']['all_passed']}")


def example_deployment_validation():
    """Example: Full deployment validation with data consistency checks"""
    print("\n" + "=" * 70)
    print("EXAMPLE 3: DEPLOYMENT VALIDATION")
    print("=" * 70)

    pipeline = DataQualityValidatedPipeline()

    print("\nRunning deployment validation...")
    deployment_result = pipeline.run_deployment_validation()

    print(f"\nReady for deployment: {deployment_result['ready_for_deployment']}")
    print(f"Export path: {deployment_result.get('export_path', 'N/A')}")


def example_agent_with_quality_checks():
    """Example: Agent execution with integrated quality checks"""
    print("\n" + "=" * 70)
    print("EXAMPLE 4: AGENT WITH INTEGRATED QUALITY CHECKS")
    print("=" * 70)

    # Create agent (uses DataQualityValidatedPipeline internally)
    qa_agent = QAAssistantAgent()

    test_results = {
        "total": 150,
        "passed": 145,
        "failed": 5,
        "coverage": 94.2,
    }

    print("\nExecuting QA agent with data quality validation...")
    result = qa_agent.execute(test_results)

    print(f"Agent execution result: {result}")
    print(f"Execution history with quality metadata: {qa_agent.execution_history}")


def example_orchestrator_with_quality():
    """Example: Orchestrator with quality validation across all agents"""
    print("\n" + "=" * 70)
    print("EXAMPLE 5: ORCHESTRATOR WITH CROSS-AGENT QUALITY VALIDATION")
    print("=" * 70)

    orchestrator = AgentOrchestrator()

    unified_data = {
        "test_results": {
            "total": 150,
            "passed": 145,
            "failed": 5,
            "coverage": 94.2,
        },
        "execution_data": {"duration_ms": 2500, "memory_mb": 256},
        "compliance_data": {
            "encrypted": True,
            "pii_masked": True,
            "audit_enabled": True,
        },
        "deployment_config": {
            "version": "1.0.0",
            "environment": "production",
        },
    }

    print("\nExecuting all agents with quality validation...")
    results = orchestrator.execute_all_agents(unified_data)

    print(f"\nAll agents executed with quality checks")
    for agent_name, result in results.items():
        print(f"  {agent_name}: {result.get('status', 'completed')}")


if __name__ == "__main__":
    print("Data Quality Testing Examples")
    print(f"Started at: {datetime.utcnow().isoformat()}")

    # Run examples
    example_pre_execution_quality_check()
    example_post_execution_quality_check()
    example_deployment_validation()
    example_agent_with_quality_checks()
    example_orchestrator_with_quality()

    print("\n" + "=" * 70)
    print("All data quality examples completed successfully!")
    print("=" * 70)
