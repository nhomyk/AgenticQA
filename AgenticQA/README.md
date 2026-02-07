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

## Analytics Dashboard

A 12-page Streamlit dashboard backed by Neo4j and Plotly for full observability into the agent system.

```
streamlit run dashboard/app.py
```

### Dashboard Pages

| Page | What It Shows |
|---|---|
| **Overview** | System-wide metrics — total agents, delegations, top performers |
| **Network** | Interactive collaboration graph — nodes are agents, edges are delegations color-coded by success rate |
| **Performance** | Duration distributions, latency trends, agent-by-agent response times |
| **Chains** | Full delegation chain traces — see exactly how SDET → SRE → result flowed |
| **GraphRAG** | Interactive Hybrid RAG architecture diagram with live recommendation engine |
| **Live Activity** | Real-time agent execution feed with status indicators |
| **Pipeline Flow** | End-to-end data flow from commit to deployment gate |
| **Ontology** | Design-vs-reality analysis — intended delegation paths vs. actual usage |
| **Agent Testing** | Per-agent test results, pass rates, coverage deltas, health scores |
| **Pipeline Security** | Defense-in-depth diagram — 6 security layers from CI gate to immutability |
| **API Plug** | Unified API connectivity view — service status, route inventory, test coverage |
| **Stack Anatomy** | Full-stack architecture map with LOC breakdown across 7 layers and 10 frameworks |

### Hybrid RAG Query Flow

The dashboard's recommendation engine combines two retrieval strategies to suggest which agent should handle a task:

```
            ┌──────────────────┐
            │   Agent Query    │
            │   (task type)    │
            └────────┬─────────┘
                     │
          ┌──────────┴──────────┐
          ▼                     ▼
   ┌─────────────┐      ┌─────────────┐
   │  Weaviate   │      │   Neo4j     │
   │  (vectors)  │      │  (graphs)   │
   │             │      │             │
   │ "What does  │      │ "Who has    │
   │  this task  │      │  succeeded  │
   │  look like?"│      │  at this?"  │
   └──────┬──────┘      └──────┬──────┘
          │   cosine sim       │  graph traversal
          └──────────┬─────────┘
                     ▼
            ┌──────────────────┐
            │ Weighted Ranking │
            │ (best of both)   │
            └────────┬─────────┘
                     ▼
            ┌──────────────────┐
            │  Recommended     │
            │  Agent + Score   │
            └──────────────────┘
```

### Security Architecture

Every agent execution passes through 6 validation layers before reaching the artifact store:

```
  ┌──────────────────────────────────────────────────────────┐
  │  1. CI/CD Pipeline Gate                                  │
  │     16 jobs · 3 Python versions · final deployment gate  │
  ├──────────────────────────────────────────────────────────┤
  │  2. Delegation Guardrails                                │
  │     max depth=3 · max total=5 · timeout=30s · whitelist  │
  ├──────────────────────────────────────────────────────────┤
  │  3. Task-Agent Ontology                                  │
  │     18 task types · confidence scoring · 70% min success │
  ├──────────────────────────────────────────────────────────┤
  │  4. Schema & PII Validation                              │
  │     4 PII patterns · schema compliance · encryption      │
  ├──────────────────────────────────────────────────────────┤
  │  5. Data Quality Testing                                 │
  │     10 tests · integrity checks · temporal consistency   │
  ├──────────────────────────────────────────────────────────┤
  │  6. Immutability & Integrity                             │
  │     SHA-256 hashing · duplicate detection · verification │
  └──────────────────────────────────────────────────────────┘
```

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
| **Testing** | Pytest (250 tests), Playwright, Pa11y |
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
AgenticQA/
├── src/agenticqa/
│   ├── collaboration/    # Agent delegation, registry, guardrails
│   ├── graph/            # Neo4j graph store, hybrid RAG
│   ├── rag/              # Weaviate vector store, embeddings, retrieval
│   ├── data_store/       # Artifact store, snapshots, security
│   └── cli.py            # CLI interface
├── dashboard/            # 12-page Streamlit analytics dashboard
├── tests/                # 250 tests — unit, integration, RAG, delegation, UI
├── .github/workflows/    # CI pipeline (16 jobs) + nightly self-validation
└── examples/             # SDK usage (Python, TypeScript, Neo4j)
```

---

## Documentation

- [Agent Collaboration](AgenticQA/docs/AGENT_COLLABORATION.md) — delegation system and guardrails
- [Hybrid RAG Architecture](AgenticQA/HYBRID_RAG_ARCHITECTURE.md) — vector + graph + relational design
- [Agent Learning System](AgenticQA/AGENT_LEARNING_SYSTEM.md) — how pattern learning works
- [Pipeline Validation](AgenticQA/PIPELINE_VALIDATION_WORKFLOW.md) — self-testing workflow
- [Quick Reference](AgenticQA/QUICK_REFERENCE.md) — commands cheat sheet

---

## License

MIT
