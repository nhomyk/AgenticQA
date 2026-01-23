"""Agent execution examples and integration tests"""

from src.agents import (
    QAAssistantAgent,
    PerformanceAgent,
    ComplianceAgent,
    DevOpsAgent,
    AgentOrchestrator,
)
from datetime import datetime


def example_qa_agent():
    """Example: QA Agent analyzing test results"""
    print("\n" + "=" * 70)
    print("QA ASSISTANT AGENT EXAMPLE")
    print("=" * 70)

    agent = QAAssistantAgent()

    test_results = {
        "total": 150,
        "passed": 145,
        "failed": 5,
        "coverage": 94.2,
    }

    result = agent.execute(test_results)
    print(f"Analysis Result: {result}")

    # Get insights from historical data
    insights = agent.get_pattern_insights()
    print(f"Pattern Insights: {insights}")


def example_performance_agent():
    """Example: Performance Agent monitoring metrics"""
    print("\n" + "=" * 70)
    print("PERFORMANCE AGENT EXAMPLE")
    print("=" * 70)

    agent = PerformanceAgent()

    execution_data = {"duration_ms": 2500, "memory_mb": 256}

    result = agent.execute(execution_data)
    print(f"Analysis Result: {result}")


def example_compliance_agent():
    """Example: Compliance Agent checking requirements"""
    print("\n" + "=" * 70)
    print("COMPLIANCE AGENT EXAMPLE")
    print("=" * 70)

    agent = ComplianceAgent()

    compliance_data = {
        "encrypted": True,
        "pii_masked": True,
        "audit_enabled": True,
    }

    result = agent.execute(compliance_data)
    print(f"Compliance Check Result: {result}")


def example_devops_agent():
    """Example: DevOps Agent managing deployment"""
    print("\n" + "=" * 70)
    print("DEVOPS AGENT EXAMPLE")
    print("=" * 70)

    agent = DevOpsAgent()

    deployment_config = {
        "version": "1.0.0",
        "environment": "production",
    }

    result = agent.execute(deployment_config)
    print(f"Deployment Result: {result}")


def example_orchestrator():
    """Example: Run all agents together through orchestrator"""
    print("\n" + "=" * 70)
    print("AGENT ORCHESTRATOR EXAMPLE")
    print("=" * 70)

    orchestrator = AgentOrchestrator()

    # Prepare data for all agents
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

    # Execute all agents
    results = orchestrator.execute_all_agents(unified_data)
    print(f"\nOrchestrated Results:")
    for agent_name, result in results.items():
        print(f"  {agent_name}: {result}")

    # Get collective insights
    insights = orchestrator.get_agent_insights()
    print(f"\nCollective Agent Insights:")
    for agent_name, insight in insights.items():
        print(f"  {agent_name}: {insight}")


if __name__ == "__main__":
    print("AgenticQA Agent Integration Examples")
    print(f"Started at: {datetime.utcnow().isoformat()}")

    # Run individual agent examples
    example_qa_agent()
    example_performance_agent()
    example_compliance_agent()
    example_devops_agent()

    # Run orchestrator example
    example_orchestrator()

    print("\n" + "=" * 70)
    print("All agent examples completed successfully!")
    print("=" * 70)
