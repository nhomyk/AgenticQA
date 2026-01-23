# Agent Integration with Data Store

All agents now have integrated knowledge of and utilization of the data store.

## 🤖 Agent Types

### 1. **QA Assistant Agent**
- Analyzes test results and provides feedback
- Uses historical patterns to identify failure trends
- Recommends test stabilization improvements
- Data: test results, pass/fail rates, coverage metrics

### 2. **Performance Agent**
- Monitors execution performance metrics
- Tracks latency, memory usage, throughput
- Suggests optimizations based on patterns
- Data: duration, memory, CPU usage

### 3. **Compliance Agent**
- Ensures regulatory compliance (SOC2, GDPR, HIPAA)
- Validates data encryption and PII masking
- Maintains audit logs
- Data: encryption status, audit flags, compliance checks

### 4. **DevOps Agent**
- Manages deployments and infrastructure
- Runs health checks and monitoring
- Orchestrates rollouts and rollbacks
- Data: deployment versions, environment status

## 📦 Data Store Integration

Each agent automatically:

✅ **Records executions** to the data store with SHA256 checksums
✅ **Accesses historical patterns** for smarter decision-making
✅ **Analyzes failure trends** from compiled data
✅ **Detects flaky tests/processes** across time
✅ **Generates performance insights** from accumulated metrics

## 🔄 Execution Flow

```
Agent Execution
    ↓
Perform Task (QA, Perf, Compliance, DevOps)
    ↓
Validate Data (Schema, PII, Encryption)
    ↓
Store Result (with UUID, checksum, metadata)
    ↓
Query Historical Patterns
    ↓
Make Data-Driven Recommendations
    ↓
Return Enhanced Result with Insights
```

## 🚀 Usage

### Python - Direct Agent Execution

```python
from src.agents import QAAssistantAgent, AgentOrchestrator

# Single agent
qa_agent = QAAssistantAgent()
results = qa_agent.execute({
    "total": 150,
    "passed": 145,
    "failed": 5,
    "coverage": 94.2
})

# All agents at once
orchestrator = AgentOrchestrator()
all_results = orchestrator.execute_all_agents(unified_data)

# Get pattern insights
insights = qa_agent.get_pattern_insights()
```

### REST API - Agent Orchestration

```bash
# Execute all agents
curl -X POST http://localhost:8000/api/agents/execute \
  -H "Content-Type: application/json" \
  -d '{
    "test_results": {"total": 150, "passed": 145, "failed": 5},
    "execution_data": {"duration_ms": 2500, "memory_mb": 256},
    "compliance_data": {"encrypted": true, "pii_masked": true},
    "deployment_config": {"version": "1.0.0", "environment": "production"}
  }'

# Get agent insights
curl http://localhost:8000/api/agents/insights

# Search data store
curl -X POST http://localhost:8000/api/datastore/search \
  -H "Content-Type: application/json" \
  -d '{"source": "QA_Assistant"}'

# Get data store stats
curl http://localhost:8000/api/datastore/stats

# Get patterns
curl http://localhost:8000/api/datastore/patterns
```

## 📊 Data Flow

1. **Agent Execution**: Agent performs its task (testing, monitoring, etc.)
2. **Data Validation**: All output validated against schema
3. **Store Artifact**: Result stored with metadata and checksum
4. **Pattern Analysis**: Compiled data analyzed for trends
5. **Intelligence**: Insights feed back to agents for smarter decisions

## 🔐 Security

All agent data passes through:
- Schema validation
- PII detection and masking
- Data immutability verification
- SHA256 integrity checks
- Encryption readiness validation

## 📁 Files

- `src/agents.py` - Agent base class and implementations
- `example_agent_integration.py` - Standalone execution examples
- `agent_api.py` - FastAPI REST endpoint for agent orchestration
- `src/data_store/` - Data store modules

## 🚄 Running Agents

**Standalone (Python):**
```bash
python example_agent_integration.py
```

**API Server:**
```bash
pip install fastapi uvicorn
python -m uvicorn agent_api:app --reload
```

## 📈 Metrics & Insights

Each agent can access:
- Error patterns and frequencies
- Performance trends (latency, throughput)
- Flakiness detection (10-90% failure rate)
- Execution statistics
- Historical comparisons

Example:
```python
qa_agent = QAAssistantAgent()
patterns = qa_agent.get_pattern_insights()
# Returns: errors, performance, flakiness data from compiled history
```

## 🔄 Continuous Intelligence

As more executions run:
1. More data accumulates in `.test-artifact-store/`
2. Patterns become more accurate
3. Agents make smarter recommendations
4. System becomes self-improving and self-optimizing
