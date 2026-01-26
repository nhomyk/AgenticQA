# Weaviate Setup for AgenticQA

## Local Development Setup

### Prerequisites

- Docker and Docker Compose installed
- Python 3.9+
- weaviate-client Python package

### Installation

1. **Install Python dependencies:**

```bash
pip install weaviate-client
```

2. **Start Weaviate locally:**

```bash
docker-compose -f docker-compose.weaviate.yml up -d
```

3. **Verify Weaviate is running:**

```bash
curl http://localhost:8080/v1/.well-known/ready
```

You should see: `{"status":"ok"}`

4. **View Weaviate Dashboard:**

Open http://localhost:8080 in your browser

### Usage in AgenticQA

```python
from agenticqa.rag import VectorStore, MultiAgentRAG

# Default: connects to local Weaviate at localhost:8080
vector_store = VectorStore()

# Or with custom host/port
vector_store = VectorStore(host="localhost", port=8080)

# Use with MultiAgentRAG
rag = MultiAgentRAG(vector_store)
```

### Stop Weaviate

```bash
docker-compose -f docker-compose.weaviate.yml down
```

### Cleanup (remove data)

```bash
docker-compose -f docker-compose.weaviate.yml down -v
```

---

## Production Deployment

### Weaviate Cloud

For production, use Weaviate Cloud instead of local Docker:

1. **Sign up at https://console.weaviate.cloud**

2. **Create a cluster**

3. **Get your API key**

4. **Connect from AgenticQA:**

```python
from agenticqa.rag import VectorStore

vector_store = VectorStore(
    host="https://your-cluster.weaviate.network",
    api_key="your-api-key"
)
```

### Kubernetes

For enterprise deployments, Weaviate provides Kubernetes helm charts:

```bash
helm repo add weaviate https://weaviate.github.io/helm
helm install weaviate weaviate/weaviate \
  --namespace agenticqa \
  --values values.yaml
```

---

## Environment Variables

```bash
# For Weaviate Cloud authentication
export WEAVIATE_API_KEY="your-api-key"

# For OpenAI embeddings (optional)
export OPENAI_API_KEY="your-openai-key"
```

---

## Troubleshooting

### Connection Refused

**Problem:** `Failed to connect to Weaviate at localhost:8080`

**Solution:**
1. Check Docker is running: `docker ps`
2. Check container is healthy: `docker-compose -f docker-compose.weaviate.yml ps`
3. Check logs: `docker-compose -f docker-compose.weaviate.yml logs weaviate`
4. Restart: `docker-compose -f docker-compose.weaviate.yml restart`

### Collection Not Found

**Problem:** `Collection not found in Weaviate`

**Solution:**
- Weaviate auto-creates collections on first use
- If collection exists but is empty, that's OK (will populate on first insert)

### Slow Queries

**Problem:** Searches are slow

**Solution:**
1. Ensure Weaviate has enough resources (CPU, memory)
2. Check query complexity
3. Consider adding indexes (Weaviate does this automatically)

---

## Performance Tuning

### For Development (laptop)

```yaml
# In docker-compose.weaviate.yml
resources:
  limits:
    cpus: '2'
    memory: 2G
```

### For Production (server)

```yaml
resources:
  limits:
    cpus: '8'
    memory: 16G
```

---

## Monitoring

### Health Check

```bash
curl http://localhost:8080/v1/meta
```

### Metrics

Weaviate exposes Prometheus metrics at:
```
http://localhost:8080/metrics
```

---

## Migration from In-Memory Store

If you were using the old in-memory `SimpleVectorStore`:

**Before:**
```python
from agenticqa.rag import VectorStore
store = VectorStore(max_documents=10000)  # In-memory
```

**After (no changes needed!):**
```python
from agenticqa.rag import VectorStore
store = VectorStore()  # Now uses Weaviate
```

The API is identical - just swap the implementation and you're done!

---

## Further Reading

- [Weaviate Documentation](https://weaviate.io/developers/weaviate)
- [Python Client Documentation](https://weaviate-python-client.readthedocs.io/)
- [Vector Search Best Practices](https://weaviate.io/blog)
