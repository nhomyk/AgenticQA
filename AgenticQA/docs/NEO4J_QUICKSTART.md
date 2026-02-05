# Neo4j Integration Quick Start Guide

## 🚀 What You Just Built

Congratulations! You've just integrated **Neo4j graph database** into AgenticQA, enabling powerful **GraphRAG** (Graph Retrieval-Augmented Generation) capabilities.

### What This Means

**Before (Weaviate only):**
- ✅ Semantic similarity: "What similar situations did we encounter?"
- ❌ No structural context: "How did agents collaborate to solve it?"

**After (Weaviate + Neo4j):**
- ✅ Semantic similarity (Weaviate)
- ✅ Delegation patterns (Neo4j)
- ✅ **GraphRAG**: Combined intelligence!

---

## 📦 Setup (5 Minutes)

### 1. Install Neo4j Python Driver

```bash
pip install neo4j rich  # rich is for pretty analytics output
```

### 2. Start Neo4j with Docker Compose

```bash
cd /Users/nicholashomyk/mono/AgenticQA
docker-compose -f docker-compose.weaviate.yml up -d neo4j
```

**Verify it's running:**
```bash
docker ps | grep neo4j
```

### 3. Initialize Neo4j Schema

```python
from agenticqa.graph import DelegationGraphStore

store = DelegationGraphStore()
store.connect()
store.initialize_schema()
store.close()
```

**Or use the CLI:**
```bash
python -c "from agenticqa.graph import DelegationGraphStore; s = DelegationGraphStore(); s.connect(); s.initialize_schema(); s.close(); print('✓ Neo4j initialized')"
```

---

## 🎯 Quick Test

### Test 1: Record a Delegation

```python
from agenticqa.graph import DelegationGraphStore
import uuid

store = DelegationGraphStore()
store.connect()

# Create agents
store.create_or_update_agent("SDET_Agent", "qa")
store.create_or_update_agent("SRE_Agent", "devops")

# Record delegation
delegation_id = str(uuid.uuid4())
store.record_delegation(
    from_agent="SDET_Agent",
    to_agent="SRE_Agent",
    task={"task_type": "generate_tests", "file": "src/api.py"},
    delegation_id=delegation_id,
    depth=1
)

# Update with result
store.update_delegation_result(
    delegation_id=delegation_id,
    status="success",
    duration_ms=123.5,
    result={"tests_generated": 5}
)

print("✓ Delegation recorded to Neo4j!")
store.close()
```

### Test 2: Query Analytics

```python
from agenticqa.graph import DelegationGraphStore

store = DelegationGraphStore()
store.connect()

# Find most delegated-to agents
results = store.get_most_delegated_agents(limit=5)
for agent in results:
    print(f"{agent['agent']}: {agent['delegation_count']} delegations")

store.close()
```

### Test 3: Run Full Analytics Suite

```bash
python examples/neo4j_analytics.py
```

This will show you:
- Most delegated-to agents
- Delegation chains
- Circular delegation detection
- Success rates
- Bottleneck analysis
- GraphRAG recommendations

---

## 🌐 Neo4j Browser

**Access the Neo4j Browser UI:**

1. Open: http://localhost:7474
2. Login:
   - Username: `neo4j`
   - Password: `agenticqa123`

**Try these Cypher queries:**

```cypher
// View all agents
MATCH (a:Agent)
RETURN a;

// View delegation network
MATCH (from:Agent)-[d:DELEGATES_TO]->(to:Agent)
RETURN from, d, to;

// Find most delegated-to agent
MATCH (a:Agent)<-[d:DELEGATES_TO]-()
RETURN a.name, count(d) as delegations
ORDER BY delegations DESC
LIMIT 5;
```

---

## 🧪 Run Tests

```bash
# Make sure Neo4j is running first
docker-compose -f docker-compose.weaviate.yml up -d neo4j

# Run Neo4j tests
pytest tests/test_neo4j_delegation.py -v -s
```

---

## 📊 Real-World Usage

### Automatic Delegation Tracking (Already Enabled!)

The `DelegationTracker` now **automatically writes to Neo4j** when agents delegate tasks.

**In your CI/CD pipeline:**

```python
from agenticqa.collaboration import AgentRegistry
from src.agents import SDETAgent, SREAgent

# Initialize registry (tracker auto-connects to Neo4j)
registry = AgentRegistry()
sdet = SDETAgent()
sre = SREAgent()

registry.register_agent(sdet)
registry.register_agent(sre)

# This automatically records to Neo4j!
registry.reset_for_new_request("SDET_Agent")
result = sdet.delegate_to_agent("SRE_Agent", {
    "task": "generate_tests",
    "file": "src/api.py"
})

# View delegation summary
summary = registry.get_delegation_summary()
print(summary["delegation_path"])
```

### GraphRAG Recommendations

```python
from agenticqa.graph import create_hybrid_rag

# Initialize Hybrid RAG (Weaviate + Neo4j)
hybrid_rag = create_hybrid_rag()

# Get recommendation: Who should I delegate to?
recommendation = hybrid_rag.recommend_delegation_target(
    from_agent="SDET_Agent",
    task_context={"task_type": "generate_tests", "priority": "high"},
    task_type="generate_tests"
)

if recommendation:
    print(f"Recommended: {recommendation['recommendation']}")
    print(f"Confidence: {recommendation['confidence']}")
    print(f"Sources: {recommendation['sources']}")
```

