# RAG Integration Guide for Agents

Complete guide to integrating Retrieval-Augmented Generation (RAG) into AgenticQA agents.

## Overview

The RAG system enhances agent decision-making by providing access to semantically relevant codebase context. Instead of making decisions based on limited information, agents can now retrieve specific code examples, patterns, and documentation.

## Quick Integration (5 minutes)

### Step 1: Enable RAG Indexing

RAG indexing runs automatically in your CI/CD pipeline (Phase 0.5):

```bash
# In GitHub Actions
✅ Automatically indexes codebase after linting
✅ Generates .rag-index/ with semantic embeddings
✅ Stores index as pipeline artifact
```

### Step 2: Configure Environment

Add to your `.env` or GitHub Secrets:

```bash
# Enable RAG globally
RAG_ENABLED=true

# Choose embedding provider (default: mock)
EMBEDDING_PROVIDER=mock        # mock, openai, local
OPENAI_API_KEY=sk-...         # (optional) for OpenAI

# Choose vector store (default: chroma for local)
RAG_PROVIDER=chroma            # chroma, pinecone
PINECONE_API_KEY=...          # (optional) for Pinecone
PINECONE_INDEX=agenticqa       # Index name
```

### Step 3: Use RAG in Your Agent

```javascript
const AgentWithRAG = require('./src/rag/agent-rag-mixin');
const baseAgent = require('./your-agent');

// Wrap your agent
const agent = new AgentWithRAG(baseAgent);
await agent.initialize();

// All decisions now include RAG context
const decision = await agent.decide('What test should I write?');
// {
//   decision: 'Write unit test for getUserById...',
//   ragContext: [
//     { source: 'lib/user-service.js', score: 0.92, preview: '...' },
//     { source: 'test/user-service.test.js', score: 0.87, preview: '...' }
//   ],
//   latency: 245
// }
```

## Architecture & Design

### Three-Layer Design

```
┌─────────────────────────────┐
│    Agent Decision Layer     │  ← Your existing agents
│  (compliance, fullstack...)  │
└────────────┬────────────────┘
             │
┌────────────▼────────────────┐
│   RAG Context Injection     │  ← AgentWithRAG mixin
│  (augment with retrieval)    │
└────────────┬────────────────┘
             │
┌────────────▼────────────────┐
│  Semantic Context Retrieval │  ← Vector store + embedding
│  (relevant code snippets)    │
└────────────┬────────────────┘
             │
┌────────────▼────────────────┐
│   Codebase Embeddings       │  ← Generated from src/rag/indexing.js
│   (chunked + encoded)        │
└─────────────────────────────┘
```

### Data Flow

```
User Request
    ↓
[Original Agent Decision] → "Fix this error"
    ↓
[RAG Retrieval] → Find relevant code/docs
    ↓
[Context Injection] → Augment with context
    ↓
[Enhanced Decision] → "Fix this error using pattern from lib/utils.js"
    ↓
Better outcomes, faster
```

## Component Descriptions

### 1. Vector Store (`src/rag/vector-store.js`)

Handles storage and retrieval of semantic embeddings.

**Supported Providers:**
- **Pinecone** (cloud-hosted, best for production)
- **Chroma** (local, best for development)

**Key Methods:**

```javascript
const store = new RAGVectorStore({
  provider: 'chroma',           // or 'pinecone'
  topK: 5,                       // Return top-5 results
  scoreThreshold: 0.5,           // Min relevance (0-1)
  localPath: '.rag-index/chroma' // Local storage path
});

// Store embeddings from indexing phase
await store.initialize();
await store.storeEmbeddings(embeddingsArray);

// Retrieve context for a query
const context = await store.retrieveContext(queryEmbedding, {
  topK: 5,
  scoreThreshold: 0.5
});
// Returns: [ { source, content, score }, ... ]
```

### 2. Document Loader (`src/rag/document-loader.js`)

Loads codebase and chunks it for embedding.

**Features:**
- Recursive directory traversal
- Smart semantic chunking (by function/class)
- Configurable overlap and size limits
- Extension filtering
- Respects ignore patterns

