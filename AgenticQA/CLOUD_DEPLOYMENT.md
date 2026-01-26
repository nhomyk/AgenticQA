# AgenticQA Cloud Deployment Guide

## Overview

AgenticQA is designed for **production-scale cloud deployments** using Weaviate Cloud as the vector database backend. This eliminates the need to run local Docker containers in your pipeline and provides enterprise-grade persistence, scalability, and reliability.

## Architecture

```
┌─────────────────────────────────────────────────────┐
│  Your Pipeline (CI/CD, Lambda, Container, etc)     │
│  ├─ Tests                                           │
│  ├─ Agents                                          │
│  └─ Quality Gates                                   │
└────────────────────┬────────────────────────────────┘
                     │
                     │ AGENTICQA_RAG_MODE=cloud
                     │ + API credentials
                     ▼
┌─────────────────────────────────────────────────────┐
│  AgenticQA Python SDK                               │
│  └─ Automatic Weaviate Cloud Connection            │
└────────────────────┬────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────┐
│  Weaviate Cloud (Managed, Persistent, Scalable)    │
│  ├─ Collections: test_results, errors, etc         │
│  ├─ Replication: Multi-region backup               │
│  └─ Indexing: Automatic with backups               │
└─────────────────────────────────────────────────────┘
```

## Quick Start

### Step 1: Create Weaviate Cloud Cluster