---

## 📈 Analytics Dashboard Ideas

Here are some powerful analytics you can now build:

### 1. Agent Collaboration Network
```cypher
MATCH (from:Agent)-[d:DELEGATES_TO]->(to:Agent)
WHERE d.status = 'success'
WITH from, to, count(d) as weight
WHERE weight > 2
RETURN from, to, weight;
```
**Visualization:** Network graph showing which agents collaborate most

### 2. Delegation Performance Over Time
```cypher
MATCH ()-[d:DELEGATES_TO]->()
RETURN date(d.timestamp) as day,
       avg(d.duration_ms) as avg_duration,
       count(d) as delegations
ORDER BY day;
```
**Visualization:** Line chart of delegation performance trends

### 3. Success Rate Heatmap
```cypher
MATCH (from:Agent)-[d:DELEGATES_TO]->(to:Agent)
WITH from.name as from_agent,
     to.name as to_agent,
     count(d) as total,
     sum(CASE WHEN d.status = 'success' THEN 1 ELSE 0 END) as successes
WHERE total >= 3
RETURN from_agent, to_agent,
       (toFloat(successes) / total) as success_rate;
```
**Visualization:** Heatmap of agent pair success rates

---

## 🎓 For Your Shelf Interview

### Key Talking Points

**1. Multi-Model Architecture**
- "I implemented a polyglot persistence pattern combining Weaviate (vector) and Neo4j (graph)"
- "This enables GraphRAG - combining semantic similarity with structural relationship context"

**2. Real-World Graph Modeling**
- "Designed a graph schema for tracking agent delegations with 5 node types and 5 relationship types"
- "Implemented indexes and constraints for query performance"

**3. Production-Ready Features**
- "Dual-write pattern for gradual migration (in-memory + Neo4j)"
- "Connection pooling, error handling, graceful degradation"
- "Comprehensive test suite with pytest"

**4. Analytics Capabilities**
- "Built 8+ analytics queries: bottleneck detection, success rates, delegation chains"
- "Can detect circular delegations, find optimal delegation paths"
- "GraphRAG recommendations based on historical patterns"

### Demo Script

**5-Minute Demo:**

1. **Show Docker Compose setup** (multi-database architecture)
2. **Run analytics script** (`python examples/neo4j_analytics.py`)
3. **Open Neo4j Browser** (visual network graph)
4. **Show GraphRAG code** (hybrid query combining Weaviate + Neo4j)
5. **Explain schema design** (from `docs/NEO4J_SCHEMA.md`)

**Questions to Expect:**
- "How does Neo4j complement Weaviate?" → GraphRAG pattern
- "How do you handle failures?" → Graceful degradation, optional Neo4j
- "What about performance?" → Indexes, connection pooling, batch writes
- "How would you scale this?" → Neo4j clustering, read replicas

---

## 🔧 Configuration

### Environment Variables

```bash
# Neo4j connection (optional, defaults shown)
export NEO4J_URI="bolt://localhost:7687"
export NEO4J_USER="neo4j"
export NEO4J_PASSWORD="agenticqa123"

# Disable Neo4j (use in-memory only)
export ENABLE_NEO4J="false"
```

### Python Configuration

```python
from agenticqa.graph import DelegationGraphStore

# Custom connection
store = DelegationGraphStore(
    uri="bolt://production-neo4j:7687",
    user="readonly",
    password="secret",
    database="agenticqa_prod"
)
```

---

## 📚 Next Steps

1. **Explore Schema**: Read [NEO4J_SCHEMA.md](NEO4J_SCHEMA.md) for all queries
2. **Run Analytics**: `python examples/neo4j_analytics.py`
3. **Customize Queries**: Add your own analytics in `delegation_store.py`
4. **Build Dashboard**: Use Neo4j Browser or Bloom for visualization
5. **Integrate with CI**: Delegation tracking is automatic!

---

## 🐛 Troubleshooting

### "Neo4j not available"
```bash
# Check if Neo4j is running
docker ps | grep neo4j

# Check logs
docker logs agenticqa-neo4j

# Restart
docker-compose -f docker-compose.weaviate.yml restart neo4j
```

### "Authentication failed"
```bash
# Reset password
docker exec -it agenticqa-neo4j cypher-shell -u neo4j -p neo4j
# Then run: ALTER CURRENT USER SET PASSWORD FROM 'neo4j' TO 'agenticqa123';
```

### "Connection refused"
- Make sure port 7687 isn't blocked by firewall
- Check `docker-compose.weaviate.yml` has correct ports

---

## 🎉 Congratulations!

You now have:

✅ Neo4j graph database integrated
✅ Automatic delegation tracking
✅ GraphRAG capabilities (Weaviate + Neo4j)
✅ Powerful analytics queries
✅ Comprehensive tests
✅ Portfolio-ready demo for Shelf

**This is seriously impressive work.** You've built a production-grade, multi-database architecture with cutting-edge GraphRAG capabilities. This will absolutely stand out in your Shelf interview!

---

## 📞 Support

- **Schema Reference**: [NEO4J_SCHEMA.md](NEO4J_SCHEMA.md)
- **Neo4j Docs**: https://neo4j.com/docs/
- **GraphRAG Research**: https://arxiv.org/abs/2404.16130
- **Shelf Careers**: https://shelf.io/careers/

**Good luck with your Shelf interview! 🚀**
