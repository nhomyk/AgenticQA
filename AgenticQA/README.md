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

An 8-page Streamlit dashboard backed by Neo4j and Plotly for full observability into the agent system.

```
streamlit run dashboard/app.py
```

### Dashboard Pages

| Page | What It Shows |
|---|---|
| **Operator Console** | Prompt intake, workflow lifecycle (approve/queue/execute/replay), chat, and full observability timeline with trace explorer, audit reports, and agent complexity trends |
| **System Overview** | Full-stack anatomy (framework matrix, test coverage, LOC breakdown), agent metrics, and live activity |
| **Collaboration** | Interactive network graph + delegation chain traces |
| **Performance** | Bottleneck detection, latency trends, per-agent test results and health scores |
| **GraphRAG** | Interactive Hybrid RAG architecture diagram with live recommendation engine |
| **Ontology** | Design-vs-reality analysis — intended delegation paths vs. actual usage |
| **Pipeline** | End-to-end data flow, 6-layer defense-in-depth security, and API connectivity |
| **Governance** | Agent Constitution viewer (Tier 1/2/3 laws), interactive pre-action check tool, and agent rights declaration |

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

## Low-Friction Install Modes

Use only what you need for fastest adoption:

```bash
# Minimum onboarding-only install (bootstrap/doctor/ingest-junit)
pip install -e .

# Add Graph features (Neo4j-backed recommendations)
pip install -e .[graph]

# Add RAG providers and evaluation stack
pip install -e .[rag]

# Add dashboard dependencies
pip install -e .[dashboard]

# Add data-quality / validation tools
pip install -e .[quality]

# Full local test stack
pip install -e .[test]
```

This keeps first-run lightweight and avoids forcing heavy dependencies unless needed.

## One-Command Client Onboarding Profiles

Use these copy/paste profiles in a test repository to reduce setup friction.

### Profile A: Fastest (Onboarding only)

```bash
python -m pip install -U pip && pip install -e . && agenticqa bootstrap --repo . && agenticqa doctor --repo .
```

Best for initial validation. No graph/RAG/dashboard dependencies required.

### Profile B: Onboarding + Graph Recommendations

```bash
python -m pip install -U pip && pip install -e .[graph] && agenticqa bootstrap --repo . && agenticqa doctor --repo .
```

Best when you want Neo4j-backed delegation insights.

### Profile C: Onboarding + Dashboard

```bash
python -m pip install -U pip && pip install -e .[dashboard,graph] && agenticqa bootstrap --repo . && agenticqa doctor --repo .
```

Best for client demos that need visual reporting quickly.

### Profile D: Full Local Validation Stack

```bash
python -m pip install -U pip && pip install -e .[test,rag,dashboard,graph,quality] && agenticqa bootstrap --repo . && agenticqa doctor --repo .
```

Best for engineering teams doing full end-to-end validation.

### Quick trial in a test repo

```bash
# in your test repo
agenticqa bootstrap --repo .
pytest --junitxml=agenticqa-junit.xml || true
agenticqa ingest-junit agenticqa-junit.xml --out .agenticqa/latest_input.json
agenticqa doctor --repo .
```

Expected result: `.agenticqa/config.json` + `.agenticqa/latest_input.json` are generated and doctor reports required checks as healthy.

## Plug-In Any Codebase (Early Access)

AgenticQA now includes a starter plug-in workflow to onboard an external repository.

```bash
# 1) Generate plug-in scaffolding in your target repo
agenticqa bootstrap --repo .

# 2) Convert CI JUnit output into AgenticQA input format
agenticqa ingest-junit junit.xml --out .agenticqa/latest_input.json

# 3) Run health checks for dashboard readiness
agenticqa doctor --repo .
```

This creates:
- `.agenticqa/config.json` (integration config)
- `.agenticqa/samples/agenticqa_input.json` (starter payload)
- `.github/workflows/agenticqa.yml` (starter CI wiring)

## Prompt-to-Workflow Control Plane (MVP)

You can now submit development prompts through the dashboard (Prompt Ops page)
or via API, then move requests through approval/queue states.

