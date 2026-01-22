# RAG Quick Start

Get RAG working in 10 minutes.

## 1. Automatic (CI/CD - No Setup Needed)

RAG indexing runs automatically:

```
GitHub Push
    ↓
Pipeline starts
    ↓
[Phase 0.5: RAG Indexing] ← Automatic
    ├─ Loads codebase
    ├─ Generates embeddings
    └─ Stores index
    ↓
Index ready for agents
```

**Status:** Check in GitHub Actions under "rag-indexing" job.

## 2. Manual Development Setup

### Development (Mock - Free)

```bash
# Generate index with mock embeddings
node src/rag/indexing.js

# Verify it works
node src/rag/verify-index.js
```

**Output:**
```
✅ Loaded 42 files
✅ Created 156 chunks
✅ Generated 156 embeddings
✅ Index ready
Cost: $0 (mock)
```

### Production (OpenAI - Accurate)

```bash
# Set API key
export OPENAI_API_KEY=sk-your-key

# Index with real embeddings
EMBEDDING_PROVIDER=openai node src/rag/indexing.js

# Verify
node src/rag/verify-index.js
```

**Output:**
```
✅ Loaded 42 files
✅ Created 156 chunks
✅ Generated 156 embeddings with OpenAI
✅ Index ready
Cost estimate: $0.03
```

## 3. Use in Your Agent

### Minimal Example

```javascript
const AgentWithRAG = require('./src/rag/agent-rag-mixin');

// Wrap ANY agent
const baseAgent = {
  async decide(task) {
    return `I think: ${task}`;
  }
};

const agent = new AgentWithRAG(baseAgent);
await agent.initialize();

// Use it
const result = await agent.decide('How should I test this?');
console.log(result);
// {
//   decision: "I think: How should I test this?",
//   ragContext: [
//     { source: "test/example.test.js", score: 0.92, preview: "..." },
//     { source: "docs/testing.md", score: 0.87, preview: "..." }
//   ],
//   latency: 245
// }
```

### Real Agent Example

```javascript
// compliance-agent.js
const ComplianceAgent = require('./compliance-agent');
const AgentWithRAG = require('./src/rag/agent-rag-mixin');

// Wrap it
const agent = new AgentWithRAG(ComplianceAgent);
await agent.initialize();

// Now it retrieves GDPR examples, security patterns, etc.
const decision = await agent.decide('Check GDPR compliance');
```

## 4. Configuration Options

### Environment Variables

```bash
# Enable RAG (default: false)
export RAG_ENABLED=true

# Choose embedding (default: mock)
export EMBEDDING_PROVIDER=mock    # Fast, free for dev
export EMBEDDING_PROVIDER=openai  # Accurate, costs $
export OPENAI_API_KEY=sk-...

# Choose storage (default: chroma)
export RAG_PROVIDER=chroma        # Local, fast, free
export RAG_PROVIDER=pinecone      # Cloud, persistent
export PINECONE_API_KEY=...
```

### Programmatic Config

```javascript
const vectorStore = new RAGVectorStore({
  provider: 'chroma',
  topK: 5,              // Return top-5 results
  scoreThreshold: 0.5,  // Min relevance (0-1)
  localPath: '.rag-index/chroma'
});

const embedder = new EmbeddingsProvider({
  provider: 'openai',
  dimension: 1536,
  batchSize: 10
});

const loader = new DocumentLoader({
  chunkSize: 500,
  overlapSize: 50,
  extensions: ['.js', '.md']
});
```

## 5. Monitor Performance

```javascript
const agent = new AgentWithRAG(myAgent);
await agent.initialize();

// Make some decisions
for (let i = 0; i < 10; i++) {
  await agent.decide(`Task ${i}`);
}

// Check performance
const stats = agent.getRAGStats();
console.log(`
✓ Success rate: ${stats.successfulRetrievals}/${stats.successfulRetrievals + stats.failedRetrievals}
✓ Avg latency: ${stats.averageLatency}ms
✓ Cost estimate: $${stats.embedderStats.costEstimate}
`);
```

## 6. Debug Retrieval

```javascript
const agent = new AgentWithRAG(myAgent);
await agent.initialize();

// Get context for a query
const context = await agent.getContextForQuery('write unit test');

// See what was retrieved
context.slice(0, 3).forEach(item => {
  console.log(`${item.source} (${(item.score*100).toFixed(0)}%)`);
  console.log(`  ${item.content.substring(0, 80)}...`);
});
```

## 7. Production Checklist

- [ ] Enable `RAG_ENABLED=true` in GitHub Secrets
- [ ] Set `EMBEDDING_PROVIDER=openai` and `OPENAI_API_KEY`
- [ ] Set `RAG_PROVIDER=pinecone` and API key (or use Chroma)
- [ ] Run indexing: `EMBEDDING_PROVIDER=openai node src/rag/indexing.js`
- [ ] Verify index: `node src/rag/verify-index.js`
- [ ] Monitor costs with `getRAGStats()`
- [ ] Test in staging before production

## 8. Troubleshooting

### Problem: "Index not found"
```bash
# Solution: Run indexing
node src/rag/indexing.js
```

### Problem: "Slow retrievals (>1000ms)"
```bash
# Solution 1: Use Pinecone
export RAG_PROVIDER=pinecone

# Solution 2: Reduce topK
export RAG_TOP_K=3
```

### Problem: "High costs"
```bash
# Solution: Use mock in development
export EMBEDDING_PROVIDER=mock  # Free!
```

### Problem: "Can't connect to Pinecone"
```bash
# Solution: Check env vars
echo $PINECONE_API_KEY
echo $PINECONE_INDEX

# Test connection
node -e "const {RAGVectorStore} = require('./src/rag/vector-store'); new RAGVectorStore({provider:'pinecone'}).initialize().then(console.log)"
```

## 9. Cost Examples

### Development (Mock)
```
Tokens: 12,400 per indexing
Cost: $0
Queries: Free
```

### Small Production (OpenAI)
```
Indexing: 50,000 tokens = $0.001
Per query: 50 tokens = $0.000001
1000 queries/month = $0.03
```

### Large Production (Pinecone)
```
Monthly: $0.04 per 1M API calls
10,000 queries/month = $0.0004
Storage: ~$1/month
Total: ~$1.04/month
```

## 10. Next Steps

1. **Try it:** `node src/rag/indexing.js`
2. **Verify:** `node src/rag/verify-index.js`
3. **Use it:** Wrap your agent with `AgentWithRAG`
4. **Monitor:** Check `getRAGStats()`
5. **Scale:** Enable in CI/CD and production

## Files

- [RAG_AGENT_INTEGRATION.md](RAG_AGENT_INTEGRATION.md) - Complete guide
- [src/rag/README.md](src/rag/README.md) - RAG system overview
- [src/rag/agent-rag-mixin.js](src/rag/agent-rag-mixin.js) - Mixin code

## Questions?

Check the logs:
```bash
# Enable debug mode
RAG_DEBUG=true node your-script.js

# Check index
cat .rag-index/manifest.json | jq '.'
```
