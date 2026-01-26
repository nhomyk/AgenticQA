# SDK Documentation

## Overview

AgenticQA provides comprehensive SDKs for both Python and TypeScript/JavaScript, making it easy to integrate intelligent QA automation into your projects.

### Quick Links
- **Python SDK**: `agenticqa` on PyPI (coming soon)
- **TypeScript SDK**: `agenticqa` on npm (coming soon)
- **REST API**: Available on port 8000 by default

---

## Python SDK

### Installation

```bash
pip install agenticqa
```

### Basic Usage

```python
from agenticqa import AgentOrchestrator

orchestrator = AgentOrchestrator()
results = orchestrator.execute_all_agents({
    "code": "...",
    "tests": "...",
})
```

### Remote Client

Connect to a remote AgenticQA server:

```python
from agenticqa.client import RemoteClient

client = RemoteClient("http://agenticqa-server.example.com:8000")
results = client.execute_agents({"code": "...", "tests": "..."})
patterns = client.get_patterns()
```

### CLI Usage

```bash
# Execute agents
agenticqa execute test_data.json

# View patterns
agenticqa patterns

# View statistics
agenticqa stats
```

### Key Classes

- **`AgentOrchestrator`**: Execute all agents simultaneously
- **`RemoteClient`**: Connect to remote AgenticQA API
- **`TestArtifactStore`**: Access test artifacts and patterns
- **`DataQualityValidatedPipeline`**: Run complete pipeline with validation

---

## TypeScript/JavaScript SDK

### Installation

```bash
npm install agenticqa
```

### Basic Usage

```typescript
import { AgenticQAClient } from 'agenticqa';

const client = new AgenticQAClient('http://localhost:8000');

const results = await client.executeAgents({
  code: '...',
  tests: '...',
});

const patterns = await client.getPatterns();
```

### React Integration

```typescript
import { AgenticQAClient } from 'agenticqa';

// Create client
const client = new AgenticQAClient();

// Fetch data
const insights = await client.getAgentInsights();
const stats = await client.getDatastoreStats();
```

### Key Methods

- `executeAgents(testData)`: Execute all agents
- `getAgentInsights(agentName?)`: Get agent recommendations
- `getPatterns()`: Get detected patterns
- `getDatastoreStats()`: Get data store statistics
- `searchArtifacts(query)`: Search test artifacts
- `healthCheck()`: Check server health

---

## REST API

### Authentication

Optional bearer token for authentication:

```bash
curl -H "Authorization: Bearer YOUR_TOKEN" http://localhost:8000/api/agents/execute
```

### Core Endpoints

- `POST /api/agents/execute` - Execute agents
- `GET /api/agents/insights` - Get agent insights
- `GET /api/agents/{name}/history` - Get agent history
- `GET /api/datastore/search` - Search artifacts
- `GET /api/datastore/artifact/{id}` - Get artifact
- `GET /api/datastore/stats` - Get statistics
- `GET /api/datastore/patterns` - Get patterns

---

## Examples

### CI/CD Integration

```python
from agenticqa import DataQualityValidatedPipeline

pipeline = DataQualityValidatedPipeline()
results = pipeline.execute_with_validation(test_data)

if results['devops_agent']['status'] == 'passed':
    print("✅ Ready to deploy!")
else:
    print("❌ Do not deploy!")
```

### Pattern Analysis

```python
from agenticqa import TestArtifactStore, PatternAnalyzer

store = TestArtifactStore()
analyzer = PatternAnalyzer(store)
patterns = analyzer.detect_patterns()

print(f"Failure patterns: {len(patterns['failure_patterns'])}")
print(f"Performance trends: {len(patterns['performance_trends'])}")
```

### Real-time Monitoring

```typescript
const client = new AgenticQAClient();

// Poll every 10 seconds
setInterval(async () => {
  const stats = await client.getDatastoreStats();
  const patterns = await client.getPatterns();
  
  console.log(`Artifacts: ${stats.total_artifacts}`);
  console.log(`Flaky tests: ${patterns.flakiness_detection.length}`);
}, 10000);
```

---

## Support

For issues, questions, or feature requests, visit the [GitHub repository](https://github.com/nhomyk/AgenticQA).

