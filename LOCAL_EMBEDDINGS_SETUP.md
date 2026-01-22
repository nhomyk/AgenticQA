# Local Embeddings Setup

Use free, production-ready embeddings locally with HuggingFace sentence-transformers.

## Installation (One-time)

```bash
# Install HuggingFace transformers library
npm install @xenova/transformers

# That's it! Models download on first use (~22MB)
```

## Usage

### Option 1: Environment Variable (Recommended)

```bash
# Enable local embeddings (free, default)
export EMBEDDING_PROVIDER=local

# Run your code
node src/rag/indexing.js
```

### Option 2: Programmatic

```javascript
const EmbeddingsProvider = require('./src/rag/embeddings');

const embedder = new EmbeddingsProvider({
  provider: 'local'
  // No API key needed!
});

// First use downloads the model (~22MB)
const embedding = await embedder.embed('write a test');
```

## What Happens

**First Run:**
```
📥 Loading HuggingFace model: Xenova/all-MiniLM-L6-v2...
[████████████████████] 100% downloaded
✅ Model loaded successfully (will be cached for future runs)
```

**Subsequent Runs:**
```
✅ Model loaded from cache instantly
```

## Available Models

| Model | Size | Speed | Quality | Best For |
|-------|------|-------|---------|----------|
| `Xenova/all-MiniLM-L6-v2` | 22MB | ⚡⚡⚡ | ⭐⭐⭐⭐ | Default (recommended) |
| `Xenova/all-mpnet-base-v2` | 109MB | ⚡⚡ | ⭐⭐⭐⭐⭐ | Higher quality, slower |
| `Xenova/all-distilroberta-v1` | 67MB | ⚡⚡⚡ | ⭐⭐⭐⭐ | Good balance |

Change model:
```bash
export EMBEDDING_MODEL=Xenova/all-mpnet-base-v2
```

## Performance

```
Indexing 100 files with local embeddings:
✓ Time: 2-3 minutes (CPU-bound)
✓ Cost: $0
✓ No network calls
✓ Privacy: 100% on-device
```

## Switching Providers Later

When ready to scale, switch providers without code changes:

```bash
# Current: Free local
export EMBEDDING_PROVIDER=local

# Later: OpenAI for higher quality
export EMBEDDING_PROVIDER=openai
export OPENAI_API_KEY=sk-...

# Or: Keep using local (never pay)
# No changes needed to your code!
```

## Troubleshooting

### Issue: "MODULE_NOT_FOUND @xenova/transformers"

```bash
npm install @xenova/transformers
```

### Issue: Model download fails

```bash
# Check internet connection
# Models are cached at ~/.cache/huggingface/

# Clear cache and re-download
rm -rf ~/.cache/huggingface/
npm run rag:index  # Re-downloads fresh
```

### Issue: Very slow on first run

**Expected behavior:**
- First run: 2-5 minutes (downloads model, generates embeddings)
- Subsequent runs: Fast (model is cached)

The model file (~22MB) is cached locally and reused.

### Issue: Memory issues on large codebases

**Solution: Process in smaller batches**

```bash
# Default batch size is 10, reduce if needed
export RAG_CHUNK_SIZE=200  # Smaller chunks
export RAG_BATCH_SIZE=5    # Smaller batches
```

## Cost Comparison

| Provider | Cost | Setup |
|----------|------|-------|
| Local | **$0** | `npm install` |
| OpenAI | $0.03/month | API key |
| Mock | $0 | None (testing only) |

## Next: Add More Providers

The system is designed to be extensible. To add a new provider later:

1. Add case in `EmbeddingsProvider.embed()`:
```javascript
case 'newprovider':
  return this.embedNewProvider(text);
```

2. Implement the method:
```javascript
async embedNewProvider(text) {
  // Your implementation
}
```

3. Set environment variable:
```bash
export EMBEDDING_PROVIDER=newprovider
```

That's it! No other code changes needed.

## Ready?

```bash
npm install @xenova/transformers
export EMBEDDING_PROVIDER=local
node src/rag/indexing.js
```

Your codebase is now indexed with **free, production-ready embeddings**. 🚀