**Configuration:**

```javascript
const loader = new DocumentLoader({
  extensions: ['.js', '.ts', '.md'],
  chunkSize: 500,              // Tokens per chunk
  overlapSize: 50,             // Overlap for context
  maxFileSize: 1000000,        // Bytes
  ignorePatterns: ['node_modules', 'dist', '.git'],
  maxDepth: 10                 // Directory depth
});

// Load and chunk documents
const documents = await loader.loadCodebase('./src');
// Returns: [ { file, content, metadata }, ... ]
```

### 3. Embeddings Provider (`src/rag/embeddings.js`)

Generates vector embeddings from text.

**Supported Providers:**

| Provider | Best For | Cost | Dimension |
|----------|----------|------|-----------|
| **mock** | Testing/dev | $0 | 1536 |
| **openai** | Production | ~$0.02/1M tokens | 1536 |
| **local** | Self-hosted | $0 | 1536 |

**Usage:**

```javascript
const embedder = new EmbeddingsProvider({
  provider: 'openai',                // or 'mock', 'local'
  dimension: 1536,                   // Vector dimension
  batchSize: 10                      // Process 10 at a time
});

// Single embedding
const embedding = await embedder.embed('write unit test');

// Batch embeddings
const embeddings = await embedder.embedBatch([
  'write unit test',
  'refactor function',
  'add documentation'
]);

// Get cost estimates
const stats = embedder.getStats();
console.log(`Cost estimate: $${stats.costEstimate}`);
```

### 4. Indexing Pipeline (`src/rag/indexing.js`)

Orchestrates the full indexing process.

**What It Does:**

```
1. Load all relevant files from codebase
2. Split into semantic chunks
3. Generate embeddings for each chunk
4. Store in vector database
5. Generate manifest.json with metadata
6. Report statistics & costs
```

**Running Manually:**

```bash
# Default (mock embeddings, local storage)
node src/rag/indexing.js

# With OpenAI API
EMBEDDING_PROVIDER=openai OPENAI_API_KEY=sk-... node src/rag/indexing.js

# With Pinecone
RAG_PROVIDER=pinecone PINECONE_API_KEY=... node src/rag/indexing.js

# Output
✅ Loaded 42 files
✅ Created 156 chunks
✅ Generated 156 embeddings
✅ Stored in vector database
✅ Index ready at: .rag-index/
Cost estimate: $0.03 USD
```

### 5. Index Verification (`src/rag/verify-index.js`)

Tests index quality and retrieval accuracy.

**What It Tests:**

```
✅ Index manifest exists and is valid
✅ Index directory structure
✅ Retrieval quality (cosine similarity)
✅ Sample queries and scoring
✅ Vector store connectivity
```

**Running Manually:**

```bash
node src/rag/verify-index.js

# Output
Query 1: "How do I write tests?"
  1. test/example.test.js (92%)
  2. docs/testing.md (87%)
  3. lib/utils.js (72%)

Query 2: "Fix authentication error"
  1. auth/middleware.js (94%)
  2. docs/security.md (81%)
  ...
```

### 6. Agent RAG Mixin (`src/rag/agent-rag-mixin.js`)

Wraps existing agents to add RAG capabilities.

**How It Works:**

```javascript
// Wrap any agent
class MyAgent {
  async decide(task) {
    return 'My decision: ' + task;
  }
}

const agent = new MyAgent();
const ragAgent = new AgentWithRAG(agent);

// Now decide() returns augmented decisions
const result = await ragAgent.decide('Fix the deploy bug');
// {
//   decision: 'My decision: Fix the deploy bug',
//   ragContext: [...],  // ← NEW: Relevant context
//   latency: 342        // ← NEW: Retrieval time
// }
```

**Interface:**

```javascript
class AgentWithRAG {
  async initialize() { }           // Load index & config
  async decide(task) { }           // Original + RAG context
  async getContextForQuery(task) { } // Get raw context
  async augmentDecisionWithContext(decision, context) { }
  getRAGStats() { }               // Monitor stats
}
```

