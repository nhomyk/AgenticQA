"""
Python SDK Example 2: Remote API Client

This example shows how to connect to a remote AgenticQA server
and use it for distributed QA testing.
"""

from agenticqa.client import RemoteClient

# Connect to remote AgenticQA server
client = RemoteClient("http://agenticqa-server.example.com:8000")

# Check if server is healthy
if not client.health_check():
    print("❌ Server is not available!")
    exit(1)

print("✅ Connected to AgenticQA server")

# Execute agents on test data
test_data = {
    "code": "def hello(name): return f'Hello, {name}!'",
    "tests": "assert hello('World') == 'Hello, World!'",
}

results = client.execute_agents(test_data)
print("\n🎯 Agent Execution Results:")
print(f"  QA Status: {results.get('qa_agent', {}).get('status', 'unknown')}")
print(f"  Performance: {results.get('performance_agent', {}).get('status', 'unknown')}")
print(f"  Compliance: {results.get('compliance_agent', {}).get('status', 'unknown')}")
print(f"  DevOps: {results.get('devops_agent', {}).get('status', 'unknown')}")

# Get agent insights
insights = client.get_agent_insights()
print(f"\n💡 Agent Insights: {len(insights)} items")

# Get recent QA agent history
qa_history = client.get_agent_history("qa", limit=10)
print(f"\n📝 Recent QA Executions: {len(qa_history)}")
for execution in qa_history[:3]:
    print(f"  - {execution.get('timestamp')}: {execution.get('status')}")

# Search for specific artifacts
artifacts = client.search_artifacts("type:test-result", limit=20)
print(f"\n🔍 Found {len(artifacts)} test artifacts")

# Get data store statistics
stats = client.get_datastore_stats()
print(f"\n📊 Data Store Statistics:")
print(f"  Total Artifacts: {stats.get('total_artifacts', 0)}")
print(f"  Storage Size: {stats.get('storage_size', 0)} bytes")

# Get detected patterns
patterns = client.get_patterns()
print(f"\n🎯 Detected Patterns:")
print(f"  Failure Patterns: {len(patterns.get('failure_patterns', []))}")
print(f"  Performance Trends: {len(patterns.get('performance_trends', []))}")
print(f"  Flaky Tests: {len(patterns.get('flakiness_detection', []))}")

# Clean up
client.close()
