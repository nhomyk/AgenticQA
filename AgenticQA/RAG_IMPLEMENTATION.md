# RAG (Retrieval-Augmented Generation) in AgenticQA

## Overview

AgenticQA now implements **Weaviate-backed RAG** that combines deterministic validation gates with semantic retrieval for intelligent recommendations. Weaviate provides enterprise-grade vector search with persistence, scalability, and production-ready performance.

**Key Upgrade:** Replaced in-memory vector store with Weaviate for:
- ✅ **Persistence** - Survives restarts
- ✅ **Scalability** - Handles millions of documents
- ✅ **Performance** - O(1) approximate nearest neighbor search
- ✅ **Enterprise-Ready** - Used by Fortune 500 companies
- ✅ **Open Source** - No vendor lock-in

## Architecture

### Hybrid Approach: Deterministic Gates + RAG Insights

```
Agent Decision Making:
├── Deterministic Validation Gates (Unchanged)
│   ├── Rule-based checks
│   ├── Checksum validation
│   ├── Schema verification
│   └── Threshold-based decisions
│
└── RAG-Enhanced Insights (New)
    ├── Vector store retrieval
    ├── Semantic similarity search
    ├── Historical pattern matching
    └── Context-aware recommendations
```

**Key Principle:** RAG enhances decision-making WITHOUT changing gate logic. Agents remain deterministic for compliance and reliability while gaining intelligence from history.

## Components

### 1. Vector Store (`weaviate_store.py`)

**WeaviateVectorStore** provides persistent, scalable vector storage using Weaviate.

**Features:**
- ✅ **Persistent Storage** - Data survives restarts
- ✅ **Scalable** - Handles millions of documents  
- ✅ **Hybrid Search** - BM25 + Vector similarity
- ✅ **Auto-Collection** - Schemas created automatically
- ✅ **Local + Cloud** - Docker for dev, Weaviate Cloud for production
- ✅ **Performance Monitoring** - Stats and metrics built-in

**Collection Types:**
- `test_results` - Test execution history
- `errors` - Error patterns and resolutions
- `compliance_rules` - Regulatory requirements
- `performance_patterns` - Performance optimizations
- `agent_decisions` - Agent decision history

```python
from agenticqa.rag import WeaviateVectorStore, VectorDocument

# Connect to local or cloud Weaviate
store = WeaviateVectorStore(
    url="http://localhost:8080",  # Local Docker
    api_key=None,  # Not needed for local
    collection_name="test_results"
)

# Add document with embedding
doc = VectorDocument(
    id="doc_123",
    content="Test timeout in payment flow",
    embedding=[...],  # 768-dimensional
    metadata={"test_name": "checkout", "duration_ms": 5000},
    doc_type="test_result"
)
store.add_document(doc)

# Search similar documents
results = store.search(
    query_embedding=query_embedding,
    limit=5,
    threshold=0.7,
    where_filter={"test_name": "checkout"}  # Optional BM25 filtering
)

# Get statistics
stats = store.stats()
print(f"Collection: {stats['name']}, Docs: {stats['doc_count']}")
```

**Connection Methods:**

```python
# Local Docker (development)
store = WeaviateVectorStore(
    url="http://localhost:8080",
    collection_name="test_results"
)

# Weaviate Cloud (production)
store = WeaviateVectorStore(
    url="https://cluster-name.weaviate.network",
    api_key="YOUR_API_KEY",
    collection_name="test_results"
)

# Auto-cleanup with context manager
with WeaviateVectorStore(...) as store:
    store.add_document(doc)
    results = store.search(...)
```

### 2. Embeddings (`embeddings.py`)

Converts text to dense vector representations for semantic search.

**Embedder Types:**

#### SimpleHashEmbedder (Default)
- Lightweight and fast
- Uses character/word n-grams + syntax patterns
- Deterministic (same input = same embedding)
- Good for test automation context