1. Go to [Weaviate Cloud Console](https://console.weaviate.cloud)
2. Create a new cluster:
   - **Cluster Name**: `agenticqa-prod` (or your preferred name)
   - **Tier**: Free tier is fine for testing, upgrade as needed
   - **Region**: Choose closest to your pipeline infrastructure
3. Wait for cluster to be ready (usually 2-3 minutes)
4. Copy your **Cluster URL** and **API Key** from the console

### Step 2: Set Environment Variables

```bash
# Copy the example file
cp .env.cloud.example .env.cloud

# Edit with your actual values
export AGENTICQA_RAG_MODE=cloud
export WEAVIATE_HOST=your-cluster-name.weaviate.network
export WEAVIATE_API_KEY=your-api-key-from-console
```

### Step 3: Verify Connection

```python
from agenticqa.rag import RAGConfig, create_rag_system

# Check configuration
config = RAGConfig.get_weaviate_config()
print(RAGConfig.print_config_summary())

# Create RAG system (will verify cloud connection)
rag = create_rag_system()
print(f"Connected! Collection: {config.collection_name}")
```

## Integration in Pipelines

### GitHub Actions

```yaml
name: AgenticQA Tests

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    env:
      AGENTICQA_RAG_MODE: cloud
      WEAVIATE_HOST: ${{ secrets.WEAVIATE_HOST }}
      WEAVIATE_API_KEY: ${{ secrets.WEAVIATE_API_KEY }}
    
    steps:
      - uses: actions/checkout@v3
      
      - uses: actions/setup-python@v4
        with:
          python-version: '3.11'
      
      - name: Install dependencies
        run: |
          pip install -e .
          pip install pytest
      
      - name: Run tests with cloud RAG
        run: pytest tests/test_rag_retrieval.py -v
      
      - name: Run quality agents
        run: python -m agenticqa.cli --mode cloud
```

### GitLab CI

```yaml
stages:
  - test
  - deploy

test_with_rag:
  stage: test
  image: python:3.11
  variables:
    AGENTICQA_RAG_MODE: cloud
    WEAVIATE_HOST: $WEAVIATE_HOST
    WEAVIATE_API_KEY: $WEAVIATE_API_KEY
  script:
    - pip install -e .
    - pytest tests/test_rag_retrieval.py -v
  only:
    - merge_requests
    - main
```

### AWS Lambda

```python
import os
import json
from agenticqa.rag import create_rag_system
from agenticqa.agents import QualityAgent

# Environment variables set at Lambda layer
def lambda_handler(event, context):
    # Credentials from Lambda environment (no need to store locally)
    os.environ['AGENTICQA_RAG_MODE'] = 'cloud'
    # WEAVIATE_HOST and WEAVIATE_API_KEY already set
    
    # Create RAG system (connects to Weaviate Cloud)
    rag = create_rag_system()
    
    # Run quality checks
    agent = QualityAgent(rag=rag)
    results = agent.evaluate_code(event['code'])
    
    return {
        'statusCode': 200,
        'body': json.dumps(results)
    }
```

### Docker Container

```dockerfile
FROM python:3.11-slim

WORKDIR /app

# Install AgenticQA
COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .

# Cloud configuration via environment variables
ENV AGENTICQA_RAG_MODE=cloud

CMD ["python", "-m", "agenticqa.cli", "--mode", "cloud"]
```

Run with:
```bash
docker run \
  -e WEAVIATE_HOST=cluster-name.weaviate.network \
  -e WEAVIATE_API_KEY=your-api-key \
  agenticqa:latest
```

## Environment Variables

| Variable | Required | Description | Example |
|----------|----------|-------------|---------|
| `AGENTICQA_RAG_MODE` | No | Deployment mode (local/cloud/custom) | `cloud` |
| `WEAVIATE_HOST` | Yes (cloud/custom) | Weaviate endpoint | `cluster.weaviate.network` |
| `WEAVIATE_API_KEY` | Yes (cloud) | Authentication key | `abc123xyz...` |
| `WEAVIATE_COLLECTION` | No | Collection name | `AgenticQADocuments` |
| `OPENAI_API_KEY` | No | For semantic embeddings | `sk-...` |

## Usage in Code

### Factory Pattern (Recommended)

```python
from agenticqa.rag import create_rag_system

# Automatically reads environment variables
rag = create_rag_system()

# Use in your pipeline
for test_result in test_results:
    rag.learn_from_test(test_result)

recommendations = rag.get_recommendations()
```

### Manual Configuration

```python
from agenticqa.rag import RAGConfig, WeaviateVectorStore, MultiAgentRAG

# Get configuration from environment
config = RAGConfig.get_weaviate_config()

# Create vector store
store = WeaviateVectorStore(**config.to_dict())

# Create RAG system
rag = MultiAgentRAG(store)
```

### Validation

```python
from agenticqa.rag import RAGConfig

# Validate cloud configuration is set correctly
try:
    RAGConfig.validate_cloud_config()
    config = RAGConfig.get_weaviate_config()
    print(RAGConfig.print_config_summary())
except ValueError as e:
    print(f"Configuration error: {e}")
    exit(1)
```

## Production Best Practices

### 1. Secret Management

**Never commit API keys!**

Store credentials in:
- **GitHub Actions**: Use [Secrets](https://docs.github.com/en/actions/security-guides/encrypted-secrets)
- **GitLab CI**: Use [CI/CD Variables](https://docs.gitlab.com/ee/ci/variables/)
- **AWS**: Use [Secrets Manager](https://aws.amazon.com/secrets-manager/)
- **Azure**: Use [Key Vault](https://azure.microsoft.com/en-us/services/key-vault/)

Example:
```bash
# In GitHub Actions
- name: Run tests
  env:
    WEAVIATE_API_KEY: ${{ secrets.WEAVIATE_API_KEY }}
  run: pytest tests/
```

### 2. Collection Management

Use different collections for different environments:

```python
import os

env = os.getenv('ENVIRONMENT', 'dev')
os.environ['WEAVIATE_COLLECTION'] = f'agenticqa_{env}'

rag = create_rag_system()
```

Collections:
- `agenticqa_dev`: Development testing
- `agenticqa_staging`: Pre-production validation
- `agenticqa_prod`: Production data

### 3. Monitoring

```python
from agenticqa.rag import create_rag_system

rag = create_rag_system()

# Monitor storage usage
stats = rag.vector_store.stats()
print(f"Documents: {stats['doc_count']}")
print(f"Collections: {stats['name']}")

# Log for monitoring
import logging
logger = logging.getLogger(__name__)
logger.info(f"RAG system initialized with {stats['doc_count']} documents")
```

### 4. Error Handling

```python
from agenticqa.rag import create_rag_system, RAGConfig

try:
    RAGConfig.validate_cloud_config()
    rag = create_rag_system()
except ValueError as e:
    logger.error(f"Cloud configuration invalid: {e}")
    # Fall back to local mode or raise
    raise
except Exception as e:
    logger.error(f"Failed to connect to Weaviate Cloud: {e}")
    raise
```

## Troubleshooting

### Connection Issues

```python
import urllib.request

# Test connectivity to Weaviate Cloud
host = os.getenv('WEAVIATE_HOST')
try:
    response = urllib.request.urlopen(f'https://{host}/v1/meta')
    print("✓ Connected to Weaviate Cloud")
except Exception as e:
    print(f"✗ Connection failed: {e}")
    print(f"  Check WEAVIATE_HOST: {host}")
```

### Invalid API Key

```
Error: Unauthorized (401)
Solution:
  1. Verify API key is correct in Weaviate Cloud console
  2. Ensure key hasn't been revoked
  3. Check if key belongs to correct cluster
```

### Missing Environment Variables

```python
from agenticqa.rag import RAGConfig

try:
    RAGConfig.validate_cloud_config()
except ValueError as e:
    print(f"Missing: {e}")
    # Error message tells you exactly what's missing
```

## Cost Optimization

- **Free Tier**: Up to 100K vectors, limited bandwidth
- **Standard Tier**: Pay-as-you-go, good for production
- **Enterprise**: Custom pricing, SLA, support

### Estimate Usage

1 million documents stored:
- ~5GB storage (5 bytes per vector dimension)
- ~$50-100/month (Standard tier)

See [Weaviate Pricing](https://weaviate.io/pricing)

## Migration from Local to Cloud

### Before (Local Docker)

```python
from agenticqa.rag import VectorStore

store = VectorStore(host="localhost", port=8080)
rag = MultiAgentRAG(store)
```

### After (Cloud)

```python
from agenticqa.rag import create_rag_system

# Just set environment variables
export AGENTICQA_RAG_MODE=cloud
export WEAVIATE_HOST=cluster.weaviate.network
export WEAVIATE_API_KEY=your-key

rag = create_rag_system()
```

**No code changes needed!** Environment-based configuration handles it.

## Support

For issues:
1. Check [Weaviate Cloud Documentation](https://weaviate.io/developers/weaviate/quickstart)
2. Review [WEAVIATE_SETUP.md](WEAVIATE_SETUP.md)
3. See troubleshooting section above
4. Check logs with: `RAGConfig.print_config_summary()`