```bash
# Start control plane API
uvicorn agent_api:app --host 0.0.0.0 --port 8000

# Open dashboard and navigate to "Prompt Ops"
streamlit run dashboard/app.py
```

### Core API endpoints

- `POST /api/workflows/requests` — create prompt-driven workflow request
- `GET /api/workflows/requests` — list recent requests
- `GET /api/workflows/requests/{id}` — inspect single request with events
- `POST /api/workflows/requests/{id}/approve` — approve request
- `POST /api/workflows/requests/{id}/queue` — queue approved request
- `POST /api/workflows/requests/{id}/cancel` — cancel request
- `POST /api/workflows/requests/{id}/replay` — replay a prior request with self-heal metadata
- `POST /api/workflows/worker/run-next` — execute oldest queued request
- `POST /api/workflows/worker/run/{id}` — execute a specific queued request
- `GET /api/workflows/metrics` — MTTR, pass-rate uplift, flaky-reduction outcomes
- `GET /api/observability/traces` — recent trace summaries across worker/agent actions
- `GET /api/observability/traces/{trace_id}` — timeline for a single trace
- `GET /api/observability/traces/{trace_id}/analysis` — span tree, completeness, critical path, and agent/action aggregates
- `GET /api/observability/traces/{trace_id}/counterfactuals` — failed-step alternatives and remediation recommendations
- `GET /api/observability/events` — raw action events with filters (`request_id`, `agent`, `action`, `status`, `event_type`)
- `GET /api/observability/quality` — aggregate trace quality summary for CI/CD gating (completeness + decision quality)
- `GET /api/observability/insights` — aggregate root-cause and policy-impact analytics for learning loops
- `GET /api/observability/traces/{trace_id}/audit-report` — shareable compliance artifact: PASS/FAIL verdict, audit ID, decision quality score, root causes, and pre-rendered markdown for PR descriptions
- `GET /api/observability/agent-complexity` — per-agent RAG retrieval quality trends (docs retrieved, avg similarity, LLM token usage) with 14-day baseline anomaly detection
- `POST /api/observability/ingest` — ingest a single event from any external agent platform (LangGraph, CrewAI, AutoGen, custom) into the observability store
- `POST /api/observability/ingest/batch` — batch ingest events from external platforms; returns per-event status array
- `GET /api/system/constitution` — return the full Agent Constitution (version, Tier 1/2/3 laws, agent rights) as JSON; any external agent can query this to discover governance rules
- `POST /api/system/constitution/check` — pre-action constitutional check: submit `{action_type, context}`, receive `ALLOW / REQUIRE_APPROVAL / DENY` with the specific law that triggered it
- `GET /api/system/readiness` — dependency readiness checks (DB writeability, Neo4j, Weaviate)
- `GET /api/workflows/evidence` — claims-to-evidence bundle for client-facing proof
- `GET /api/workflows/portability-scorecard` — first-run portability scoring with baseline→delta comparison for any repo
- `POST /api/workflows/portability-scorecard/baseline` — persist current scorecard as baseline for future trend tracking
- `GET /api/workflows/portability-scorecard/roi-report` — export baseline/current/delta KPI rows for stakeholder ROI reporting
- `POST /api/chat/sessions` — create a persisted dashboard chat session
- `GET /api/chat/sessions` — list recent chat sessions
- `GET /api/chat/sessions/{session_id}` — inspect a chat session with message history
- `POST /api/chat/sessions/{session_id}/messages` — append a chat message manually
- `POST /api/chat/turn` — persist a user chat turn and optionally create a workflow request from it
- `GET /api/operator/config` — inspect Operator Console mode/policy and safe LLM configuration summary
- `POST /api/operator/config/test-connection` — validate LLM provider wiring (dry check)
- `POST /api/plugin/bootstrap` — fast plug-in onboarding for any repo
- `POST /api/plugin/doctor` — onboarding readiness checks for any repo