**Available Stats:**

```javascript
const stats = agent.getRAGStats();
// {
//   successfulRetrievals: 42,
//   failedRetrievals: 2,
//   averageLatency: 245,           // milliseconds
//   totalTokensEmbedded: 12400,
//   embedderStats: {
//     provider: 'openai',
//     costEstimate: 0.25,
//     tokensProcessed: 12400
//   }
// }
```

## Integration Patterns

### Pattern 1: Compliance Agent

```javascript
const ComplianceAgent = require('./compliance-agent');
const AgentWithRAG = require('./src/rag/agent-rag-mixin');

async function setupComplianceWithRAG() {
  const agent = new AgentWithRAG(ComplianceAgent);
  await agent.initialize();
  
  // Now it can reference compliance patterns from codebase
  const decision = await agent.decide('Check GDPR compliance');
  // Retrieves from: SECURITY.md, compliance-checks.js, etc.
  
  return agent;
}
```

### Pattern 2: SDET Agent

```javascript
const SDETAgent = require('./sdet-agent');
const AgentWithRAG = require('./src/rag/agent-rag-mixin');

const testAgent = new AgentWithRAG(SDETAgent);
await testAgent.initialize();

const result = await testAgent.decide('Write test for dashboard component');
// Retrieves: cypress/e2e/*.cy.js, test patterns, selectors
// Result includes code examples to follow
```

### Pattern 3: SRE Agent

```javascript
const SREAgent = require('./agentic_sre_engineer');
const AgentWithRAG = require('./src/rag/agent-rag-mixin');

const sreAgent = new AgentWithRAG(SREAgent);
await sreAgent.initialize();

const result = await sreAgent.decide('Fix deployment failure');
// Retrieves: deployment scripts, error recovery guides, fixes
// Can reference exact commands and patterns
```

### Pattern 4: Fullstack Agent

```javascript
const FullstackAgent = require('./fullstack-agent');
const AgentWithRAG = require('./src/rag/agent-rag-mixin');

const fullstack = new AgentWithRAG(FullstackAgent);
await fullstack.initialize();

const result = await fullstack.decide('Generate test for new feature');
// Retrieves: test fixtures, patterns, utilities
// Understands existing test structure and conventions
```

## Configuration & Tuning

### Environment Variables

```bash
# Feature Flags
RAG_ENABLED=true|false              # Enable/disable RAG globally
RAG_DEBUG=true|false                # Enable verbose logging

# Vector Store
RAG_PROVIDER=chroma|pinecone        # Default: chroma
PINECONE_API_KEY=...                # For Pinecone
PINECONE_INDEX=agenticqa            # Index name
PINECONE_ENVIRONMENT=us-west1-gcp   # Region

# Embeddings
EMBEDDING_PROVIDER=mock|openai|local # Default: mock
OPENAI_API_KEY=sk-...               # For OpenAI
EMBEDDING_MODEL=text-embedding-3-small # Model choice
EMBEDDING_BATCH_SIZE=10             # Process N at a time

# Retrieval Tuning
RAG_TOP_K=5                         # Return top-5 results
RAG_SCORE_THRESHOLD=0.5             # Min relevance (0-1)
RAG_CHUNK_SIZE=500                  # Tokens per chunk
RAG_OVERLAP=50                      # Chunk overlap

# Performance
RAG_TIMEOUT_MS=5000                 # Retrieval timeout
RAG_CACHE_RESULTS=true              # Cache embeddings
```

### Tuning Guide

**For Development (Mock)**
```bash
RAG_ENABLED=true
EMBEDDING_PROVIDER=mock
RAG_PROVIDER=chroma
RAG_TIMEOUT_MS=2000
```

**For Testing (Fast OpenAI)**
```bash
RAG_ENABLED=true
EMBEDDING_PROVIDER=openai
RAG_PROVIDER=chroma
RAG_TOP_K=3
RAG_SCORE_THRESHOLD=0.6
OPENAI_API_KEY=sk-test...
```