```python
from agenticqa.rag import SimpleHashEmbedder

embedder = SimpleHashEmbedder(embedding_dim=768)
embedding = embedder.embed("Test timeout in checkout flow")
```

#### SemanticEmbedder (ML-based)
- Uses `sentence-transformers` for semantic understanding
- Better semantic similarity
- Falls back to SimpleHashEmbedder if transformers unavailable

```python
from agenticqa.rag import SemanticEmbedder

embedder = SemanticEmbedder(model_name="all-MiniLM-L6-v2")
embedding = embedder.embed("Test timeout in checkout flow")
```

#### Specialized Embedders
- `TestResultEmbedder` - For test results
- `ErrorEmbedder` - For errors/exceptions
- `ComplianceRuleEmbedder` - For compliance rules
- `PerformancePatternEmbedder` - For performance patterns

```python
from agenticqa.rag import TestResultEmbedder

test_embedder = TestResultEmbedder()
embedding = test_embedder.embed_test_result({
    "test_name": "checkout_flow",
    "status": "failed",
    "error_message": "Timeout"
})
```

### 3. RAG Retriever (`retriever.py`)

Retrieves relevant context from vector store to enhance agent decisions.

**Retrieval Methods:**

```python
from agenticqa.rag import RAGRetriever

retriever = RAGRetriever(vector_store, embedder)

# Retrieve similar tests
similar_tests = retriever.retrieve_similar_tests(
    test_name="checkout_flow",
    test_type="integration",
    k=5
)

# Retrieve similar errors
similar_errors = retriever.retrieve_similar_errors(
    error_type="TimeoutError",
    message="Request timeout after 30s",
    k=5
)

# Retrieve applicable compliance rules
compliance_rules = retriever.retrieve_applicable_compliance_rules(
    context="Customer data handling",
    regulations=["GDPR", "CCPA"],
    k=10
)

# Get recommendations for agent
recommendations = retriever.get_agent_recommendations(
    agent_type="qa",
    context={
        "test_name": "checkout",
        "test_type": "integration"
    }
)
```

### 4. Multi-Agent RAG (`retriever.py`)

Orchestrates RAG across all agents with learning feedback loop.

```python
from agenticqa.rag import MultiAgentRAG

rag_system = MultiAgentRAG(vector_store, embedder)

# Augment agent context with RAG insights
augmented_context = rag_system.augment_agent_context(
    agent_type="qa",
    agent_context={
        "test_name": "checkout",
        "test_type": "integration"
    }
)
# Returns: original context + rag_recommendations + rag_insights_count

# Log agent execution for future learning
rag_system.log_agent_execution(
    agent_type="qa",
    execution_result={
        "test_name": "checkout",
        "status": "failed",
        "error_message": "Payment declined"
    }
)
```

## Integration with Agents

### QA Agent + RAG

```python
# QA Agent execution with RAG insights
context = {
    "test_name": "checkout_flow",
    "test_type": "integration",
    "pass_threshold": 0.95
}

# Augment with RAG
augmented_context = rag_system.augment_agent_context("qa", context)

# Agent uses insights without changing gate logic
# Deterministic: pass if current_pass_rate >= pass_threshold
# RAG: adds rag_recommendations for context

if augmented_context["current_pass_rate"] >= augmented_context["pass_threshold"]:
    decision = "PASS"
else:
    decision = "FAIL"

# But agent can also consider recommendations
high_confidence_insights = augmented_context.get("high_confidence_insights", [])
if high_confidence_insights:
    # Consider insights for enhanced decision quality
    pass
```

### Performance Agent + RAG

```python
context = {
    "operation": "checkout_api_call",
    "current_metrics": {
        "latency_ms": 450,
        "cpu_percent": 85
    }
}

# Get similar performance patterns
augmented = rag_system.augment_agent_context("performance", context)

# Recommendations might include:
# "Similar operation baseline: 200ms. Suggestion: Add caching layer"
```

### Compliance Agent + RAG