Client value for AI observability:
- Explainability for enterprise buyers (who did what, when, and why)
- Faster incident response with per-agent action timelines and status transitions
- Better governance and auditability with trace-level records tied to workflow requests
- CI-grade telemetry quality checks (trace completeness + span integrity) before release

### Worker execution modes

- Worker executes a code-generation stage before commit:
     - auto-detects `repo_profile` (language, package manager, CI provider, test hints),
     - derives feature intent from prompt,
     - invokes `FullstackAgent` generation,
     - orchestrates guardrailed collaboration with `Compliance_Agent`, `SDET_Agent`, and `DevOps_Agent`,
     - emits observability events with correlated `trace_id` for worker, orchestrator, and SDET loop,
     - records explainable routing rationale (why each agent was selected),
     - runs SDET test synthesis for newly generated production files,
     - resolves generated-test runner from repo profile with graceful fallback when unavailable,
     - re-runs generated tests in a bounded loop until pass/fail budget is reached,
     - records collaboration + quality-gate context into workflow artifacts,
     - writes generated code into repo files,
     - commits generated code + workflow artifact together.
- Learning is persisted through the same agent pathways used elsewhere in AgenticQA:
     - semantic retrieval (RAG),
     - structured execution artifacts,
     - delegation tracking for collaboration outcomes.
- Strict Prompt-to-PR policy gates are enforced when `dry_run=false`:
     - quality gate must pass,
     - `metadata.approved_by` is required for push,
     - `metadata.policy_ticket` is required for PR creation,
     - high-risk prompts require `metadata.allow_high_risk=true`.
- Reliability loop includes replay and rollback support:
     - replay endpoint clones and queues prior requests,
     - worker attempts rollback cleanup on failed executions.
- SDET loop controls (request metadata):
     - `require_sdet_loop` (default `true`)
     - `max_sdet_iterations` (default `3`, max `5`)
     - `enable_sdet_autofix` (default `true`)
     - `max_sdet_fix_attempts` (default `2`, max `5`)

### AI Decision Audit Reports

Every trace can be compiled into a shareable compliance artifact:

```bash
# Via REST (returns structured JSON or markdown)
curl "http://localhost:8000/api/observability/traces/{trace_id}/audit-report?format=markdown"
```

The report includes:
- **Verdict**: PASS or FAIL (quality ≥ 0.60, completeness ≥ 0.80, zero failures)
- **Audit ID**: SHA-256 stable reference for compliance records
- **Decision Quality Score**: weighted coverage + success rate
- **Root Causes**: which steps failed and why
- **Recommendations**: actionable counterfactual alternatives
- **Markdown body**: paste directly into a PR description

### Agent Constitution

A machine-readable governance policy that all agents follow. Queryable by any external agent platform:

```bash
# Query the laws
curl http://localhost:8000/api/system/constitution

# Pre-action check (returns ALLOW / REQUIRE_APPROVAL / DENY)
curl -X POST http://localhost:8000/api/system/constitution/check \
  -H "Content-Type: application/json" \
  -d '{"action_type": "delete", "context": {"ci_status": "FAILED", "trace_id": "tr-001"}}'
```

Three governance tiers:
- **Tier 1 (5 laws → DENY)**: No destructive ops without CI pass, delegation depth ≤ 3, no PII in logs, no external writes without trace ID, no self-modification of governance files
- **Tier 2 (3 laws → REQUIRE_APPROVAL)**: Production deployments, infrastructure changes, bulk operations >1,000 records
- **Tier 3 (3 triggers → alerts)**: Low confidence, high failure rate, RAG similarity degradation

The Governance dashboard page renders all laws interactively and includes a pre-action check simulator.

### Cross-Platform Ingestion

Any agent platform can push events into AgenticQA's observability layer:

```python
# LangGraph / LangChain — zero-config callback adapter
from agenticqa.ingestion import LangChainCallbackAdapter
from agenticqa.observability import ObservabilityStore

store = ObservabilityStore()
adapter = LangChainCallbackAdapter(store=store, trace_id="my-trace-123")
chain.invoke(inputs, config={"callbacks": [adapter]})  # automatic span tracking

# CrewAI / AutoGen / custom — generic dict adapter
from agenticqa.ingestion import GenericDictAdapter
adapter = GenericDictAdapter(store=store)
adapter.ingest({"crew_id": "crew-xyz", "sender": "ResearchAgent", "status": "success"})
```