**For Production (Pinecone)**
```bash
RAG_ENABLED=true
EMBEDDING_PROVIDER=openai
RAG_PROVIDER=pinecone
RAG_TOP_K=5
RAG_SCORE_THRESHOLD=0.5
OPENAI_API_KEY=sk-prod...
PINECONE_API_KEY=prod-key
```

## Monitoring & Debugging

### Check Index Status

```bash
# View index manifest
cat .rag-index/manifest.json | jq '.'

# See chunk statistics
node -e "console.log(JSON.parse(require('fs').readFileSync('.rag-index/manifest.json')))"
```

### Monitor Agent Performance

```javascript
const agent = new AgentWithRAG(myAgent);
await agent.initialize();

// Make decisions
for (let i = 0; i < 10; i++) {
  await agent.decide(`Task ${i}`);
}

// Get stats
const stats = agent.getRAGStats();
console.log(`
Average latency: ${stats.averageLatency}ms
Success rate: ${stats.successfulRetrievals / (stats.successfulRetrievals + stats.failedRetrievals) * 100}%
Cost estimate: $${stats.embedderStats.costEstimate}
`);
```

### Debug Retrieval

```javascript
const agent = new AgentWithRAG(myAgent);
await agent.initialize();

// Get raw context for debugging
const context = await agent.getContextForQuery('Write test');

context.forEach(result => {
  console.log(`
Source: ${result.source}
Score: ${(result.score * 100).toFixed(1)}%
Preview: ${result.content.substring(0, 100)}...
  `);
});
```

### Enable Debug Logging

```bash
RAG_DEBUG=true node your-script.js

# Output
[RAG] Initializing vector store (chroma)...
[RAG] Loaded 42 documents from index
[RAG] Query: "write test" (156 chunks available)
[RAG] Retrieved 5 results in 245ms
[RAG] Top result: lib/test-utils.js (0.92 score)
```

## Cost Analysis

### Embedding Costs

| Provider | Cost | Dimension | Notes |
|----------|------|-----------|-------|
| Mock | $0 | 1536 | Development only |
| Local | $0 | 1536 | Self-hosted compute |
| OpenAI text-embedding-3-small | $0.02/1M tokens | 1536 | Default production |
| OpenAI text-embedding-3-large | $0.13/1M tokens | 3072 | Higher quality |

### Cost Estimate Example

**One-time indexing cost (new codebase):**
- 100 files × 500 tokens average = 50,000 tokens
- OpenAI cost: 50,000 ÷ 1,000,000 × $0.02 = **$0.001**

**Per-request cost (agent decisions):**
- 1 query × 50 tokens = 50 tokens
- OpenAI cost: 50 ÷ 1,000,000 × $0.02 = **$0.000001**

**Monthly estimate (1000 agent decisions/day):**
- 1000 queries × 30 days × $0.000001 = **$0.03/month**

### Optimization for Cost

1. **Use mock for development** (free)
2. **Batch queries** in workflows
3. **Cache embeddings** for repeated queries
4. **Reduce topK** for faster retrieval
5. **Increase score threshold** to filter noise

## Troubleshooting

### Issue: "Index not found"

```
ERROR: Index manifest not found at .rag-index/manifest.json
```

**Solution:**
```bash
# Run indexing first
node src/rag/indexing.js

# Or in CI/CD, ensure rag-indexing job passed
```

### Issue: "RAG initialization failed"

```
ERROR: RAG initialization failed (context)
```

**Causes & Solutions:**

| Cause | Solution |
|-------|----------|
| Missing env vars | Set `RAG_ENABLED=true` |
| No index found | Run `node src/rag/indexing.js` |
| Invalid config | Check `RAG_PROVIDER` and `EMBEDDING_PROVIDER` |
| API key invalid | Verify `OPENAI_API_KEY` or `PINECONE_API_KEY` |

### Issue: Slow retrievals (>1000ms)

**Solutions:**

1. **Use Pinecone** (faster than local for large indexes)
   ```bash
   RAG_PROVIDER=pinecone
   ```

