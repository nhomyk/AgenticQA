# Neo4j Graph Schema for Agent Delegation

## Overview

This document defines the Neo4j graph schema for tracking agent delegations, collaboration patterns, and execution history in AgenticQA.

## Node Types

### 1. Agent Node
Represents an AI agent in the system.

```cypher
CREATE (:Agent {
  name: String!,           // e.g., "SDET_Agent", "SRE_Agent"
  type: String,            // e.g., "qa", "devops", "compliance"
  created_at: DateTime,
  last_active: DateTime,
  total_executions: Integer,
  total_delegations_made: Integer,
  total_delegations_received: Integer,
  success_rate: Float      // Overall success rate
})
```

### 2. Execution Node
Represents a single agent execution/task.

```cypher
CREATE (:Execution {
  execution_id: String!,   // Unique execution ID
  agent_name: String!,
  deployment_id: String,   // CI/CD deployment ID
  pipeline_run: String,    // GitHub Actions run ID
  task_type: String,       // e.g., "coverage_analysis", "linting_fix"
  status: String!,         // "success", "failed", "partial"
  timestamp: DateTime!,
  duration_ms: Float,
  error_message: String,
  metadata: Map            // Additional context
})
```

### 3. Deployment Node
Represents a CI/CD pipeline deployment.

```cypher
CREATE (:Deployment {
  deployment_id: String!,
  pipeline_run: String!,
  branch: String,
  commit_sha: String,
  started_at: DateTime!,
  completed_at: DateTime,
  status: String,          // "success", "failed", "in_progress"
  total_delegations: Integer,
  max_delegation_depth: Integer
})
```

## Relationship Types

### 1. DELEGATES_TO
Represents a delegation from one agent to another.

```cypher
CREATE (from:Agent)-[:DELEGATES_TO {
  delegation_id: String!,
  execution_id: String,    // Source execution
  task: Map!,              // Task details
  timestamp: DateTime!,
  duration_ms: Float,
  depth: Integer!,         // Delegation chain depth
  status: String!,         // "success", "failed", "timeout"
  error_message: String,
  result: Map              // Delegation result
}]->(to:Agent)
```

### 2. EXECUTED_BY
Links an Execution to the Agent that ran it.

```cypher
CREATE (execution:Execution)-[:EXECUTED_BY]->(agent:Agent)
```

### 3. PART_OF_DEPLOYMENT
Links an Execution to its parent Deployment.

```cypher
CREATE (execution:Execution)-[:PART_OF_DEPLOYMENT]->(deployment:Deployment)
```

### 4. FOLLOWS
Represents sequential delegation in a chain.

```cypher
CREATE (execution1:Execution)-[:FOLLOWS {
  delegation_id: String!,
  depth: Integer!
}]->(execution2:Execution)
```

### 5. ROOT_OF
Links the first execution in a delegation chain.

```cypher
CREATE (deployment:Deployment)-[:ROOT_OF]->(execution:Execution)
```

## Indexes

```cypher
-- Agent lookup
CREATE INDEX agent_name_idx FOR (a:Agent) ON (a.name);

-- Execution lookup
CREATE INDEX execution_id_idx FOR (e:Execution) ON (e.execution_id);
CREATE INDEX execution_timestamp_idx FOR (e:Execution) ON (e.timestamp);
CREATE INDEX execution_deployment_idx FOR (e:Execution) ON (e.deployment_id);

-- Deployment lookup
CREATE INDEX deployment_id_idx FOR (d:Deployment) ON (d.deployment_id);
CREATE INDEX deployment_pipeline_idx FOR (d:Deployment) ON (d.pipeline_run);
CREATE INDEX deployment_timestamp_idx FOR (d:Deployment) ON (d.started_at);

-- Delegation relationship lookup
CREATE INDEX delegation_timestamp FOR ()-[r:DELEGATES_TO]-() ON (r.timestamp);
CREATE INDEX delegation_status FOR ()-[r:DELEGATES_TO]-() ON (r.status);
```

## Constraints

```cypher
-- Unique agent names
CREATE CONSTRAINT agent_name_unique FOR (a:Agent) REQUIRE a.name IS UNIQUE;

-- Unique execution IDs
CREATE CONSTRAINT execution_id_unique FOR (e:Execution) REQUIRE e.execution_id IS UNIQUE;

-- Unique deployment IDs
CREATE CONSTRAINT deployment_id_unique FOR (d:Deployment) REQUIRE d.deployment_id IS UNIQUE;
```

## Example Queries

### 1. Find Most Delegated-To Agent
```cypher
MATCH (a:Agent)<-[d:DELEGATES_TO]-()
RETURN a.name as agent,
       count(d) as delegation_count,
       avg(d.duration_ms) as avg_duration_ms
ORDER BY delegation_count DESC
LIMIT 5;
```

### 2. Analyze Delegation Chains
```cypher
MATCH path = (start:Agent)-[:DELEGATES_TO*]->(end:Agent)
WHERE length(path) > 1
RETURN start.name as origin,
       end.name as destination,
       length(path) as chain_length,
       [r in relationships(path) | r.duration_ms] as durations
ORDER BY chain_length DESC
LIMIT 10;
```

