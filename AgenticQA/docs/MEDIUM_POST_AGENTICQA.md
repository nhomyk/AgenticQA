# Your AI Agents Have No Laws. I Built the Answer.

*How I built an autonomous multi-agent CI/CD platform with constitutional governance, forensic decision traceability, and universal observability — with LLM-free native agents.*

---

The AI agent space is moving fast. LangGraph, CrewAI, AutoGen — every week there's a new framework promising autonomous software delivery. Teams are deploying agents that deploy code, delete files, modify infrastructure, and delegate tasks to other agents.

And most of them are operating without a single enforceable rule governing their behavior.

That terrifies me. It should terrify you too.

I spent the last year building **AgenticQA** — a multi-agent CI/CD platform — and the thing I kept running into wasn't model quality or retrieval accuracy. It was a more fundamental problem: **there's no layer in any of these frameworks that stops an agent from doing something catastrophic before it happens.**

This post is about the three architectural decisions I made that I believe are genuinely new in this space — and what I learned building them.

---

## The Three Problems Nobody Is Solving

After working with enterprise engineering teams, I kept hearing the same concerns when the topic of AI agents came up:

**"We have no governance."** Who's stopping an agent from deleting a production database because the CI check failed? What prevents an SDET agent from modifying a GitHub Actions workflow it was never supposed to touch?

**"We have no forensics."** When something goes wrong — and it will — how do you reconstruct why the agent made a specific decision? A log dump isn't a forensic artifact. You need a chain of custody.

**"We can't use this cross-platform."** LangGraph's telemetry doesn't talk to CrewAI's. AutoGen has its own observability story. Enterprise teams running heterogeneous stacks have no shared observability layer.

I built AgenticQA to solve all three. Here's how.

---

## Innovation 1: The Agent Constitution

This is the thing I'm most proud of, and as far as I can tell, no other agent platform has shipped it.

AgenticQA ships a **machine-readable governance document** — a YAML file called the Agent Constitution — that every agent queries before taking any action. Pre-action. Not as a log, not as an alert after the fact. Before.

```bash
# Any agent, anywhere, can query the law
curl http://localhost:8000/api/system/constitution

# Pre-action check — instant ALLOW / REQUIRE_APPROVAL / DENY
curl -X POST http://localhost:8000/api/system/constitution/check \
  -H "Content-Type: application/json" \
  -d '{"action_type": "delete", "context": {"ci_status": "FAILED", "trace_id": "tr-001"}}'

# Response:
# → {"verdict": "DENY", "law": "T1-001", "reason": "Destructive op blocked: CI not passing"}
```

The Constitution has three enforcement tiers:

| Tier | Verdict | What It Governs |
|---|---|---|
| **Tier 1** | `DENY` | Destructive ops without CI pass · Delegation depth > 3 · PII in logs · Traceless external writes · Self-modification · File scope violations |
| **Tier 2** | `REQUIRE_APPROVAL` | Production deployments · Infrastructure changes · Bulk operations > 1,000 records |
| **Tier 3** | Alert only | Low confidence · High failure rate · RAG similarity degradation |

This isn't just a filter. It's **versioned, git-tracked, and queryable by external agent frameworks** via a stable API. If you're running LangGraph agents against your infrastructure, you can point them at AgenticQA's constitution endpoint and get governance for free.

Why does this matter for enterprise buyers? Because this is the exact artifact compliance teams ask for when evaluating agent platforms against SOC 2, HIPAA, and GDPR. It's the difference between "we have guardrails" and "here is the versioned law set governing every agent action, with a stable audit trail."

---

## Innovation 2: Agent File Scopes — YAML-Governed Access Control

This came out of a real scenario I kept imagining: an SDET agent, trying to be helpful, modifies a GitHub Actions workflow because it "detected an issue." The CI pipeline breaks. Nobody knows why because there's no record of what the agent touched.

AgenticQA solves this with **declared file scopes** — every agent has a YAML-backed access policy enforced as a Tier 1 constitutional law before any write operation.

| Agent | Can Write | Cannot Write |
|---|---|---|
| **SDET_Agent** | `tests/**`, `conftest.py` | `.github/**`, `*.yml`, `src/**` |
| **SRE_Agent** | `.github/**`, `*.sh`, `Dockerfile` | `src/**`, `tests/**` |
| **Fullstack_Agent** | `src/**`, `frontend/**`, `api/**` | `.github/**`, `tests/**` |
| **DevOps_Agent** | `k8s/**`, `terraform/**`, `.github/workflows/**` | `src/**`, `tests/**` |
| **Compliance_Agent** | *(read-only — enforced)* | Everything |

```bash
curl -X POST http://localhost:8000/api/system/agent-scopes/check \
  -H "Content-Type: application/json" \
  -d '{"agent": "SDET_Agent", "action": "write", "file_path": ".github/workflows/ci.yml"}'

# → {"verdict": "DENY", "law": "T1-006", "reason": "SDET_Agent is not permitted to write .github/workflows/ci.yml"}
```

This is not OS-level file permissions. This is the agent's own governance layer denying the action before any filesystem call is made. It's policy-as-code at the agent identity layer.

Enterprise security teams have a specific ask when evaluating whether to run autonomous agents against production codebases: **what can each agent touch, and how is that enforced?** This is that answer.

---

## Innovation 3: Forensic AI Decision Audit Reports

Every agent execution in AgenticQA produces a **shareable compliance artifact** with a stable audit ID. Not a log. Not a trace dump. A forensic verdict.

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

The report includes:
- SHA-256 trace integrity hash
- Counterfactual analysis — "what should the agent have done instead?"
- Root cause attribution across the delegation chain
- Decision quality scoring and completeness metrics

These are designed to be **embedded directly into pull request descriptions**:

```bash
curl "http://localhost:8000/api/observability/traces/{trace_id}/audit-report?format=markdown"
```

Every PR that touches agent-generated code carries its own forensic record. When an auditor, a compliance officer, or a skeptical engineering manager asks "why did the agent do this?" — you have an answer with a stable ID, not a Slack message saying "I think the model decided to..."

---

## The Architecture Decision That Made This All Possible: LLM-Free by Design

The most counterintuitive thing about AgenticQA's native agents is that they don't rely on LLMs for their decisions. This was deliberate.

They use **Case-Based Reasoning (CBR)** — deterministic pattern matching against historical embeddings. Every deployment teaches the platform. No retraining. No prompt engineering. No API latency. The platform also supports LLM-based agents through its ingestion adapters — it observes and governs them too — but the core decision engine is intentionally LLM-free.

| | LLM-Based Agents | AgenticQA (native) |
|---|---|---|
| **Cost per 1,000 decisions** | $30–100 | ~$1 |
| **Decision latency** | 2–5 seconds | 10–50ms |
| **Deterministic?** | No | Yes |
| **Works offline?** | No | Yes |
| **Explainable?** | No | Yes |
| **Improves over time?** | Requires retraining | Automatic |

The learning loop is implemented at the retrieval layer: every execution stores `rag_docs_retrieved`, `avg_similarity_score`, and `patterns_considered`. An EWMA flakiness tracker (α=0.3) detects degrading agents before a human notices. Anomaly detection fires when RAG retrieval similarity drops more than 20% below the 14-day baseline — which means the platform self-monitors its own intelligence quality.

This is what makes the governance layer possible. You can't write deterministic laws for a system that's non-deterministic. By keeping the native agents CBR-based, every decision is traceable, reproducible, and auditable. The constitution can be enforced because the agents don't make probabilistic guesses — they retrieve proven patterns and apply them under governed conditions.

---

## The System at a Glance

Seven specialized agents collaborate under constitutional governance across the full CI/CD pipeline:

```
  Prompt / trigger
         │
         ▼
  ┌────────────────────────┐
  │    ConstitutionalGate  │  ← ALLOW / DENY before anything happens
  └───────────┬────────────┘
              │
     ┌────────┼────────┐
     ▼        ▼        ▼
  SDET     QA Agent  Fullstack
  Agent              Agent
     │                  │
  delegates         validates with
     ▼                  ▼
  SRE Agent       Compliance Agent
                        │
                   consults
                        ▼
                  DevOps + Performance
                        │
                        ▼
  ┌─────────────────────────────────────┐
  │          Hybrid RAG Layer           │
  │  Weaviate + Neo4j + SQLite          │
  │  "What worked? Who succeeded? When?"│
  └─────────────────────────────────────┘
         │
         ▼
  Observability → Audit Report → PR artifact
```

The hybrid RAG layer is worth calling out separately. Most agent platforms use a single vector store. AgenticQA uses three:

- **Weaviate** for semantic similarity retrieval (what docs are relevant?)
- **Neo4j** for delegation graph intelligence (who should handle this? what's the failure risk?)
- **SQLite/PostgreSQL** for outcome tracking and threshold calibration

Neo4j doesn't just store delegation history — it actively recommends delegation targets and predicts failure risk before the delegation happens.

---

## Universal Observability — Works With Any Framework

One thing I was deliberate about: AgenticQA shouldn't require you to switch frameworks. If you're running LangGraph today, you shouldn't have to rebuild.

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

Field mapping is automatic. Token usage flows into complexity trends. Every event is queryable through the audit API immediately. **AgenticQA becomes the observability backbone for your entire agent fleet, regardless of what framework each agent was built in.**

---

## What This Looks Like in Practice

| Capability | What Happens | Internal Benchmark Result |
|---|---|---|
| Self-Healing | SRE detects linting errors, retrieves proven fix, commits | 90% of errors resolved autonomously |
| Coverage Intelligence | SDET identifies gaps, prioritizes by criticality | 100% of critical gaps surfaced |
| Code Generation | Fullstack generates → compliance check → tests → commit | 80% of simple features handled end-to-end |
| Pattern Learning | Each run stored as embeddings, retrieved before next decision | 96% retrieval confidence after 50 deployments |
| Self-Validation | Nightly pipeline injects intentional errors to verify agents | 99.5% pipeline uptime across validation runs |
| Constitutional Enforcement | Pre-action check on every destructive or sensitive operation | Zero constitutional violations by design |

*Capability results are from internal benchmark and validation runs. Constitutional enforcement (final row) is architecturally guaranteed — the gate is mandatory, not probabilistic.*

---

## Why This Matters Now

The enterprise conversation around AI agents is shifting. The early question was "can agents do this?" That's mostly been answered.

The current question is: **"Can we trust agents to do this in production, with real data, on real infrastructure, without a human watching every action?"**

That question requires governance. It requires forensics. It requires a system that can prove, after the fact, that every agent acted within defined boundaries — and if it didn't, it was stopped before the damage was done.

That's the gap I built AgenticQA to fill.

---

## Try It

```bash
git clone https://github.com/nhomyk/AgenticQA.git
cd AgenticQA
pip install -e .
uvicorn agent_api:app --host 0.0.0.0 --port 8000
streamlit run dashboard/app.py
```

The constitution, agent scopes, governance API, and observability layer all run without Docker. The full stack with Weaviate + Neo4j takes one extra command.

I'm actively looking for teams who are deploying agents in CI/CD and want to talk about the governance layer. If that's you — reach out.

---

*AgenticQA is MIT licensed. The governance layer (Agent Constitution + file scopes + ConstitutionalGate) is the part I'm most interested in discussing with teams running agents at scale.*
