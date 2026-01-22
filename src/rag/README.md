/**
 * RAG README
 * Integration guide and quick start for RAG system
 */

# RAG (Retrieval-Augmented Generation) System

AgenticQA's RAG system enables agents to access semantic context from your codebase for enhanced decision-making.

## Features

✅ **Semantic Search** - Find relevant code/docs by meaning, not keywords  
✅ **Flexible Storage** - Pinecone (cloud) or local Chroma (dev)  
✅ **Zero External Deps** - Node.js built-ins only (crypto, fs, https)  
✅ **Cost Tracking** - Monitor API usage and estimate costs  
✅ **Test Suite** - Verify index integrity and retrieval quality  
✅ **Agent Integration** - Simple mixin for existing agents  

## Quick Start

### 1. Index Your Codebase

```bash
# Default (mock embeddings, local storage)
npm run rag:index

# With OpenAI embeddings
EMBEDDING_PROVIDER=openai OPENAI_API_KEY=sk-... npm run rag:index

# With Pinecone
RAG_PROVIDER=pinecone PINECONE_API_KEY=... PINECONE_INDEX=... npm run rag:index
```

### 2. Verify Index

```bash
npm run rag:verify
```

### 3. Enable in Agents

```javascript
const AgentWithRAG = require('./src/rag/agent-rag-mixin');

const agent = new AgentWithRAG(baseAgent);
await agent.initialize();

// Now all decisions include RAG context
const decision = await agent.decide('How should I fix this error?');
```

## Architecture

```
Documents
    ↓
[DocumentLoader] - Load & chunk codebase
    ↓
Chunks (500 token windows)
    ↓
[EmbeddingsProvider] - Generate embeddings
    ├─ OpenAI (production)
    ├─ Local models (dev)
    └─ Mock (testing)
    ↓
Embeddings (1536 dims)
    ↓
[RAGVectorStore] - Store & retrieve
    ├─ Pinecone (cloud)
    └─ Local Chroma (dev)
    ↓
[AgentWithRAG] - Use in agents
    ↓
Enhanced Decisions
```

## Configuration

### Environment Variables

```bash
# Embedding provider
EMBEDDING_PROVIDER=mock|openai|local
OPENAI_API_KEY=sk-...
EMBEDDING_MODEL=text-embedding-3-small

# Vector store
RAG_PROVIDER=pinecone|chroma
PINECONE_API_KEY=...
PINECONE_INDEX=agenticqa

# Enable/disable
RAG_ENABLED=true|false
```

### Programmatic Config

```javascript
const vectorStore = new RAGVectorStore({
  provider: 'pinecone',
  topK: 5,
  scoreThreshold: 0.5,
  localPath: '.rag-index/chroma'
});

const loader = new DocumentLoader({
  extensions: ['.js', '.md'],
  chunkSize: 500,
  overlapSize: 50,
  maxFileSize: 1000000
});

const embedder = new EmbeddingsProvider({
  provider: 'openai',
  dimension: 1536,
  batchSize: 10
});
```

## Usage in Agents

### Basic Usage

```javascript
const agent = new AgentWithRAG(myAgent);
await agent.initialize();

const decision = await agent.decide('Error in deploy phase');
// {
//   decision: 'Restart SRE Agent [Based on analysis...]',
//   ragContext: [
//     { source: 'src/sre-agent.js', relevance: '87%', preview: '...' },
//     { source: 'docs/recovery.md', relevance: '81%', preview: '...' }
//   ],
//   latency: 245
// }
```

### Advanced: Custom Retrieval

```javascript
const agent = new AgentWithRAG(myAgent);

// Retrieve specific context
const embedding = await agent.embedder.embed('database migration');
const results = await agent.vectorStore.retrieveContext(
  embedding,
  topK: 10,
  scoreThreshold: 0.3
);

results.forEach(r => {
  console.log(`${r.source} (${r.score * 100}%): ${r.content}`);
});
```

### Monitoring

```javascript
const agent = new AgentWithRAG(myAgent);

// Get statistics
const stats = agent.getRAGStats();
console.log(`Successful retrievals: ${stats.successfulRetrievals}`);
console.log(`Average latency: ${stats.averageLatency}`);
console.log(`Embedding cost: $${stats.embedderStats.costEstimate}`);
```

## Integration with Data Validation

RAG context is validated before use:

```javascript
// In data-validation-pipeline.js
const context = await agent.vectorStore.retrieveContext(embedding);

await pipeline.validatePreDeployment(context, {
  schema: {
    type: 'array',
    items: {
      type: 'object',
      properties: {
        content: { type: 'string', minLength: 50 },
        source: { type: 'string' },
        score: { type: 'number', minimum: 0, maximum: 1 }
      },
      required: ['content', 'source', 'score']
    }
  }
});
```

## Performance

| Operation | Duration | Notes |
|-----------|----------|-------|
| Index 100 files | 15-30s | Includes embedding generation |
| Query embedding | 200-500ms | Depends on provider |
| Vector search | 50-200ms | Local: faster, Pinecone: slower |
| **Total per query** | **250-700ms** | Minimal pipeline overhead |

## Cost Estimation

| Provider | Cost | Notes |
|----------|------|-------|
| Mock | $0 | Development/testing |
| Local | $0 | Self-hosted, compute only |
| OpenAI | ~$0.02/1M tokens | Per embedding request |
| Pinecone | $0.04/1M requests | Plus storage (~$1/month) |

## Troubleshooting

### Issue: "Index manifest not found"

```bash
# Run indexing first
npm run rag:index
```

### Issue: "RAG initialization failed"

Check environment variables:

```bash
echo $EMBEDDING_PROVIDER
echo $RAG_PROVIDER
echo $RAG_ENABLED
```

### Issue: Slow retrievals

1. Check latency: `agent.getRAGStats()`
2. Reduce topK: `retrieveContext(embedding, topK: 3)`
3. Increase threshold: `scoreThreshold: 0.7`
4. Use Pinecone over local for large indexes

### Issue: High costs

1. Use mock embeddings for development
2. Batch embeddings together
3. Monitor `embedderStats.costEstimate`
4. Cache embeddings when possible

## Next Steps

1. **Production Deployment**
   - Set up Pinecone account
   - Configure OpenAI API
   - Run indexing in CI/CD
   - Monitor costs

2. **Integration**
   - Add RAG to all agents
   - Monitor latency impact
   - Validate context quality
   - Measure decision improvement

3. **Optimization**
   - Fine-tune chunk size
   - Adjust score threshold
   - Cache popular queries
   - Implement reranking

## Files

- `vector-store.js` - Vector DB abstraction (Pinecone/Chroma)
- `document-loader.js` - Document loading & chunking
- `embeddings.js` - Embedding generation (OpenAI/Local/Mock)
- `agent-rag-mixin.js` - Agent enhancement mixin
- `indexing.js` - One-time index creation script
- `verify-index.js` - Index validation & testing

## Contributing

To add a new embedding provider:

1. Add to `EmbeddingsProvider.embed()` switch statement
2. Implement new method (e.g., `embedHuggingFace()`)
3. Test with `verify-index.js`
4. Update docs

To add a new vector store:

1. Extend `RAGVectorStore` base class
2. Implement `initialize()`, `storeEmbeddings()`, `retrieveContext()`
3. Add to provider selection
4. Test with `indexing.js`
