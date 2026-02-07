# AgenticQA

**Autonomous multi-agent CI/CD platform where 7 specialized AI agents collaborate, learn from every deployment, and self-heal — without LLMs.**

[![CI Pipeline](https://github.com/nhomyk/AgenticQA/actions/workflows/ci.yml/badge.svg)](https://github.com/nhomyk/AgenticQA/actions/workflows/ci.yml)
[![Pipeline Validation](https://github.com/nhomyk/AgenticQA/actions/workflows/pipeline-validation.yml/badge.svg)](https://github.com/nhomyk/AgenticQA/actions/workflows/pipeline-validation.yml)
[![Python 3.8+](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

---

## How It Works

Seven specialized agents run inside your CI/CD pipeline. Each agent stores execution patterns as vector embeddings in Weaviate, retrieves similar historical cases before making decisions, and improves with every deployment — all through deterministic pattern matching, not LLM API calls.

Agents don't work in isolation. They delegate to each other through a governed collaboration system with depth limits, circular-dependency detection, and budget controls.

```
                         ┌──────────────┐
                         │  CI Pipeline │
                         └──────┬───────┘
                                │
              ┌─────────────────┼─────────────────┐
              ▼                 ▼                 ▼
         ┌─────────┐     ┌──────────┐      ┌──────────┐
         │   SRE   │     │   SDET   │      │ Fullstack│
         │  Agent  │◄────│  Agent   │      │  Agent   │
         └─────────┘     └──────────┘      └────┬─────┘
              │                                  │
              │          ┌──────────┐            │
              │          │    QA    │            ▼
              │          │  Agent   │     ┌────────────┐
              │          └──────────┘     │ Compliance │
              │                           │   Agent    │
              │          ┌──────────┐     └─────┬──────┘
              │          │   Perf   │           │
              │          │  Agent   │           ▼
              │          └──────────┘     ┌──────────┐
              │                           │  DevOps  │
              │                           │  Agent   │
              │                           └──────────┘
              ▼
     ┌─────────────────────────────────────────────┐
     │          Hybrid RAG Layer                    │
     │  Weaviate (vectors) + Neo4j (graphs)        │
     │  + Relational DB (metrics)                  │
     └─────────────────────────────────────────────┘
```

**Delegation paths:** SDET delegates test generation to SRE. Fullstack validates with Compliance before generating code. Compliance consults DevOps on deployment security.

---

## Key Capabilities

| Capability | What Happens | Result |
|---|---|---|
| **Self-Healing** | SRE agent detects linting errors, retrieves proven fixes from Weaviate, applies them, and commits | 90% of linting errors fixed autonomously |
| **Coverage Intelligence** | SDET agent identifies gaps, prioritizes by business criticality, delegates test generation to SRE | 100% of critical gaps detected |
| **Code Generation** | Fullstack agent generates API endpoints and UI components from feature requests after compliance validation | 80% of simple features automated |
| **Pattern Learning** | Every pipeline run stores success/failure patterns as embeddings — agents get smarter without retraining | 96% decision confidence after 50 deployments |
| **Self-Validation** | Separate nightly pipeline injects intentional errors to verify agents detect and fix them | 99.5% pipeline uptime |
| **Quality Evaluation** | Ragas measures faithfulness, relevancy, precision, and recall across all agent decisions | Continuous quality tracking |

---

## Why Pattern Learning Over LLMs

Agents use Case-Based Reasoning — deterministic pattern matching against historical embeddings instead of LLM inference.

| | LLM-Based | AgenticQA |
|---|---|---|
| **Cost per 1K fixes** | $30–100 | **$1** |
| **Latency** | 2–5s | **10–50ms** |
| **Deterministic** | No | **Yes** |
| **Works offline** | No | **Yes** |
| **Explainable** | No | **Yes** |

---

## Tech Stack

| Layer | Technology |
|---|---|
| **Vector DB** | Weaviate |
| **Graph DB** | Neo4j |
| **Relational DB** | SQLite / PostgreSQL |
| **Embeddings** | Sentence-Transformers |
| **Quality Metrics** | Ragas |
| **API** | FastAPI |
| **Dashboard** | Streamlit + Plotly |
| **CI/CD** | GitHub Actions |
| **Testing** | Pytest, Playwright, Pa11y |
| **Language** | Python 3.8+ |

---

## Quick Start

```bash
# Install
git clone https://github.com/nhomyk/AgenticQA.git
cd AgenticQA
pip install -e .

# Start infrastructure
docker compose -f docker-compose.weaviate.yml up -d

# Run tests
pytest tests/ -v

# Launch dashboard
streamlit run dashboard/app.py
```

---

## Project Structure

```
src/agenticqa/
├── collaboration/    # Agent delegation, registry, guardrails
├── graph/            # Neo4j graph store, hybrid RAG
├── rag/              # Weaviate vector store, embeddings, retrieval
├── data_store/       # Artifact store, snapshots, security
└── cli.py            # CLI interface

dashboard/            # Streamlit analytics dashboard
tests/                # Unit, integration, RAG, delegation, UI tests
.github/workflows/    # CI pipeline + nightly self-validation
examples/             # SDK usage (Python, TypeScript, Neo4j)
```

---

## Documentation

- [Agent Collaboration](docs/AGENT_COLLABORATION.md) — delegation system and guardrails
- [Hybrid RAG Architecture](HYBRID_RAG_ARCHITECTURE.md) — vector + graph + relational design
- [Agent Learning System](AGENT_LEARNING_SYSTEM.md) — how pattern learning works
- [Pipeline Validation](PIPELINE_VALIDATION_WORKFLOW.md) — self-testing workflow
- [Quick Reference](QUICK_REFERENCE.md) — commands cheat sheet

---

## License

MIT