### 3. Find Circular Delegations (Should Be None!)
```cypher
MATCH path = (a:Agent)-[:DELEGATES_TO*]->(a)
RETURN path;
```

### 4. Delegation Success Rate by Agent Pair
```cypher
MATCH (from:Agent)-[d:DELEGATES_TO]->(to:Agent)
WITH from.name as from_agent,
     to.name as to_agent,
     count(d) as total,
     sum(CASE WHEN d.status = 'success' THEN 1 ELSE 0 END) as successes
RETURN from_agent,
       to_agent,
       total,
       successes,
       (toFloat(successes) / total) as success_rate
ORDER BY total DESC;
```

### 5. Find Bottleneck Agents
```cypher
MATCH (a:Agent)<-[d:DELEGATES_TO]-()
WHERE d.duration_ms > 1000  // Slow delegations
WITH a.name as agent,
     count(d) as slow_delegations,
     avg(d.duration_ms) as avg_duration,
     percentileCont(d.duration_ms, 0.95) as p95_duration
WHERE slow_delegations > 5
RETURN agent, slow_delegations, avg_duration, p95_duration
ORDER BY avg_duration DESC;
```

### 6. Deployment Timeline with Delegations
```cypher
MATCH (d:Deployment)-[:ROOT_OF]->(e:Execution)
MATCH path = (e)-[:FOLLOWS*0..]->(child:Execution)
RETURN d.deployment_id,
       d.status,
       d.started_at,
       [execution in nodes(path) | execution.agent_name] as execution_chain,
       length(path) as delegation_depth;
```

### 7. Find Optimal Delegation Path (GraphRAG!)
```cypher
// Given current task, find which agent historically succeeded
MATCH (from:Agent {name: $from_agent})-[d:DELEGATES_TO]->(to:Agent)
WHERE d.task.task_type = $task_type
  AND d.status = 'success'
  AND d.duration_ms < $acceptable_duration_ms
WITH to.name as recommended_agent,
     count(d) as success_count,
     avg(d.duration_ms) as avg_duration,
     stdDev(d.duration_ms) as duration_stddev
WHERE success_count >= 3  // At least 3 successful delegations
RETURN recommended_agent,
       success_count,
       avg_duration,
       duration_stddev,
       (success_count * 1000.0 / avg_duration) as priority_score
ORDER BY priority_score DESC
LIMIT 1;
```

### 8. Collaboration Network Visualization
```cypher
MATCH (from:Agent)-[d:DELEGATES_TO]->(to:Agent)
WITH from, to, count(d) as delegation_count
WHERE delegation_count > 2  // Filter noise
RETURN from, to, delegation_count;
```

## GraphRAG Integration

### Query Pattern: "What worked for similar tasks?"

```cypher
// Step 1: Get current context from application
// Step 2: Query Weaviate for semantic similarity
// Step 3: Use execution_ids from Weaviate to query Neo4j for delegation patterns
MATCH (e:Execution {execution_id: $execution_id_from_weaviate})
MATCH (e)-[:EXECUTED_BY]->(agent:Agent)
MATCH (agent)-[d:DELEGATES_TO WHERE d.status = 'success']->(:Agent)
RETURN d.task, d.result, d.duration_ms
ORDER BY e.timestamp DESC
LIMIT 5;
```

### Hybrid RAG Query Flow

```
1. User Request
   ↓
2. Query Weaviate (Semantic Search)
   → Returns: Similar past executions with embeddings
   ↓
3. Extract execution_ids from Weaviate results
   ↓
4. Query Neo4j (Graph Traversal)
   → Returns: Delegation chains, patterns, success paths
   ↓
5. Combine Results
   → Semantic context (Weaviate) + Relationship context (Neo4j)
   ↓
6. Return enriched recommendation to agent
```

## Performance Considerations

- **Indexes**: All timestamp and ID fields indexed for fast lookups
- **Pagination**: Use `SKIP` and `LIMIT` for large result sets
- **Query Optimization**: Use `EXPLAIN` and `PROFILE` to optimize slow queries
- **Data Retention**: Archive old delegations (>90 days) to keep graph performant
- **Batch Writes**: Use transactions to batch multiple delegation records

## Migration Strategy

1. **Phase 1**: Write to both in-memory tracker AND Neo4j (dual-write)
2. **Phase 2**: Validate Neo4j data matches in-memory
3. **Phase 3**: Read from Neo4j for analytics, in-memory for real-time
4. **Phase 4**: Migrate fully to Neo4j, deprecate in-memory tracker

## Security

- **Authentication**: Neo4j requires auth (user: neo4j, pass: agenticqa123)
- **Network**: Neo4j isolated to Docker network
- **Data Sanitization**: Sanitize task details before storing (no secrets!)
- **Access Control**: Only CI/CD pipeline can write, dashboards read-only
