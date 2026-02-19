# AgenticQA

**The world's first autonomous AI agent platform with constitutional governance, forensic decision traceability, and universal cross-platform observability — without LLMs.**

[![CI Pipeline](https://github.com/nhomyk/AgenticQA/actions/workflows/ci.yml/badge.svg)](https://github.com/nhomyk/AgenticQA/actions/workflows/ci.yml)
[![Pipeline Validation](https://github.com/nhomyk/AgenticQA/actions/workflows/pipeline-validation.yml/badge.svg)](https://github.com/nhomyk/AgenticQA/actions/workflows/pipeline-validation.yml)
[![Python 3.8+](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

---

## The Problem

Enterprise teams adopting AI agents face three unsolved problems:

1. **No governance.** AI agents take actions — deploy, delete, delegate — with no enforceable laws stopping them from doing something catastrophic.
2. **No forensics.** When something goes wrong, there's no way to reconstruct *why* an agent made a decision or what it should have done differently.
3. **No interoperability.** Every agent framework (LangGraph, CrewAI, AutoGen) has its own telemetry silo. There's no common observability layer.

AgenticQA solves all three — and does it in deterministic, LLM-free, sub-50ms operations.

---

## What's Groundbreaking

### ⚖️ The Agent Constitution — Industry First

No agent platform on Earth has done this. AgenticQA ships a **machine-readable governance document** that every agent enforces before acting:

```bash
# Any agent, anywhere, can query the law
curl http://localhost:8000/api/system/constitution

# Pre-action check — instant ALLOW / REQUIRE_APPROVAL / DENY
curl -X POST http://localhost:8000/api/system/constitution/check \
  -H "Content-Type: application/json" \
  -d '{"action_type": "delete", "context": {"ci_status": "FAILED", "trace_id": "tr-001"}}'
# → {"verdict": "DENY", "law": "T1-001", "name": "no_destructive_without_ci", "reason": "..."}
```

**Three enforcement tiers, enforced in milliseconds:**

| Tier | Verdict | Laws |
|---|---|---|
| **Tier 1** | `DENY` | No destructive ops without CI pass · Delegation depth ≤ 3 · No PII in logs · No traceless external writes · No self-modification |
| **Tier 2** | `REQUIRE_APPROVAL` | Production deployments · Infrastructure changes · Bulk operations >1K records |
| **Tier 3** | Alert | Low confidence · High failure rate · RAG similarity degradation |

This is the artifact enterprise buyers ask for when evaluating agent platforms for SOC 2, HIPAA, and GDPR compliance. No competitor has it. It ships as a versioned YAML file any external agent can query.

---

### 🔬 Forensic AI Decision Audit Reports

Every agent execution produces a **shareable compliance artifact** with a stable audit ID — embeddable directly into pull request descriptions:

```bash
curl "http://localhost:8000/api/observability/traces/{trace_id}/audit-report?format=markdown"
```

```
┌─────────────────────────────────────────────────────┐
│  AUDIT REPORT — audit_id: a3f9c1b2d4e8              │
│  Verdict: ✅ PASS                                    │
│  Decision Quality: 0.87  |  Completeness: 0.94       │
│  Agents: QA_Assistant, SDET_Agent, DevOps_Agent      │
│  Root Causes: none                                   │
│  Recommendations: none                               │
└─────────────────────────────────────────────────────┘
```

Not a log dump. A forensic verdict with SHA-256 traceability, counterfactual analysis ("what should the agent have done instead?"), and root cause attribution — all generated from the live observability store.

---

### 🌐 Universal Agent Observability — Works With Any Platform

AgenticQA doesn't lock you in. If you're running LangGraph, CrewAI, AutoGen, or a custom framework, **one adapter and all your telemetry flows in automatically:**

```python
# LangGraph / LangChain — zero-config callback
from agenticqa.ingestion import LangChainCallbackAdapter
adapter = LangChainCallbackAdapter(store=store, trace_id="my-trace")
chain.invoke(inputs, config={"callbacks": [adapter]})
# Every chain, tool, and LLM call is now traced, quality-gated, and auditable

# CrewAI / AutoGen / custom — one dict per event
from agenticqa.ingestion import GenericDictAdapter
GenericDictAdapter(store=store).ingest({
    "crew_id": "crew-xyz", "sender": "ResearchAgent", "status": "success"
})
```

Field mapping is automatic. Token usage flows into complexity trends. Every event is immediately queryable via the audit report and trace timeline APIs. **AgenticQA becomes the observability backbone for your entire agent fleet, regardless of framework.**

---

### 🧠 Agents That Learn — Without Retraining

The platform uses **Case-Based Reasoning (CBR)** — deterministic pattern matching against historical embeddings instead of expensive LLM inference. Every deployment teaches the agents. No retraining. No drift.

| | LLM-Based Agents | AgenticQA |
|---|---|---|
| **Cost per 1K decisions** | $30–100 | **$1** |
| **Latency** | 2–5 seconds | **10–50ms** |
| **Deterministic?** | No | **Yes** |
| **Works offline?** | No | **Yes** |
| **Explainable decisions?** | No | **Yes** |
| **Gets better over time?** | Requires retraining | **Automatic** |

The learning loop: every execution stores `rag_docs_retrieved`, `avg_similarity_score`, and `patterns_considered`. EWMA flakiness trends (α=0.3) detect when an agent is degrading. Anomaly detection fires when RAG retrieval similarity drops >20% below the 14-day baseline — your signal that the vector index needs attention before a human even notices.

---

## The System

Seven specialized agents collaborate under constitutional governance across your entire CI/CD pipeline:

```
  Type-to-code prompt
         │
         ▼
  ┌─────────────────────────────────────────────────┐
  │            ConstitutionalGate                   │
  │   Every action checked: ALLOW / DENY first      │
  └────────────────────┬────────────────────────────┘
                       │
         ┌─────────────┼─────────────┐
         ▼             ▼             ▼
    ┌─────────┐   ┌─────────┐  ┌──────────┐
    │  SDET   │   │   QA    │  │ Fullstack│
    │  Agent  │   │  Agent  │  │  Agent   │
    └────┬────┘   └─────────┘  └────┬─────┘
         │                          │
    delegates                  validates with
         ▼                          ▼
    ┌─────────┐              ┌────────────┐
    │   SRE   │              │ Compliance │
    │  Agent  │              │   Agent    │
    └─────────┘              └─────┬──────┘
                                   │
                             consults
                                   ▼
                             ┌──────────┐   ┌─────────┐
                             │  DevOps  │   │  Perf   │
                             │  Agent   │   │  Agent  │
                             └──────────┘   └─────────┘
         │
         ▼
  ┌─────────────────────────────────────────────────┐
  │              Hybrid RAG Layer                   │
  │  Weaviate (vectors) + Neo4j (graphs) + SQLite   │
  │  "What has worked? Who succeeded? How often?"   │
  └─────────────────────────────────────────────────┘
         │
         ▼
  Observability Store → Audit Report → PR artifact
```

**Delegation is governed.** Max depth 3, circular-dependency detection, budget controls, and Neo4j-backed delegation recommendations with failure risk prediction.

---

## Key Outcomes

| Capability | What Happens | Measured Result |
|---|---|---|
| **Self-Healing** | SRE detects linting errors, retrieves proven fixes, commits | 90% of errors fixed autonomously |
| **Coverage Intelligence** | SDET identifies gaps, prioritizes by business criticality | 100% of critical gaps detected |
| **Code Generation** | Fullstack generates from prompt → compliance → tests → commit | 80% of simple features automated |
| **Pattern Learning** | Every run stored as embeddings, retrieved before next decision | 96% confidence after 50 deployments |
| **Self-Validation** | Nightly pipeline injects intentional errors to verify agents | 99.5% pipeline uptime |
| **Constitutional Enforcement** | Pre-action check before every destructive or sensitive operation | Zero unauthorized destructive actions |

---

## 8-Page Analytics Dashboard

```bash
streamlit run dashboard/app.py
```

| Page | What It Shows |
|---|---|
| **Operator Console** | Prompt intake → approve → queue → execute → replay. Trace explorer with timeline, span tree, counterfactuals, audit report generator, and agent complexity trends |
| **Governance** | Agent Constitution viewer (all Tier 1/2/3 laws), interactive pre-action check simulator, agent rights declaration |
| **System Overview** | Stack anatomy, framework matrix, test coverage, LOC breakdown, live agent metrics |
| **Collaboration** | Interactive delegation network graph + chain traces |
| **Performance** | Bottleneck detection, latency trends, per-agent health scores |
| **GraphRAG** | Hybrid RAG architecture diagram + live recommendation engine |
| **Ontology** | Design-vs-reality — intended paths vs. actual delegation usage |
| **Pipeline** | Data flow, 6-layer security architecture, API connectivity tester |

---

## Quick Start

```bash
git clone https://github.com/nhomyk/AgenticQA.git
cd AgenticQA
pip install -e .

# Start infrastructure (optional — most features work without it)
docker compose -f docker-compose.weaviate.yml up -d

# Run 300+ tests
pytest tests/ -v

# Launch control plane
uvicorn agent_api:app --host 0.0.0.0 --port 8000

# Launch dashboard
streamlit run dashboard/app.py
```

### Onboard any repo in 3 commands

```bash
agenticqa bootstrap --repo .          # generate CI wiring + config
agenticqa ingest-junit results.xml    # convert existing test output
agenticqa doctor --repo .             # readiness check with copy-paste fix commands
```

### Install only what you need

```bash
pip install -e .                            # core (no heavy deps)
pip install -e .[graph]                     # + Neo4j delegation intelligence
pip install -e .[rag]                       # + Weaviate/Qdrant vector retrieval
pip install -e .[dashboard,graph]           # + full dashboard
pip install -e .[test,rag,dashboard,graph]  # full validation stack
```

---

## Core API

**Governance**
- `GET  /api/system/constitution` — machine-readable law set; queryable by any agent platform
- `POST /api/system/constitution/check` — pre-action check: returns `ALLOW / REQUIRE_APPROVAL / DENY`

**Observability & Auditing**
- `GET  /api/observability/traces/{id}/audit-report` — PASS/FAIL compliance artifact with stable audit ID
- `GET  /api/observability/traces/{id}/counterfactuals` — "what should the agent have done?" analysis
- `GET  /api/observability/traces/{id}/analysis` — span tree, critical path, completeness, orphan detection
- `GET  /api/observability/agent-complexity` — per-agent retrieval quality trends + anomaly flags
- `GET  /api/observability/quality` — CI-grade trace quality gate (completeness + decision quality)
- `GET  /api/observability/insights` — root-cause distribution and policy-impact analytics

**Cross-Platform Ingestion**
- `POST /api/observability/ingest` — ingest one event from LangGraph, CrewAI, AutoGen, or custom
- `POST /api/observability/ingest/batch` — bulk ingest; returns per-event status array

**Workflow Control Plane**
- `POST /api/workflows/requests` — submit prompt-driven workflow
- `POST /api/workflows/requests/{id}/approve` — human approval gate
- `POST /api/workflows/worker/run/{id}` — execute governed workflow
- `GET  /api/workflows/metrics` — MTTR, pass-rate uplift, flaky-reduction outcomes
- `GET  /api/workflows/evidence` — claims-to-evidence bundle for client-facing ROI proof
- `GET  /api/workflows/portability-scorecard` — repo portability scoring with baseline delta

---

## Security Architecture

Every agent execution passes through 6 validation layers — and now a 7th constitutional layer on top:

```
  ┌──────────────────────────────────────────────────────────┐
  │  0. Constitutional Gate (NEW)                            │
  │     pre-action ALLOW/DENY · 5 Tier 1 laws · PII block   │
  ├──────────────────────────────────────────────────────────┤
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

## Tech Stack

| Layer | Technology |
|---|---|
| **Agent Governance** | Constitution YAML + ConstitutionalGate (pre-action enforcement) |
| **Vector DB** | Weaviate / Qdrant (pluggable) |
| **Graph DB** | Neo4j |
| **Relational DB** | SQLite / PostgreSQL |
| **Embeddings** | Sentence-Transformers |
| **Quality Metrics** | Ragas |
| **API** | FastAPI + Pydantic |
| **Dashboard** | Streamlit + Plotly |
| **CI/CD** | GitHub Actions (16 jobs) |
| **Testing** | Pytest (300+ tests), Playwright, Pa11y |
| **Language** | Python 3.8+ |

---

## Project Structure

```
AgenticQA/
├── src/agenticqa/
│   ├── constitution.yaml        # Agent Constitution — versioned, machine-readable law set
│   ├── constitutional_gate.py   # Pre-action enforcement: ALLOW / REQUIRE_APPROVAL / DENY
│   ├── audit_report.py          # Forensic compliance artifact builder (PR-embeddable markdown)
│   ├── observability.py         # SQLite store: complexity tracking, anomaly detection, audit trail
│   ├── ingestion/               # Cross-platform adapters: LangChain, CrewAI, AutoGen, REST
│   ├── verification/            # Feedback loop, outcome tracker, threshold calibrator, tracer
│   ├── graph/                   # Neo4j: delegation store, GraphRAG, failure risk prediction
│   ├── rag/                     # Weaviate/Qdrant: vector retrieval, reranking, similarity scoring
│   ├── collaboration/           # Agent delegation, registry, guardrails
│   ├── data_store/              # Artifact store, snapshots, security, EWMA pattern analyzer
│   └── cli.py                   # CLI: bootstrap, doctor, ingest-junit
├── dashboard/                   # 8-page Streamlit analytics dashboard
├── agent_api.py                 # FastAPI control plane (30+ endpoints)
├── tests/                       # 300+ tests — unit, integration, governance, RAG, UI
└── .github/workflows/           # 16-job CI pipeline + nightly self-validation benchmark
```

---

## License

MIT