```python
context = {
    "context": "Customer SSN in logs",
    "regulations": ["GDPR", "HIPAA", "CCPA"]
}

# Get applicable compliance rules
augmented = rag_system.augment_agent_context("compliance", context)

# Recommendations might include compliance rules that apply
```

### DevOps Agent + RAG

```python
context = {
    "error_type": "TimeoutError",
    "message": "Connection timeout to payment service"
}

# Get similar errors and resolutions
augmented = rag_system.augment_agent_context("devops", context)

# Recommendations might include:
# "Similar error occurred 5 times. Resolution: Increase timeout threshold"
```

## Data Flow

### Learning Cycle

```
1. Agent Execution
   └─> Produces test result, error, compliance check, or deployment result

2. Log to Vector Store
   └─> Convert to embedding
       └─> Store with metadata

3. Future Retrieval
   └─> New agent execution
       └─> Create query embedding
           └─> Search vector store
               └─> Find similar past executions
                   └─> Generate recommendations

4. Enhanced Decision
   └─> Agent uses recommendation context
       └─> Makes better decision (gate logic unchanged)
           └─> Executes (deterministically)
               └─> Logs result (cycle continues)
```

### Example: Test Failure Pattern Learning

**Day 1:**
```
Test "checkout_flow" fails with "Timeout error"
└─> Logged to vector store
    └─> Added to test_result documents
```

**Day 2:**
```
Test "checkout_flow" runs again
└─> Create query embedding for test
    └─> Search vector store
        └─> Find Day 1 failure (similar test, same error)
            └─> Generate recommendation: "Similar test failed before due to slow payment service. Consider timeout handling."
                └─> Agent execution proceeds (gate logic unchanged)
                    └─> But agent is aware of history
```

**Day 3:**
```
Test "checkout_api_call" (different test, similar payload)
└─> Create query embedding
    └─> Search vector store
        └─> Find both Day 1 and Day 2 data
            └─> Generate stronger recommendation: "Pattern detected: Payment service calls prone to timeout. Suggestion: Implement circuit breaker."
                └─> Agent uses insight for better decision quality
```

## Storage Structure

RAG documents stored alongside artifact store:

```
.test-artifact-store/
├── raw/
│   └── [agent outputs]
├── metadata/
│   └── [execution metadata]
├── rag/
│   ├── vector_store.json
│   ├── embeddings_cache/
│   └── retrieval_logs.json
└── [other artifact store dirs]
```

## Configuration

### Embedder Selection

```python
from agenticqa.rag import EmbedderFactory

# Set default embedder for your use case
simple_embedder = EmbedderFactory.get_embedder("simple")
semantic_embedder = EmbedderFactory.get_embedder("semantic")

# Use in RAG system
rag_system = MultiAgentRAG(vector_store, embedder=simple_embedder)
```

### Vector Store Size

```python
from agenticqa.rag import VectorStore

# Limit memory usage
store = VectorStore(max_documents=10000)

# Automatic eviction when exceeding max
# Keeps most recent documents
```

### Retrieval Thresholds

```python
# Lower threshold = more results (broader retrieval)
# Higher threshold = fewer results (only very similar)

# Default thresholds in retriever:
# - test_result: 0.5 (find patterns)
# - error: 0.5 (find similar errors)
# - compliance_rule: 0.4 (broader match for rules)
# - performance_pattern: 0.5 (find patterns)

# Adjust in retriever.py for your needs
```

## Performance Characteristics

| Operation | Time | Notes |
|-----------|------|-------|
| Embed text | O(n) | n = text length, fast for typical inputs |
| Add document | O(1) | Amortized with eviction |
| Search | O(d) | d = number of documents, cosine similarity |
| Get recommendations | O(d) | Multiple searches, filtered by type |

**Typical Performance:**
- Embed: <10ms
- Add: <1ms
- Search 10K docs: ~50ms
- Get recommendations: ~100-200ms

## Best Practices

