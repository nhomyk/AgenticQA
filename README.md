# AgenticQA

**The world's first Agentic Development Lifecycle (ADLC) platform — a closed, self-reinforcing cycle that governs, generates, scans, tests, self-heals, and ships features autonomously: describe → generate → security scan → test → self-heal → SHIP IT → learn → repeat.**

Built on constitutional governance, forensic decision traceability, adversarial red-team hardening, HIPAA/GDPR/EU AI Act compliance, prompt injection detection, LLM model regression testing, cryptographic output provenance, cross-language coverage mapping, and a Perplexity-inspired landing page that gives non-technical users a single input into the entire cycle — without requiring LLMs for the governance layer.

[![CI Pipeline](https://github.com/nhomyk/AgenticQA/actions/workflows/ci.yml/badge.svg)](https://github.com/nhomyk/AgenticQA/actions/workflows/ci.yml)
[![Pipeline Validation](https://github.com/nhomyk/AgenticQA/actions/workflows/pipeline-validation.yml/badge.svg)](https://github.com/nhomyk/AgenticQA/actions/workflows/pipeline-validation.yml)
[![Python 3.8+](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

---

## The ADLC: A Closed Loop, Not a Pipeline

Every software development methodology — SDLC, CI/CD, DevSecOps — was invented to answer the same question: *how do we move faster without breaking things?* Every one of them assumed a human at every critical handoff.

The **Agentic Development Lifecycle (ADLC)** removes those handoffs. It is a closed, self-reinforcing cycle:

```
 ┌─────────────────────────────────────────────────────────────┐
 │                    THE ADLC CYCLE                           │
 │                                                             │
 │   1. DESCRIBE ──▶ 2. GENERATE ──▶ 3. SCAN                  │
 │        ▲                               │                    │
 │        │          AgenticQA            ▼                    │
 │   7. LEARN ◀── 6. SHIP IT ◀── 5. HEAL ◀── 4. TEST          │
 │                                                             │
 │   Every phase governed · Every output signed · No handoffs  │
 └─────────────────────────────────────────────────────────────┘
```

The human bookends the cycle — *describes* the feature at the start, *reviews the verdict* at the end. Everything in between is governed autonomously. And every cycle makes the next one smarter: patterns accumulate, thresholds adapt, risk profiles sharpen.

### The Three Problems It Solves

1. **No governance.** AI agents take actions — deploy, delete, delegate — with no enforceable laws stopping them. The Agent Constitution enforces `ALLOW / REQUIRE_APPROVAL / DENY` before every action in under 5ms.
2. **No forensics.** When something goes wrong, there's no way to reconstruct *why* an agent decided what it did. AgenticQA signs every output with HMAC-SHA256 and generates a forensic audit artifact for every trace.
3. **No learning loop.** Each run is isolated. Knowledge doesn't accumulate. AgenticQA's closed feedback loop means every outcome — pass, fail, repair — feeds back into the system's pattern memory, adaptive thresholds, and developer risk profiles.

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
| **Tier 1** | `DENY` | No destructive ops without CI pass · Delegation depth ≤ 3 · No PII in logs · No traceless external writes · No self-modification · **Agent file scope violations** |
| **Tier 2** | `REQUIRE_APPROVAL` | Production deployments · Infrastructure changes · Bulk operations >1K records |
| **Tier 3** | Alert | Low confidence · High failure rate · RAG similarity degradation |

The gate enforces semantic aliases and typo resistance — `"delet"`, `"clean"`, `"wipe"`, `"release"`, `"ship"`, `"sync"` all route to the correct law. This is the artifact enterprise buyers ask for when evaluating agent platforms for SOC 2, HIPAA, and GDPR compliance. No competitor has it.

---

### 🔴 Red Team Agent — Adversarial Self-Hardening

AgenticQA's eighth agent probes its own governance stack for bypasses, patches discovered vulnerabilities, and proposes constitutional amendments — without human intervention:

```bash
curl -X POST http://localhost:8000/api/red-team/scan \
  -H "Content-Type: application/json" \
  -d '{"mode": "fast", "target": "both", "auto_patch": true}'
# → {"bypass_attempts": 20, "scanner_strength": 0.64, "gate_strength": 1.0,
#    "patches_applied": 3, "proposals_generated": 2,
#    "prompt_injection_surface": 0.0, "prompt_injection_findings": 0, "status": "patched"}
```

**20 bypass techniques across 4 attack categories:**

| Category | Techniques |
|---|---|
| **credential_obfuscation** | base64-encoded secrets, split-field tokens, reversed keys, hex-encoded, nested JSON |
| **shell_injection** | concatenated `rm`+`-rf`, base64 `curl\|bash`, env-var indirection, newline-split curl, Unicode lookalikes |
| **path_traversal** | URL-encoded `%2e%2e`, triple-dot, Windows backslash, null-byte injection |
| **constitutional_gate** | typosquatted actions, destructive aliases, deploy aliases, depth-as-string, bulk aliases, empty trace_id |

OutputScanner defends with **4-pass decode architecture**: raw JSON → Unicode NFKC normalization → base64 decode → URL decode. Discovered bypass patterns are persisted to `.agenticqa/red_team_patterns.json` and auto-loaded on every future scan. Constitutional vulnerabilities are written to `.agenticqa/constitutional_proposals.json` for human review — T1-005 prevents the agent from modifying its own governance files.

---

### 🔍 Prompt Injection Static Analysis

Every codebase scan now checks for **prompt injection attack surface** — code paths where user-controlled input flows unfiltered into LLM system prompts:

```bash
curl "http://localhost:8000/api/redteam/prompt-injection?repo_path=."
# → {"surface_score": 0.85, "total_findings": 3, "findings": [
#     {"rule_id": "PROMPT_INJECTION_SURFACE", "severity": "critical",
#      "file": "app/api/chat/route.ts", "line": 14,
#      "message": "User-controlled input directly concatenated into LLM prompt..."}]}
```

**4 detection rules (SARIF-native, security-severity 7.0–9.5):**

| Rule | Severity | What It Catches |
|---|---|---|
| `PROMPT_INJECTION_SURFACE` | critical (9.5) | User input in f-string / template literal directly assigned to `system`/`prompt` variable |
| `SYSTEM_PROMPT_OVERRIDE` | high (9.0) | User controls `role:` field in the messages array — attacker can inject system-role messages |
| `TEMPLATE_INJECTION` | high (8.0) | `.format()` / `%` / Jinja2 template rendering with user-controlled data |
| `UNVALIDATED_LLM_OUTPUT` | medium (7.0) | LLM response passed directly to `eval()`, `subprocess`, `os.system`, or `innerHTML` |

Findings appear in the Red Team step summary on every CI run alongside bypass attempts and scanner strength.

---

### 🛡️ Legal, HIPAA & Regulatory Compliance Scanning

The ComplianceAgent now runs **four static scanners** on every repo — pure Python, no subprocess, sub-second scan of a 500-file codebase:

#### Legal Risk Scanner
```bash
curl "http://localhost:8000/api/compliance/legal-risk?repo_path=."
# → {"risk_score": 0.92, "total_findings": 6, "critical_findings": 4, "findings": [
#     {"rule_id": "CREDENTIAL_EXPOSURE", "severity": "critical",
#      "file": "app/api/route.ts", "line": 5,
#      "message": "Hardcoded MongoDB Atlas URI with embedded credentials"}]}
```

| Rule | Severity | Detects |
|---|---|---|
| `CREDENTIAL_EXPOSURE` | critical/high | MongoDB Atlas URIs, AWS AKIA keys, OpenAI `sk-` keys, private key material, hardcoded passwords |
| `PII_DOCUMENT_PUBLIC` | critical/high | Legal/employment documents committed to `public/`, `static/`, `assets/` directories |
| `PRIVILEGE_BREACH` | high | File content read + LLM API call within 30 lines — destroys attorney-client privilege (ABA Rule 1.6) |
| `SSRF_RISK` | medium | Hardcoded `localhost:PORT` URLs used as proxy targets — potential SSRF if path is user-controlled |
| `NO_AUTH_ROUTE` | medium | Next.js/Express route handlers with no authentication check |

#### HIPAA PHI Scanner
```bash
curl "http://localhost:8000/api/compliance/hipaa?repo_path=."
# → {"risk_score": 0.95, "total_findings": 4, "critical_findings": 3}
```

| Rule | Severity | Detects |
|---|---|---|
| `PHI_HARDCODED` | critical | SSN literals (`XXX-XX-XXXX`), DOB/MRN variable assignments in source code |
| `PHI_TO_LLM` | critical | PHI variable names within 30 lines of an LLM API call — requires HIPAA BAA (§164.502(e)) |
| `PHI_DOCUMENT_PUBLIC` | critical | HL7, FHIR, patient CSV/JSON files committed to web-accessible directories |
| `PHI_IN_LOGS` | high | PHI field names (`patient_id`, `diagnosis`, `ssn`) passed to logging sinks (§164.312(b)) |
| `HIPAA_AUDIT_MISSING` | high | Health data routes (`/api/patient/`, `/api/health/`) without `audit_log()` call |

---

### 🇪🇺 EU AI Act Compliance Layer

**Full enforcement August 2026.** High-risk AI systems (employment, legal, credit, education, critical infrastructure) face fines up to €30M or 6% global turnover. AgenticQA generates conformity evidence automatically:

```bash
curl "http://localhost:8000/api/compliance/ai-act?repo_path=."
# → {"risk_category": "high_risk", "annex_iii_match": ["legal", "employment"],
#    "conformity_score": 0.25, "findings": [
#     {"article": "Art.9", "status": "missing", "severity": "critical",
#      "remediation": "Create RISK_MANAGEMENT.md with risk register..."},
#     {"article": "Art.22", "status": "missing", "severity": "critical",
#      "remediation": "Add human_override() before any pass/fail decision..."}]}
```

| Article | Checks For | Missing → Severity |
|---|---|---|
| **Art. 9** | `RISK_MANAGEMENT.md`, risk register, code-level fallback handlers | critical |
| **Art. 13** | "AI-generated" disclosure in UI code or API responses | high |
| **Art. 14** | `require_human_review`, override mechanisms, audit logging | high |
| **Art. 22** | LLM output used as pass/fail decision without human override + appeal | critical |

Annex III classification scans README, `package.json`, and config files for 7 high-risk categories (employment, legal, credit, education, critical infrastructure, biometric, law enforcement).

---

### 🔐 AI Output Provenance — Cryptographic Chain of Custody

Every agent execution is **signed and logged** automatically. Prove what the AI said, when, and with which model:

```bash
# Verify any output by hash
curl "http://localhost:8000/api/provenance/verify?output_hash=a3f9c1b2...&agent=sre_agent"
# → {"valid": true, "reason": "valid", "record": {
#     "model_id": "claude-sonnet-4-6", "agent_name": "sre_agent",
#     "timestamp": "2026-02-26T14:22:01+00:00", "run_id": "12345678",
#     "output_length": 2847}}

# Audit chain for an agent
curl "http://localhost:8000/api/provenance/chain?agent=compliance_agent&limit=20"
```

- **HMAC-SHA256** signing: `hash(output) | model_id | timestamp | agent_name` with `AGENTICQA_PROVENANCE_SECRET`
- **Constant-time comparison** prevents timing attacks on verification
- **Tamper detection**: `signature_mismatch` / `not_found` / `valid` states
- Stored in `.agenticqa/provenance/{agent}.jsonl` — included in the CI learning cache

---

### 📐 LLM Model Regression Testing

When you swap models (Sonnet → Haiku, GPT-4o → GPT-4o-mini), does the agent behavior regress? AgenticQA answers quantitatively:

```bash
curl "http://localhost:8000/api/regression/compare?agent=sre_agent&baseline_model=claude-sonnet-4-6&candidate_model=claude-haiku-4-5"
# → {"similarity_score": 0.43, "regression_detected": true,
#    "threshold_used": 0.75, "has_baseline": true}
```

- **Golden snapshots** captured automatically from `BaseAgent._record_execution()` on every successful run
- **Embedding strategy**: fastembed (local, no API calls) → TF-IDF 256-bucket cosine fallback
- **Threshold**: adaptive via `ThresholdCalibrator` (default 0.75); regression flagged if similarity drops below
- Snapshots stored as `artifact_type="llm_golden"` in `TestArtifactStore` — same learning pipeline as all other agents

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

Not a log dump. A forensic verdict with SHA-256 traceability, counterfactual analysis ("what should the agent have done instead?"), and root cause attribution.

---

### 🛠️ Self-Healing CI — Test Repair in the Loop

SREAgent closes the loop on failing tests via a subprocess-sandboxed repair cycle:

1. Haiku reads the failing test + error message (capped at 4 000 chars)
2. Generates a patched version
3. Validates the fix in an isolated subprocess — never touches production code until confirmed green
4. Auto-applies if the sandbox run passes; records the repair in the artifact store

```python
sre.execute({
    "file_path": "src/feature.py",
    "errors": [...],
    "failing_tests": [{"test_file": "tests/test_feature.py", "test_name": "test_edge_case",
                        "error_message": "AssertionError: expected 42, got None"}]
})
# → {"fixes_applied": 3, "tests_repaired": 1, "test_repairs": [...]}
```

---

### 🏭 Agent Factory — Natural Language to Governed Agent

Describe an agent in plain English; the factory scaffolds a fully governed, constitutionally-compliant agent class:

```bash
curl -X POST http://localhost:8000/api/agent-factory/from-prompt \
  -H "Content-Type: application/json" \
  -d '{"description": "An agent that monitors S3 bucket sizes and alerts when storage exceeds thresholds"}'
# → {"spec": {...}, "scaffold": "class StorageMonitor_Agent(BaseAgent): ...", "persisted": true}
```

The factory automatically inserts the agent's capabilities into the Task-Agent Ontology — new agent types are instantly routable without any manual YAML edits.

---

### 🌐 Perplexity-Inspired Landing Page — Bridges Non-Technical and Technical Users

A dark minimal landing page (`public/index.html`, served at `GET /`) makes AgenticQA accessible to product managers, security officers, and executives — no terminal required:

```bash
python agent_api.py        # start API on :8000
open http://localhost:8000  # landing page
```

**What the page does:**

- Animated hero: *"Ship features. Fearlessly."* on a teal CSS grid (background `#080b10`)
- Single AI feature input — type a feature description, press Cmd+Enter
- **5-step progress overlay** animates in real time: Architecture → Security → Code Gen → Tests → Release
- **Verdict card** with gradient border and 4 metric tiles: security · tests · coverage · time
- Returns `SHIP IT` (green) or `REVIEW REQUIRED` (amber) based on `POST /api/demo/submit`
- "View in Dashboard →" links to Streamlit on `:8501`
- "For advanced users" section surfaces 6 dashboard modules

Non-technical users get a one-field UI. Advanced users get the full 16-page analytics dashboard. Same backend, same governance.

---

### 🚀 Autonomous Feature Pipeline — End-to-End

Describe a feature in plain English. The pipeline generates code, scans it, tests it, self-heals failures, and delivers a verdict — zero human steps:

```bash
python run_demo.py
# Uses pre-written stub by default (no API key needed)

ANTHROPIC_API_KEY=sk-ant-... python run_demo.py
# Real Claude Haiku generates the UI component
```

**8-step demo flow:**

1. Create a temp repo
2. Run 5-phase onboarding (architecture + security + coverage + test gen + baseline)
3. Submit feature description via `POST /api/demo/submit`
4. Architecture scan → security scan → stub UI generation
5. UI tests generated (Streamlit AppTest / Jest / Vitest)
6. If any test fails → LLM rewrites failing code → security re-scan → re-test (up to `max_ui_retries=2`)
7. Coverage delta recorded
8. Verdict: `SHIP IT` or `REVIEW REQUIRED`

**Self-healing loop (in `agent_api.py` + `POST /api/pipeline/ui-test-scan`):**

```python
for attempt in range(max_ui_retries):
    result = run_ui_tests(generated_code)
    if result["passed"]:
        break
    generated_code = llm_rewrite(generated_code, result["failures"])
    security_result = security_scan(generated_code)
```

**`POST /api/demo/submit`** — public endpoint, no auth required:

```bash
curl -X POST http://localhost:8000/api/demo/submit \
  -H "Content-Type: application/json" \
  -d '{"description": "Add a login form with OAuth support"}'
# → {"verdict": "SHIP IT", "elapsed_s": 4.2,
#    "security": {"findings": 0}, "tests": {"passed": 3}, "coverage": 0.34}
```

---

### 📦 Repo Onboarding + Coverage Intelligence

Drop AgenticQA onto any repo and get a full baseline in one API call:

```bash
curl -X POST http://localhost:8000/api/onboarding/run \
  -H "Content-Type: application/json" \
  -d '{"repo_path": "."}'
# → {"phases_completed": 5, "architecture": {...}, "security": {...},
#    "coverage": {"mapped_files": 42, "coverage_pct": 0.33},
#    "generated_tests": 7, "baseline_delta": {"trend": "improving"}}
```

**5-phase onboarding orchestrator:**

| Phase | What It Does |
|---|---|
| **Architecture** | Scans imports, HTTP calls, ENV usage, EXTERNAL_HTTP exposure |
| **Security** | 7 sweeps: Legal Risk · HIPAA · EU AI Act · Prompt Injection · CVE Reachability · AI Model SBOM · Agent Trust Graph |
| **Coverage** | Maps source → test files; computes coverage % per language |
| **Test Generation** | LLM generates tests for unmapped source files; validates via compile + collect-only |
| **Baseline** | Captures `BaselineDelta` snapshot at `~/.agenticqa/baselines/{repo_id}.json`; trend: improving / stable / declining |

**CoverageMapper** (`src/agenticqa/onboarding/coverage_mapper.py`) supports stem-variant matching across **11 languages**: Python, TypeScript, Go, Swift, Ruby, Java, Kotlin, JavaScript, Rust, C#, PHP.

`AuthService.py` matches `test_auth.py`, `auth_test.py`, `AuthServiceTest.java` — no configuration required.

**Endpoints:**
- `POST /api/onboarding/run` — run full 5-phase onboarding
- `GET  /api/onboarding/status` — retrieve stored baseline and last delta

**Dashboard "Onboarding" page:** Architecture | Security | Coverage | Generated Tests | Baseline Delta tabs.

---

### 🧠 Agents That Learn — Without Retraining

**Case-Based Reasoning (CBR)** — deterministic pattern matching against historical embeddings. No retraining. No drift.

| | LLM-Based Agents | AgenticQA |
|---|---|---|
| **Cost per 1K decisions** | $30–100 | **$1** |
| **Latency** | 2–5 seconds | **10–50ms** |
| **Deterministic?** | No | **Yes** |
| **Works offline?** | No | **Yes** |
| **Gets better over time?** | Requires retraining | **Automatic** |

**The closed ML learning loop (5 phases):** Feedback loop → Adaptive thresholds → Pattern-driven execution → GraphRAG-informed delegation → Adaptive strategy selection (aggressive / standard / conservative).

---

### 🏥 DataflowHealthMonitor — Ontology-Aware Infra Health

```bash
python -m agenticqa.monitoring.dataflow_health
# → ✅ qdrant        vector_store   healthy   786 pts  (critical)
# → ✅ weaviate      vector_store   healthy   v1.27.0  (secondary)
# → ✅ neo4j         graph_db       healthy   delegation store
# → ✅ artifact_store file_system   healthy   1534 artifacts

curl http://localhost:8000/api/health/dataflow
# → {"healthy": true, "broken_nodes": [], "affected_agents": {}}
```

When Qdrant goes down, the response names all 8 agents as affected. When Neo4j fails, it names only the 4 delegation-capable agents. **The monitor reads the same ontology the agents use.**

---

### 📊 SARIF 2.1.0 Export — Findings in GitHub Code Scanning

AgenticQA findings appear natively in **GitHub's Code Scanning dashboard** alongside CodeQL — with rule IDs, line numbers, and security-severity scores:

```bash
python -m agenticqa.export.sarif --sre sre-output.json --compliance compliance-output.json \
  --redteam redteam-output.json --out results.sarif
```

**25+ SARIF security-severity mappings** — linting, shell, bandit, CVE, legal risk, HIPAA PHI, prompt injection, EU AI Act, and AI Output Provenance (`UNATTESTED_OUTPUT = 8.5`).

---

## The System

Eight specialized agents under constitutional governance across your entire CI/CD pipeline:

```
  Natural-language prompt / CI trigger
         │
         ▼
  ┌─────────────────────────────────────────────────┐
  │  ConstitutionalGate + OutputScanner (Red Team)  │
  │  pre-action ALLOW/DENY · 4-pass decode · <5ms   │
  └─────────────────────────────────────────────────┘
         │
    ┌────┴──────────────────────────────────────┐
    ▼            ▼            ▼            ▼
  SDET         QA        Fullstack     RedTeam
  Agent       Agent       Agent        Agent
    │                                    │
 delegates                          Adversarial
    ▼                              probes + patches
   SRE    ←──── Self-Healing ────────────┘
  Agent          CI Repair
    │
    ▼
  Compliance  ── Legal Risk · HIPAA · EU AI Act ──▶ violations[]
  Agent            provenance + regression
    │
    ▼
  DevOps   Performance
  Agent      Agent
         │
         ▼
  Hybrid RAG Layer
  Qdrant (primary) · Neo4j (graph) · SQLite
  ┌─ Model Regression Snapshots ─────────────────┐
  │  BaseAgent auto-captures every success        │
  │  OutputProvenanceLogger signs every output    │
  └──────────────────────────────────────────────┘
         │
         ▼
  SARIF → GitHub Code Scanning + PR Comment
```

---

## The ADLC Cycle — What Each Phase Does

| Phase | Agent(s) | What Happens | Feeds Back Into |
|---|---|---|---|
| **1. Describe** | *(user)* | Feature described in plain English via landing page | Feature → code prompt |
| **2. Generate** | Fullstack + LLM | UI code generated, written to repo | Security scan input |
| **3. Scan** | ComplianceAgent + ArchitectureScanner | 12-category security sweep; context-aware severity | Verdict gate |
| **4. Test** | SDET + FrontendTestRunner | Tests auto-generated (Streamlit AppTest / Jest / Vitest); run headlessly | Self-heal trigger |
| **5. Heal** | SRE + LLM | Failing tests → LLM rewrite → security re-scan → re-test (max 2 cycles) | Updated code + test results |
| **6. Ship** | QA + ConstitutionalGate | SHIP IT / REVIEW REQUIRED verdict issued; provenance chain signed | Artifact store |
| **7. Learn** | All agents | Pass/fail feeds adaptive thresholds, developer profiles, org memory | Future cycle Phase 1 |

**Every cycle reinforces the next.** After 50 cycles: 96% pattern confidence, per-developer risk profiles, cross-repo institutional memory.

---

## Key Outcomes
| **Model Regression** | Golden snapshot + cosine similarity on model swaps | Regression detected before deployment |
| **Red Team Hardening** | 20 adversarial bypass attempts, patches scanner, proposes amendments | gate_strength 100%, scanner_strength 64%+ |
| **Pattern Learning** | Closed feedback loop: boost/penalize docs, adaptive thresholds | 96% confidence after 50 deployments |
| **Constitutional Enforcement** | Pre-action check before every destructive operation | Zero unauthorized destructive actions |
| **Autonomous UI Generation** | LLM builds frontend from description, 0 critical security findings | SHIP IT in under 5s |
| **UI Self-Healing** | Auto-generates tests, rewrites failing code, re-validates | 0 human interventions required |
| **Coverage Mapping** | Source→test stem matching across 11 languages | 0.0% → 33%+ on first feature |

---

## 16-Page Analytics Dashboard

```bash
streamlit run dashboard/app.py
```

| Page | What It Shows |
|---|---|
| **Operator Console** | Prompt intake → approve → queue → execute → replay. Trace explorer with timeline, audit report generator |
| **Governance** | Agent Constitution viewer, interactive pre-action check simulator, Agent Scopes browser |
| **System Overview** | Stack anatomy, framework matrix, test coverage, live agent metrics |
| **Collaboration** | Interactive delegation network graph + chain traces |
| **Performance** | Bottleneck detection, latency trends, per-agent health scores |
| **GraphRAG** | Hybrid RAG architecture diagram + live recommendation engine |
| **Ontology** | Design-vs-reality — intended paths vs. actual delegation usage |
| **Pipeline** | Data flow, 6-layer security architecture, API connectivity tester |
| **Red Team** | Mode/target/auto_patch controls · scanner + gate strength gauges · vulnerability table · prompt injection findings |
| **Agent Learning** | Developer risk chart · org memory panel · compliance drift · repo fix rate · learning metrics · temporal graphs |
| **Onboarding** | Architecture · Security · Coverage · Generated Tests · Baseline Delta tabs |
| **Compliance Scan** | Legal Risk · HIPAA · EU AI Act · CVE Reachability · AI Model SBOM scan results |
| **Architecture Scan** | Import graph · HTTP exposure · ENV secrets · attack surface score |
| **Agent Safety** | Multi-agent trust graph · escalation paths · missing HITL checks |
| **Release Readiness** | Pre-flight risk score · dev profiles · org memory · violation predictions |
| **Agent Factory** | Natural-language agent builder · spec preview · scaffold viewer |

---

## Quick Start

```bash
git clone https://github.com/nhomyk/AgenticQA.git
cd AgenticQA
pip install -e .

# Start infrastructure (optional — most features work without it)
docker compose -f docker-compose.weaviate.yml up -d

# Run 1538+ unit tests
pytest tests/ -m unit -v

# Launch control plane
uvicorn agent_api:app --host 0.0.0.0 --port 8000

# Open landing page (no API key needed)
open http://localhost:8000

# Run full client demo
python run_demo.py

# Launch dashboard
streamlit run dashboard/app.py
```

### Onboard any repo in 3 commands

```bash
agenticqa bootstrap --repo .          # generate CI wiring + config
agenticqa ingest-junit results.xml    # convert existing test output
agenticqa doctor --repo .             # readiness check with fix commands
```

---

## Core API

**Governance**
- `GET  /api/system/constitution` — machine-readable law set
- `POST /api/system/constitution/check` — pre-action check: `ALLOW / REQUIRE_APPROVAL / DENY`
- `GET  /api/system/agent-scopes` — per-agent file access scopes (8 agents)
- `POST /api/system/agent-scopes/check` — scope check for agent × action × file path

**Compliance & Regulatory Scanning**
- `GET  /api/compliance/legal-risk` — credentials, PII docs, privilege breach, SSRF, missing auth
- `GET  /api/compliance/hipaa` — PHI_HARDCODED, PHI_TO_LLM, PHI_IN_LOGS, HIPAA_AUDIT_MISSING
- `GET  /api/compliance/ai-act` — EU AI Act Annex III classification + Art.9/13/14/22 conformity score

**Security & Adversarial**
- `POST /api/red-team/scan` — adversarial scan (mode: fast|thorough, target: scanner|gate|both, auto_patch: bool)
- `GET  /api/redteam/prompt-injection` — static prompt injection surface scan (4 rules, SARIF-native)
- `POST /api/export/sarif` — convert agent results to SARIF 2.1.0 for GitHub Code Scanning

**AI Output Provenance**
- `GET  /api/provenance/verify` — verify output hash against signed provenance log
- `GET  /api/provenance/chain` — last N provenance records for an agent

**Model Regression**
- `GET  /api/regression/compare` — cosine similarity between baseline and candidate model outputs

**Observability & Auditing**
- `GET  /api/observability/traces/{id}/audit-report` — forensic compliance artifact with stable audit ID
- `GET  /api/observability/traces/{id}/counterfactuals` — "what should the agent have done?" analysis
- `GET  /api/health/dataflow` — ontology-aware infra health; 503 on critical failure

**Agent Factory**
- `POST /api/agent-factory/from-prompt` — natural-language description → scaffold → persisted agent

**Landing Page & Onboarding**
- `GET  /` — landing page (public, no auth)
- `POST /api/demo/submit` — lightweight autonomous pipeline for landing page (public, no auth); returns `{ verdict, elapsed_s, security, tests, coverage }`
- `POST /api/onboarding/run` — 5-phase onboarding: architecture + 7 security sweeps + coverage mapping + LLM test generation + baseline snapshot
- `GET  /api/onboarding/status` — retrieve stored baseline and last `BaselineDelta` trend
- `POST /api/pipeline/ui-test-scan` — standalone UI test scan with autonomous self-heal loop

---

## Security Architecture

```
  ┌──────────────────────────────────────────────────────────┐
  │  0. Constitutional Gate                                  │
  │     pre-action ALLOW/DENY · 6 Tier 1 laws · agent scopes│
  ├──────────────────────────────────────────────────────────┤
  │  0b. OutputScanner (Red Team hardened)                   │
  │     4-pass decode: raw → NFKC → base64 → URL            │
  │     13 danger patterns + learned bypass patterns         │
  ├──────────────────────────────────────────────────────────┤
  │  0c. Static Security Scanners (ComplianceAgent)          │
  │     Legal Risk · HIPAA PHI · Prompt Injection · EU AI Act│
  │     25+ SARIF rules · pure-Python · sub-second           │
  ├──────────────────────────────────────────────────────────┤
  │  0d. AI Output Provenance                                │
  │     HMAC-SHA256 sign · tamper detection · chain of custody│
  ├──────────────────────────────────────────────────────────┤
  │  1. CI/CD Pipeline Gate (16 jobs)                        │
  ├──────────────────────────────────────────────────────────┤
  │  2. Delegation Guardrails (max depth=3 · whitelist)      │
  ├──────────────────────────────────────────────────────────┤
  │  3. Task-Agent Ontology (20 task types · 70% min success)│
  ├──────────────────────────────────────────────────────────┤
  │  4. Schema & PII Validation                              │
  ├──────────────────────────────────────────────────────────┤
  │  5. Data Quality Testing                                 │
  ├──────────────────────────────────────────────────────────┤
  │  6. Immutability & Integrity (SHA-256 · duplicate detect)│
  └──────────────────────────────────────────────────────────┘
```

---

## Tech Stack

| Layer | Technology |
|---|---|
| **Agent Governance** | Constitution YAML + ConstitutionalGate (semantic alias enforcement, typo-resistant) |
| **Adversarial Hardening** | RedTeamAgent · AdversarialGenerator · PatternPatcher · OutputScanner (4-pass) |
| **Prompt Injection** | PromptInjectionScanner (4 rules) · SARIF PROMPT_INJECTION_SURFACE=9.5 |
| **Legal & HIPAA** | LegalRiskScanner · HIPAAPHIScanner · SARIF-native · pure-Python |
| **EU AI Act** | AIActComplianceChecker · Annex III classifier · Art.9/13/14/22 checks |
| **AI Output Provenance** | OutputProvenanceLogger · HMAC-SHA256 · JSONL chain · verify API |
| **Model Regression** | ModelRegressionTester · GoldenSnapshot · fastembed → TF-IDF cosine fallback |
| **Agent Factory** | NaturalLanguageSpecExtractor · Claude Haiku (spec extraction) · scaffold generator |
| **Self-Healing CI** | SREAgent._attempt_test_repair · SubprocessRunner sandbox · Haiku-generated patches |
| **Infra Health** | DataflowHealthMonitor · ontology-aware probes · Weaviate version detection |
| **Security Output** | SARIFExporter · SARIF 2.1.0 · GitHub Code Scanning · 25+ severity mappings |
| **Shell Linting** | shellcheck (SC codes) · SREAgent._run_shell_linter |
| **Vector DB** | Qdrant (primary) / Weaviate 1.27.0+ (secondary) |
| **Graph DB** | Neo4j |
| **Relational DB** | SQLite / PostgreSQL |
| **Embeddings** | fastembed (local) / Sentence-Transformers |
| **API** | FastAPI + Pydantic (120+ endpoints) |
| **Dashboard** | Streamlit + Plotly (16 pages) |
| **CI/CD** | GitHub Actions (16 jobs, SARIF upload, nightly self-validation) |
| **Testing** | Pytest (1538+ unit tests) |
| **Language** | Python 3.8+ |
| **Landing Page** | Vanilla HTML/CSS/JS · animated CSS grid · Perplexity-inspired dark UI |
| **Frontend Testing** | Streamlit AppTest · Jest · Vitest · FrontendTestGenerator · FrontendTestRunner |
| **Repo Onboarding** | CoverageMapper · ArchitectureScanner · RepoOnboarder · BaselineDelta |

---

## Project Structure

```
AgenticQA/
├── public/                      # Landing page (served at GET /)
│   └── index.html               # Perplexity-inspired dark minimal UI
├── run_demo.py                  # 8-step end-to-end client demo (no API key needed)
├── src/agenticqa/
│   ├── constitution.yaml        # Agent Constitution — versioned, machine-readable law set
│   ├── agent_scopes.yaml        # Per-agent file access scopes (8 agents)
│   ├── constitutional_gate.py   # Pre-action enforcement: ALLOW / REQUIRE_APPROVAL / DENY
│   ├── audit_report.py          # Forensic compliance artifact builder (PR-embeddable)
│   ├── observability.py         # SQLite store: complexity tracking, anomaly detection
│   ├── security/                # LegalRiskScanner · HIPAAPHIScanner · PromptInjectionScanner · CVEReachability
│   ├── compliance/              # AIActComplianceChecker (EU AI Act) · ComplianceDriftDetector
│   ├── provenance/              # OutputProvenanceLogger · HMAC-SHA256 signing · verify API
│   ├── regression/              # ModelRegressionTester · GoldenSnapshot · cosine similarity
│   ├── verification/            # Feedback loop, outcome tracker, threshold calibrator
│   ├── graph/                   # Neo4j: delegation store, GraphRAG, temporal violation store
│   ├── rag/                     # Weaviate/Qdrant: vector retrieval, reranking
│   ├── collaboration/           # Agent delegation, registry, guardrails
│   ├── redteam/                 # AdversarialGenerator (20 techniques) · PatternPatcher
│   ├── factory/                 # NaturalLanguageSpecExtractor · agent scaffold generator
│   │   └── sandbox/             # SubprocessRunner · OutputScanner (4-pass decode)
│   ├── monitoring/              # DataflowHealthMonitor · 5 probes · ontology-aware impact
│   ├── onboarding/              # CoverageMapper · RepoOnboarder · BaselineDelta
│   ├── testing/                 # FrontendTestGenerator · FrontendTestRunner (Streamlit/Jest/Vitest)
│   ├── export/                  # SARIFExporter · SARIF 2.1.0 · 25+ severity mappings
│   └── cli.py                   # CLI: bootstrap, doctor, ingest-junit
├── dashboard/                   # 16-page Streamlit analytics dashboard
├── agent_api.py                 # FastAPI control plane (120+ endpoints)
├── src/agents.py                # 8 agents: QA, Performance, Compliance, DevOps, SRE, SDET, Fullstack, RedTeam
├── ingest_ci_artifacts.py       # CI data bridge — ESLint, red-team, migration → learning system
├── tests/                       # 1538+ unit tests — governance, red team, HIPAA, EU AI Act, provenance
└── .github/workflows/           # 16-job CI pipeline + nightly self-validation
```

---

## License

MIT
