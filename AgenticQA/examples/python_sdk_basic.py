"""
Python SDK Example 1: Basic Agent Orchestration

This example shows how to use AgenticQA locally for simple test automation.
"""

from agenticqa import AgentOrchestrator, TestArtifactStore

# Test data to analyze
test_data = {
    "code": """
def calculate_discount(price, discount_percent):
    if discount_percent < 0 or discount_percent > 100:
        raise ValueError("Invalid discount")
    return price * (1 - discount_percent / 100)
    """,
    "tests": """
import pytest
def test_valid_discount():
    assert calculate_discount(100, 10) == 90.0
def test_invalid_discount():
    with pytest.raises(ValueError):
        calculate_discount(100, 150)
    """,
    "performance_baseline": {"execution_time_ms": 2.5},
}

# Create orchestrator and execute all agents
orchestrator = AgentOrchestrator()
results = orchestrator.execute_all_agents(test_data)

print("✅ QA Agent Results:")
print(f"  Tests Passed: {results['qa_agent'].get('tests_passed', 0)}")
print(f"  Code Quality Score: {results['qa_agent'].get('quality_score', 0)}")

print("\n⚡ Performance Agent Results:")
print(f"  Execution Time: {results['performance_agent'].get('execution_time_ms', 0)}ms")
print(f"  Performance Status: {results['performance_agent'].get('status', 'unknown')}")

print("\n🔒 Compliance Agent Results:")
print(f"  Compliance Score: {results['compliance_agent'].get('compliance_score', 0)}")
print(f"  PII Detected: {results['compliance_agent'].get('pii_detected', False)}")

print("\n🚀 DevOps Agent Results:")
print(f"  Deployment Ready: {results['devops_agent'].get('ready_to_deploy', False)}")
print(f"  Risk Level: {results['devops_agent'].get('risk_level', 'unknown')}")

# Access data store to see patterns
store = TestArtifactStore()
print(f"\n📊 Data Store Artifacts: {len(store.master_index)}")