### 1. Deterministic Gates First, RAG Second

```python
# GOOD: Gate logic unchanged, RAG adds context
if quality_metrics >= threshold:
    decision = "PASS"  # Deterministic
    recommendations = rag_recommendations  # Context
else:
    decision = "FAIL"  # Deterministic
    insights = rag_recommendations  # For debugging

# BAD: Changing gate logic based on RAG
if quality_metrics >= threshold - rag_adjustment:  # Don't do this!
    decision = "PASS"
```

### 2. Maintain Retrieval Quality

```python
# Log meaningful metadata
multi_rag.log_agent_execution("qa", {
    "test_name": "checkout_flow",  # Specific
    "status": "failed",
    "error_message": "Timeout error",  # Descriptive
    "root_cause": "Slow payment service",  # Important
    "recommendation": "Add timeout handling"  # Actionable
})
```

### 3. Monitor RAG Effectiveness

```python
# Track recommendation quality
for recommendation in augmented_context["rag_recommendations"]:
    confidence = recommendation["confidence"]
    was_helpful = check_if_helped(recommendation)
    
    # Adjust thresholds if many low-confidence recommendations
    if confidence < 0.5:
        consider_lowering_threshold()
```

## Limitations and Future Improvements

### Current Limitations
- Vector store is in-memory (cleared on restart)
- Search is O(n) linear scan (slow for very large stores)
- Embeddings are text-based only

### Future Improvements
- Persistent vector store (save/load to artifact store)
- Indexed search (ANN libraries like FAISS)
- Multi-modal embeddings (text + metrics + code)
- Active learning (system suggests what to log)
- Confidence calibration (improve threshold selection)

## Example: Complete RAG Integration

```python
from agenticqa.rag import (
    VectorStore,
    SimpleHashEmbedder,
    MultiAgentRAG
)

# 1. Initialize RAG system
vector_store = VectorStore(max_documents=10000)
embedder = SimpleHashEmbedder()
rag_system = MultiAgentRAG(vector_store, embedder)

# 2. Agent execution with RAG
def execute_qa_agent(test_config):
    # Original context
    context = {
        "test_name": test_config["name"],
        "test_type": test_config["type"],
        "pass_threshold": 0.95
    }
    
    # Augment with RAG insights
    augmented_context = rag_system.augment_agent_context("qa", context)
    
    # Run tests (original logic)
    result = run_tests(test_config)
    result.update({
        "current_pass_rate": calculate_pass_rate(result),
        "rag_insights": augmented_context.get("rag_recommendations", [])
    })
    
    # Make decision (deterministic)
    if result["current_pass_rate"] >= context["pass_threshold"]:
        decision = "PASS"
    else:
        decision = "FAIL"
    
    # Log for future learning
    rag_system.log_agent_execution("qa", result)
    
    return {
        "decision": decision,
        "insights": result["rag_insights"],
        "pass_rate": result["current_pass_rate"]
    }

# 3. Multiple executions learn from each other
results = []
for test_batch in test_batches:
    result = execute_qa_agent(test_batch)
    results.append(result)
    
    # System gets smarter with each execution
    # Recommendations become more relevant
    # Patterns become more apparent
```

## Troubleshooting

### RAG not providing recommendations
- **Cause:** Not enough documents in vector store
- **Fix:** Run more executions to populate store
- **Expected:** First 10-20 executions have limited recommendations

### Recommendations seem irrelevant
- **Cause:** Similarity threshold too low
- **Fix:** Increase threshold in retriever.py (0.5 → 0.6)
- **Check:** Verify metadata is meaningful

### Memory usage growing
- **Cause:** Vector store exceeding max_documents
- **Fix:** Increase max_documents or decrease frequency of logging
- **Monitor:** Check store.stats() periodically

---

*RAG is a powerful addition to AgenticQA that enables intelligent recommendations while maintaining deterministic reliability. Use it to learn from history and improve decision quality over time.*