2. **Reduce topK**
   ```bash
   RAG_TOP_K=3  # Instead of 5
   ```

3. **Increase score threshold**
   ```bash
   RAG_SCORE_THRESHOLD=0.7  # Filter low-relevance results
   ```

4. **Reduce chunk overlap**
   ```bash
   RAG_OVERLAP=25  # Smaller overlap
   ```

### Issue: High costs

**Solutions:**

1. **Use mock for development**
   ```bash
   EMBEDDING_PROVIDER=mock  # Free during development
   ```

2. **Monitor usage**
   ```javascript
   const stats = agent.getRAGStats();
   console.log(`Tokens: ${stats.totalTokensEmbedded}`);
   ```

3. **Cache embeddings** locally
4. **Batch index operations** - do one per day, not per request

## Best Practices

### 1. Configure Provider Per Environment

```javascript
const provider = process.env.NODE_ENV === 'production' 
  ? 'pinecone'  // Production: cloud-hosted
  : 'chroma';   // Development: local

const embedder = process.env.NODE_ENV === 'production'
  ? 'openai'    // Production: fast, accurate
  : 'mock';     // Development: free
```

### 2. Monitor Retrieval Quality

```javascript
const context = await agent.getContextForQuery(task);

// Check quality
const relevanceScores = context.map(c => c.score);
const avgRelevance = relevanceScores.reduce((a,b) => a+b) / relevanceScores.length;

if (avgRelevance < 0.5) {
  console.warn('⚠️  Low relevance scores:', relevanceScores);
}
```

### 3. Use Error Boundaries

```javascript
try {
  const context = await agent.getContextForQuery(task);
  // Use context
} catch (err) {
  console.warn('RAG retrieval failed, proceeding without context:', err.message);
  // Fall back to original decision
  return await agent.originalDecide(task);
}
```

### 4. Regularly Update Index

In CI/CD, reindex after significant changes:

```yaml
- name: "📚 Reindex RAG (on significant changes)"
  if: contains(github.event.head_commit.modified, 'src/')
  run: node src/rag/indexing.js
```

### 5. Validate Context Quality

```javascript
const context = await agent.getContextForQuery(task);

// Validate before using
for (const item of context) {
  if (item.score < 0.3) {
    console.warn(`Low confidence match from ${item.source}`);
  }
}
```

## Advanced: Custom Integration

### Adding Custom Retrieval Logic

```javascript
const AgentWithRAG = require('./src/rag/agent-rag-mixin');

class CustomAgent extends AgentWithRAG {
  async decide(task) {
    // Get base decision
    const base = await super.decide(task);
    
    // Get additional context
    const tests = await this.vectorStore.retrieveContext(
      this.embedder.embed('test for ' + task),
      { topK: 3 }
    );
    
    // Combine
    base.ragContext = { ...base.ragContext, tests };
    return base;
  }
}
```

### Custom Chunk Strategy

```javascript
const DocumentLoader = require('./src/rag/document-loader');

class CustomLoader extends DocumentLoader {
  chunkDocuments(documents) {
    // Custom chunking by class/function
    const chunks = [];
    documents.forEach(doc => {
      const classes = doc.content.match(/class\s+\w+/g) || [];
      const functions = doc.content.match(/function\s+\w+/g) || [];
      // Custom logic...
    });
    return chunks;
  }
}
```

## Support & Resources

**Files:**
- [src/rag/README.md](src/rag/README.md) - RAG overview
- [src/rag/vector-store.js](src/rag/vector-store.js) - Vector store code
- [src/rag/agent-rag-mixin.js](src/rag/agent-rag-mixin.js) - Mixin implementation

**Providers:**
- [Pinecone Docs](https://docs.pinecone.io)
- [OpenAI Embeddings](https://platform.openai.com/docs/guides/embeddings)
- [Chroma](https://docs.trychroma.com)

**Related:**
- [Data Integrity System](DATA_INTEGRITY_EXPLAINED.md) - Ensure RAG context quality
- [Agent Orchestration](AGENT_ORCHESTRATION.md) - How agents work together