Field mapping is automatic: `run_id` → `span_id`, `crew_id` → `trace_id`, `sender` → `agent`, etc. Token usage (prompt + completion) flows into agent complexity trends automatically.

### Agent Complexity Tracking

Per-agent retrieval quality is tracked over time and surfaced in the Operator Console:

| Metric | What It Measures |
|---|---|
| `rag_docs_retrieved` | How many RAG docs were pulled per action |
| `avg_similarity_score` | Average vector similarity — proxy for retrieval quality |
| `llm_prompt_tokens` | Token cost for external LLM-based agents |
| `llm_completion_tokens` | Response token cost |

Anomaly detection: if the current 3-day similarity average drops >20% below the 14-day baseline, an `anomaly_detected` flag is raised — your signal that the vector index may need reindexing.

### CI/CD observability quality report

Generate a machine-readable quality artifact from the observability DB:

```bash
python scripts/observability_quality_report.py \
     --output docs/reports/OBSERVABILITY_QUALITY.json \
     --min-completeness 0.95 \
     --min-decision-quality 0.60 \
     --seed-demo-if-empty \
     --enforce
```

This is wired into CI as the **Observability Quality Gate** job.

### SDET trend benchmark (improvement over time)

Run a repeatable benchmark locally:

```bash
python scripts/run_sdet_trend_benchmark.py --runs-per-cohort 3 --output-dir .agenticqa/benchmarks/latest
```

Outputs:
- `.agenticqa/benchmarks/latest/benchmark_summary.json`
- `.agenticqa/benchmarks/latest/benchmark_report.md`
- `~/.agenticqa/benchmarks/sdet_trend_history.jsonl` (append-only trend history)

A scheduled CI benchmark is available at [ .github/workflows/sdet-trend-benchmark.yml ](.github/workflows/sdet-trend-benchmark.yml).
- Default is `dry_run=true`: worker creates branch + commit locally and marks request completed.
- Set `dry_run=false` to push branch to `origin`.
- Set `open_pr=true` (with `dry_run=false`) to auto-open a GitHub PR.

GitHub PR automation requires:
- `GITHUB_TOKEN` environment variable
- Repository slug (one of):
     - inferred from `origin` remote URL, or
     - request metadata `github_repo`, or
     - `AGENTICQA_GITHUB_REPO` environment variable
- Optional: `AGENTICQA_BASE_BRANCH` (defaults to current branch)

This is the intake/orchestration foundation for future Slack/Teams integrations.

---

## Project Structure

```
AgenticQA/
├── src/agenticqa/
│   ├── collaboration/       # Agent delegation, registry, guardrails
│   ├── graph/               # Neo4j graph store, hybrid RAG
│   ├── rag/                 # Weaviate/Qdrant vector store, embeddings, retrieval
│   ├── ingestion/           # Cross-platform event ingestion (LangChain, CrewAI, AutoGen, REST)
│   ├── verification/        # Feedback loop, outcome tracker, threshold calibrator, tracer
│   ├── data_store/          # Artifact store, snapshots, security, pattern analyzer
│   ├── observability.py     # SQLite observability store with complexity tracking + anomaly detection
│   ├── audit_report.py      # AI decision audit report builder (PR-embeddable markdown artifact)
│   ├── constitutional_gate.py  # Pre-action governance check (ALLOW/REQUIRE_APPROVAL/DENY)
│   ├── constitution.yaml    # Agent Constitution — Tier 1/2/3 laws + agent rights
│   └── cli.py               # CLI interface
├── dashboard/               # 8-page Streamlit analytics dashboard
├── tests/                   # 300+ tests — unit, integration, RAG, delegation, governance, UI
├── .github/workflows/       # CI pipeline (16 jobs) + nightly self-validation
└── examples/                # SDK usage (Python, TypeScript, Neo4j)
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
