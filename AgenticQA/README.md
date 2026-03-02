# AgenticQA

**The world's first Agentic Development Lifecycle (ADLC) platform — a closed, self-reinforcing cycle that governs, generates, scans, tests, self-heals, and ships features autonomously: describe → generate → security scan → test → self-heal → SHIP IT → learn → repeat.**

Built on constitutional governance, forensic decision traceability, adversarial red-team hardening, HIPAA/GDPR/EU AI Act compliance, prompt injection detection, LLM model regression testing, cryptographic output provenance, AI model SBOM generation, multi-agent trust graph analysis, API security hardening with 3-layer middleware, agent safety modules (destructive action interception, scope leasing, instruction persistence), concurrent worker pool with git worktree isolation, cross-language coverage mapping (11 languages), MCP scanner support for 6 languages, and a futuristic minimal landing page that gives non-technical users a single input into the entire cycle — without requiring LLMs for the governance layer.

[![CI Pipeline](https://github.com/nhomyk/AgenticQA/actions/workflows/ci.yml/badge.svg)](https://github.com/nhomyk/AgenticQA/actions/workflows/ci.yml)
[![Pipeline Validation](https://github.com/nhomyk/AgenticQA/actions/workflows/pipeline-validation.yml/badge.svg)](https://github.com/nhomyk/AgenticQA/actions/workflows/pipeline-validation.yml)
[![Security Scan](https://github.com/nhomyk/AgenticQA/actions/workflows/feature-request.yml/badge.svg)](https://github.com/nhomyk/AgenticQA/actions/workflows/feature-request.yml)
[![Python 3.8+](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![2308+ Tests](https://img.shields.io/badge/tests-2308%2B-brightgreen.svg)](https://github.com/nhomyk/AgenticQA/actions)

---

## GitHub Marketplace Actions

Standalone security and compliance scanners built on AgenticQA — free, no API key required, results in your GitHub Security tab.

| Action | What It Does | Marketplace |
|--------|-------------|-------------|
| **MCP Security Scan** | Scans MCP servers & AI agents for 24 vulnerability classes: tool poisoning, SSRF, prompt injection, DataFlow taint | [![Marketplace](https://img.shields.io/badge/Marketplace-mcp--scan--action-blue?logo=github)](https://github.com/marketplace/actions/mcp-security-scan) |
| **EU AI Act Compliance** | Annex III risk classification + Art.9/13/14/22 conformity check — fines up to €30M | [![Marketplace](https://img.shields.io/badge/Marketplace-eu--ai--act--check--action-blue?logo=github)](https://github.com/marketplace/actions/eu-ai-act-compliance-check) |
| **AgenticQA Architecture Scan** | Maps every integration point across 13 CWE categories — attack surface score, test coverage gaps, SARIF output | [![Marketplace](https://img.shields.io/badge/Marketplace-agenticqa--scan--action-blue?logo=github)](https://github.com/marketplace/actions/agenticqa-architecture-scan) |

```yaml
# Full AI system security coverage in 3 lines:
- uses: nhomyk/agenticqa-scan-action@v1    # architecture map — 13 CWE categories
- uses: nhomyk/mcp-scan-action@v1          # MCP/AI-specific security threats
- uses: nhomyk/eu-ai-act-check-action@v1   # EU AI Act compliance
```

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

### 🚀 GitHub Action — One-Line CI Security

Add AI agent security scanning to any repository in **one line**:

```yaml
# .github/workflows/agenticqa-scan.yml
name: AgenticQA Security Scan
on: [push, pull_request]
permissions:
  contents: read
  security-events: write

jobs:
  security-scan:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: nhomyk/AgenticQA@main
        with:
          path: '.'
          fail-on-critical: 'true'
          sarif: 'true'
```

**What you get for free:**
- **13-category security scan** across 6 languages (Python, TypeScript, JavaScript, Go, Rust, Java/Kotlin)
- **SARIF upload** — findings appear in GitHub's Code Scanning tab alongside CodeQL
- **PR auto-comments** — scan results posted directly to pull requests
- **Delta scans** — baseline caching shows what changed since last push
- **Security grade** — A+ through F benchmarked against major AI frameworks
- **Artifact upload** — full JSON report retained for 30 days

| Input | Default | Description |
|---|---|---|
| `path` | `.` | Repository path to scan |
| `fail-on-critical` | `true` | Fail workflow on critical findings |
| `sarif` | `false` | Generate SARIF for GitHub Code Scanning |
| `scanners` | `all` | Comma-separated scanner list |
| `pr-comment` | `true` | Post results as PR comment |
| `baseline` | *(auto)* | Previous scan JSON for delta comparison |

| Output | Description |
|---|---|
| `total-findings` | Total findings across all scanners |
| `critical-findings` | Critical finding count |
| `risk-level` | Overall risk: low/medium/high/critical |
| `security-grade` | Grade A+ through F |
| `security-percentile` | 0-100 vs benchmark frameworks |
| `detected-languages` | Comma-separated language list |

---

### 🔄 Concurrent Feature Request Pipeline — Ship Features Autonomously

Submit feature requests and AgenticQA generates, scans, tests, and commits the code — all in parallel via an isolated concurrent worker pool:

```bash
# Trigger via GitHub Actions workflow_dispatch
gh workflow run feature-request.yml \
  -f features='["Add health check endpoint", "Add input validation", "Add request logging"]'
```

**Architecture:**
- **WorkerPool** — configurable concurrent workers, each in an isolated git worktree
- **Atomic queue pickup** — `BEGIN IMMEDIATE` SQLite transactions prevent race conditions
- **Thread-safe store** — every DB method protected by `threading.Lock`
- **Per-worker orchestration** — each worker runs the full ADLC cycle independently:
  1. Pre-scan agents (SRE, QA, Performance) analyze the codebase
  2. LLM generates implementation code
  3. Security scan + test generation loop (SDET)
  4. Git commit to unique feature branch
  5. Workflow artifact generated at `.agenticqa/workflows/{id}.md`

```bash
# Check queue status
curl http://localhost:8000/api/workflow/queue-status
# → {"pending": 0, "in_progress": 2, "completed": 5, "failed": 0}

# Submit a feature request programmatically
curl -X POST http://localhost:8000/api/workflow/submit \
  -H "Content-Type: application/json" \
  -d '{"title": "Add OAuth support", "description": "Implement OAuth2 login flow"}'
```

**Lifecycle tracking:** `RECEIVED → PLANNED → APPROVED → QUEUED → IN_PROGRESS → COMPLETED`

Full audit trail with lifecycle events, branch names, commit SHAs, and worker assignments.

---

### ✅ Client Deployment Preflight — 7-Probe Readiness Check

Before running AgenticQA on any target repository, validate that the environment is properly configured:

```bash
python -m agenticqa.client_preflight --repo /path/to/client/repo
# ✅ git_repo          Repository is a valid git repo
# ✅ git_config        user.name and user.email configured
# ✅ python_tooling    Python 3.11.0, pip 24.0, pytest 8.0.0
# ✅ node_tooling      Not required (no package.json)
# ✅ linter_availability  flake8 available for Python
# ✅ path_sanitization    Path passes security validation
# ✅ import_chain         All core modules importable

# JSON output for CI integration
python -m agenticqa.client_preflight --repo . --json

# Strict mode — fail on warnings too
python -m agenticqa.client_preflight --repo . --fail-on-warning
```

| Probe | Checks | Fail/Warn |
|---|---|---|
| `git_repo` | Is it a git repo? | fail |
| `git_config` | user.name + user.email set? | fail |
| `python_tooling` | Python, pip, pytest available? | fail |
| `node_tooling` | If package.json: node/npm available? | warn |
| `linter_availability` | flake8/eslint per detected language? | warn |
| `path_sanitization` | Repo path passes `sanitize_repo_path()`? | fail |
| `import_chain` | `agenticqa.workflow_requests` loads? | fail |

Exit codes: `0` = healthy, `1` = critical failure, `2` = warnings only.

---

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

### 🔒 API Security Hardening — 3-Layer Middleware Stack

Every API request passes through three security middlewares before reaching any endpoint:

```bash
# Authenticated request (token auto-generated on first start, printed to stderr)
curl -H "Authorization: Bearer $AGENTICQA_AUTH_TOKEN" \
  http://localhost:8000/api/agents/execute -X POST -d '{...}'

# Health + docs endpoints bypass auth
curl http://localhost:8000/health  # always accessible
```

| Middleware | What It Does |
|---|---|
| **BearerTokenMiddleware** | Timing-safe `hmac.compare_digest` auth; auto-generates token if `AGENTICQA_AUTH_TOKEN` unset; skips `/health` and `/docs`; disable with `AGENTICQA_AUTH_DISABLE=1` |
| **OriginValidationMiddleware** | Localhost-only Origin header (DNS rebinding defense); no-Origin requests (curl, CI) always pass |
| **ResponseScanMiddleware** | Runs OutputScanner on every JSON response; soft mode adds warning header; `AGENTICQA_RESPONSE_SCAN_STRICT=1` blocks credential-leaking responses |

Additional hardening:
- CORS `allow_origins` locked to explicit localhost list (no more `*`)
- `/api/agents/execute` runs constitutional check (`_constitutional_check("run_agents")`) before dispatch
- Modelled after Docker's MCP-gateway defensive patterns

---

### 🛡️ Agent Safety Modules — Runtime Guardrails

Three independent safety modules that can be composed for defense-in-depth:

#### Destructive Action Interceptor
```bash
# Pre-flight check before any tool call
curl -X POST http://localhost:8000/api/safety/intercept \
  -d '{"tool": "rm", "args": ["-rf", "/data"], "agent": "sre_agent"}'
# → {"classification": "destructive", "requires_approval": true, "token": "abc123"}

# Human approves
curl -X POST http://localhost:8000/api/safety/approve/abc123
```

Classifies every tool call into 4 tiers: `safe → reversible → irreversible → destructive`. Destructive and irreversible actions require explicit human approval via token-based queue.

#### Agent Scope Lease Manager
```bash
curl -X POST http://localhost:8000/api/safety/lease \
  -d '{"agent": "sre_agent", "max_reads": 100, "max_writes": 10, "max_deletes": 0, "ttl_seconds": 300}'
# → {"lease_id": "lease-abc", "expires_at": "2026-03-01T15:05:00Z"}
```

Hard operation caps per agent: reads, writes, deletes, executes. `check_and_consume()` is a hard block — no soft warnings. Leases expire via TTL and can be revoked instantly.

#### Instruction Persistence Warden
```bash
curl -X POST http://localhost:8000/api/safety/warden/check \
  -d '{"agent": "compliance_agent", "context_usage_pct": 75}'
# → {"compaction_risk": "high", "constraint_drift": false,
#    "recommended_action": "re_inject", "guardrail_block": "..."}
```

Monitors context window compaction risk at 50%/75%/90% thresholds. Detects constraint drift (agent forgetting its guardrails). Recommends `continue | re_inject | pause | terminate`. Generates `GuardrailBlock` for re-injection into compacted contexts.

---

### 📦 AI Model SBOM — Software Bill of Materials for AI

Automatically discovers every AI model dependency in your codebase and flags licensing and deprecation risks:

```bash
curl "http://localhost:8000/api/compliance/ai-model-sbom?repo_path=."
# → {"models_found": 4, "total_findings": 2, "findings": [
#     {"rule_id": "RESTRICTED_LICENSE", "severity": "high",
#      "file": "src/model.py", "line": 12,
#      "message": "Model 'meta-llama/Llama-2-7b' uses a restricted license (Llama 2 Community)"}]}
```

| Detection | Coverage |
|---|---|
| **Import patterns** | 25+ provider patterns: OpenAI, Anthropic, Google, HuggingFace, Cohere, Replicate, Meta, Mistral, etc. |
| **Model ID extraction** | `from_pretrained()`, `model=`, `GenerativeModel()`, pipeline strings |
| **License registry** | 50+ models with known license classifications |

| Finding | Severity | What It Flags |
|---|---|---|
| `UNKNOWN_LICENSE` | high | Model used without a known license classification |
| `RESTRICTED_LICENSE` | high | Model with non-commercial or restricted license terms |
| `EXTERNAL_API` | medium | External API call to model provider (data egress risk) |
| `DEPRECATED_MODEL` | medium | Model version known to be deprecated |
| `UNVERSIONED_MODEL` | medium | Model reference without pinned version |

---

### 🕸️ Multi-Agent Trust Graph — Framework-Aware Analysis

Detects multi-agent architectures across **14+ frameworks** and flags trust, delegation, and human oversight violations:

```bash
curl "http://localhost:8000/api/redteam/agent-trust-graph?repo_path=."
# → {"frameworks_detected": ["langchain", "crewai"], "agents_found": 5,
#    "total_findings": 3, "findings": [
#     {"rule_id": "CIRCULAR_TRUST", "severity": "critical",
#      "message": "Circular delegation chain detected: agent_a → agent_b → agent_a"},
#     {"rule_id": "MISSING_HUMAN_IN_LOOP", "severity": "high",
#      "message": "No human override mechanism found — EU AI Act Art.14 violation"}]}
```

| Frameworks Detected |
|---|
| LangGraph, CrewAI, AutoGen, LangChain, Swarm, Semantic Kernel, Haystack, DSPy, ControlFlow, BabyAGI, MetaGPT, CAMEL, TaskWeaver, OpenAI Assistants |

| Finding | Severity | What It Detects |
|---|---|---|
| `CIRCULAR_TRUST` | critical | DFS cycle detection in delegation graph |
| `MISSING_HUMAN_IN_LOOP` | critical | No `require_human_review`, override, or approval mechanism — EU AI Act Art.14 evidence gap |
| `UNCONSTRAINED_DELEGATION` | high | Agent can delegate to any other agent without scope limits |
| `PRIVILEGED_TOOL_ACCESS` | high | Agent has access to destructive tools (file delete, shell exec, DB drop) |
| `ESCALATION_PATH` | medium | Delegation chain reaches a more-privileged agent without approval gate |

---

### 🌍 MCP Scanner — Multi-Language Security Analysis

The MCP (Model Context Protocol) scanner now analyzes codebases in **6 languages**, detecting credential leaks, injection risks, and data flow violations:

```bash
# Scan a Go/Rust/Java project
python -m agenticqa.security.mcp_scanner --repo /path/to/project
# → {"files_scanned": 63, "risk_score": 1.0, "findings": [
#     {"file": "interceptors.go", "pattern": "log.Logf credential",
#      "severity": "high", "language": "go"}]}
```

| Language | File Discovery | Key Patterns |
|---|---|---|
| **Python** | `*.py` | f-string secrets, `os.environ` in prompts, `eval()`/`exec()` |
| **TypeScript/JavaScript** | `*.ts`, `*.js`, `*.tsx`, `*.jsx` | template literal injection, `process.env` exposure, `innerHTML` |
| **Go** | `*.go` | `os.Getenv()` in prompts, `log.Logf` credential leaks, `/bin/sh -c` injection, `os.Environ()` |
| **Rust** | `*.rs` | `std::env::var` exposure, unsafe blocks with user input, `Command::new` injection |
| **Java/Kotlin** | `*.java`, `*.kt` | `System.getenv()` in prompts, `Runtime.exec()`, JDBC connection strings |
| **Swift** | `*.swift` | `ProcessInfo.processInfo.environment` exposure |

Data flow tracer follows source → transform → sink paths across function boundaries. Skip directories: `vendor` (Go), `target` (Rust), `.gradle`/`.mvn` (Java).

---

### 🔧 TypeScript/JavaScript SRE — Full Linter Support

The SRE agent now supports TypeScript and JavaScript projects with the same auto-fix capabilities as Python:

```python
sre.execute({
    "language": "typescript",
    "file_path": "src/app.ts",
    "errors": [{"rule": "no-var", "line": 5, "message": "Unexpected var, use let or const"}]
})
# → {"fixes_applied": 3, "fix_rate": 0.75, "architectural_violations": 1}
```

**Linter detection priority:** oxlint (via pnpm `node_modules`) → system oxlint → ESLint fallback. Auto-detects TypeScript when `tsconfig.json` is present or `language` starts with `ts`.

**30+ auto-fix rules:** `no-var`, `prefer-const`, `unicorn/*`, `typescript/*`, `@typescript-eslint/*`, and more.

**Architectural rules** (excluded from fix rate — intentional design choices):
`typescript/no-explicit-any`, `@typescript-eslint/no-explicit-any`, `no-shadow`, `complexity`, `oxc/no-accumulating-spread`, `import/no-cycle`

Supports both oxlint `{"diagnostics":[...]}` and flat-array ESLint JSON formats. Rule objects like `{"name":"no-var","plugin":"eslint"}` are normalized automatically.

---

### 🌐 Minimal AI Landing Page — Bridges Non-Technical and Technical Users

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
| **Security** | 8 sweeps: Legal Risk · HIPAA · EU AI Act · Prompt Injection · CVE Reachability · AI Model SBOM · Agent Trust Graph · MCP Scanner |
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
  Natural-language prompt / CI trigger / GitHub Action
         │
         ▼
  ┌─────────────────────────────────────────────────────┐
  │  API Security Middleware (3 layers)                   │
  │  Bearer auth · Origin validation · Response scanning │
  └─────────────────────────────────────────────────────┘
         │
         ▼
  ┌─────────────────────────────────────────────────────┐
  │  ConstitutionalGate + OutputScanner (Red Team)       │
  │  pre-action ALLOW/DENY · 4-pass decode · <5ms        │
  └─────────────────────────────────────────────────────┘
         │
         ▼
  ┌─────────────────────────────────────────────────────┐
  │  Agent Safety Modules                                │
  │  DestructiveActionInterceptor · ScopeLeaseManager    │
  │  InstructionPersistenceWarden · approval queue        │
  └─────────────────────────────────────────────────────┘
         │
    ┌────┴──────────────────────────────────────┐
    ▼            ▼            ▼            ▼
  SDET         QA        Fullstack     RedTeam
  Agent       Agent       Agent        Agent
    │                                    │
 delegates                          Adversarial probes
    ▼                              + trust graph analysis
   SRE    ←──── Self-Healing ────────────┘
  Agent     CI Repair (Python + TS/JS)
    │
    ▼
  Compliance  ── Legal · HIPAA · EU AI Act · SBOM ──▶ violations[]
  Agent           provenance + regression + trust graph
    │
    ▼
  DevOps   Performance
  Agent      Agent
         │
         ▼
  ┌──────────────────────────────────────────────┐
  │  Hybrid RAG Layer                             │
  │  Qdrant (primary) · Neo4j (graph) · SQLite   │
  │  Model Regression · Output Provenance         │
  │  Learning Metrics · Developer Profiles        │
  │  Org Memory · Repo Profiles                   │
  └──────────────────────────────────────────────┘
         │
         ▼
  ┌──────────────────────────────────────────────┐
  │  Concurrent Feature Request Pipeline          │
  │  WorkerPool · git worktree isolation          │
  │  Atomic SQLite pickup · thread-safe store     │
  └──────────────────────────────────────────────┘
         │
         ▼
  SARIF → GitHub Code Scanning + PR Comment + Security Grade
```

---

## The ADLC Cycle — What Each Phase Does

| Phase | Agent(s) | What Happens | Feeds Back Into |
|---|---|---|---|
| **1. Describe** | *(user)* | Feature described in plain English via landing page | Feature → code prompt |
| **2. Generate** | Fullstack + LLM | UI code generated, written to repo | Security scan input |
| **3. Scan** | ComplianceAgent + ArchitectureScanner | 13-category security sweep across 6 languages; context-aware severity | Verdict gate |
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
| **GitHub Action** | One-line CI integration with SARIF, PR comments, delta scans, security grades | Add to any repo in 30 seconds |
| **Concurrent Pipeline** | WorkerPool with git worktree isolation, atomic SQLite pickup, thread-safe store | 3+ features built in parallel |
| **API Security** | 3-layer middleware: bearer auth, origin validation, response scanning | Zero credential leaks in responses |
| **Agent Safety** | Destructive action interception, scope leasing, instruction persistence warden | Hard caps on agent operations |
| **AI Model SBOM** | 25+ provider patterns, 50+ model license registry, 5 finding types | Every AI dependency catalogued |
| **Trust Graph** | 14+ multi-agent frameworks, DFS cycle detection, EU AI Act Art.14 evidence | Circular delegation blocked |
| **MCP Multi-Language** | Go/Rust/Java/Kotlin/Swift scanning alongside Python/TS/JS | 6 languages, unified risk score |
| **Client Preflight** | 7-probe deployment readiness check with CLI | Catches CI failures before they happen |

---

## 16-Page Analytics Dashboard

```bash
streamlit run dashboard/app.py
```

| Page | What It Shows |
|---|---|
| **Operator Console** | Prompt intake → approve → queue → execute → replay. Trace explorer with timeline, audit report generator. Feature request pipeline status |
| **Governance** | Agent Constitution viewer, interactive pre-action check simulator, Agent Scopes browser |
| **System Overview** | Stack anatomy, framework matrix, test coverage, live agent metrics |
| **Collaboration** | Interactive delegation network graph + chain traces |
| **Performance** | Bottleneck detection, latency trends, per-agent health scores |
| **GraphRAG** | Hybrid RAG architecture diagram + live recommendation engine |
| **Ontology** | Design-vs-reality — intended paths vs. actual delegation usage |
| **Pipeline** | Data flow, 7-layer security architecture, API connectivity tester |
| **Red Team** | Mode/target/auto_patch controls · scanner + gate strength gauges · vulnerability table · prompt injection findings · trust graph visualization |
| **Agent Learning** | Developer risk chart · org memory panel · compliance drift · repo fix rate · learning metrics · temporal graphs |
| **Onboarding** | Architecture · Security · Coverage · Generated Tests · Baseline Delta tabs |
| **Compliance Scan** | Legal Risk · HIPAA · EU AI Act · CVE Reachability · AI Model SBOM · trust graph findings |
| **Architecture Scan** | Import graph · HTTP exposure · ENV secrets · attack surface score · 13 categories · 6 languages |
| **Agent Safety** | Destructive action approval queue · scope lease creator · instruction persistence warden · interceptor simulator |
| **Release Readiness** | Pre-flight risk score · dev profiles · org memory · violation predictions |
| **Agent Factory** | Natural-language agent builder · spec preview · scaffold viewer |

---

## Quick Start

### Add to any repo (GitHub Action)

```yaml
# .github/workflows/agenticqa-scan.yml
- uses: nhomyk/AgenticQA@main
  with:
    sarif: 'true'
```

That's it. SARIF findings appear in GitHub Code Scanning. PR comments post automatically.

### Run locally

```bash
git clone https://github.com/nhomyk/AgenticQA.git
cd AgenticQA
pip install -e .

# Start infrastructure (optional — most features work without it)
docker compose -f docker-compose.weaviate.yml up -d

# Run 2308+ unit tests
pytest tests/ -m unit -v

# Launch control plane
uvicorn agent_api:app --host 0.0.0.0 --port 8000

# Open landing page (no API key needed)
open http://localhost:8000

# Run full client demo
python run_demo.py

# Launch dashboard
streamlit run dashboard/app.py

# Run deployment preflight on any target repo
python -m agenticqa.client_preflight --repo /path/to/repo
```

### Onboard any repo in 3 commands

```bash
agenticqa bootstrap --repo .          # generate CI wiring + config
agenticqa ingest-junit results.xml    # convert existing test output
agenticqa doctor --repo .             # readiness check with fix commands
```

---

## Core API (140+ endpoints)

**Governance**
- `GET  /api/system/constitution` — machine-readable law set
- `POST /api/system/constitution/check` — pre-action check: `ALLOW / REQUIRE_APPROVAL / DENY`
- `GET  /api/system/agent-scopes` — per-agent file access scopes (8 agents)
- `POST /api/system/agent-scopes/check` — scope check for agent × action × file path

**Compliance & Regulatory Scanning**
- `GET  /api/compliance/legal-risk` — credentials, PII docs, privilege breach, SSRF, missing auth
- `GET  /api/compliance/hipaa` — PHI_HARDCODED, PHI_TO_LLM, PHI_IN_LOGS, HIPAA_AUDIT_MISSING
- `GET  /api/compliance/ai-act` — EU AI Act Annex III classification + Art.9/13/14/22 conformity score
- `GET  /api/compliance/ai-model-sbom` — AI model SBOM: 25+ providers, license registry, 5 finding types

**Security & Adversarial**
- `POST /api/red-team/scan` — adversarial scan (mode: fast|thorough, target: scanner|gate|both, auto_patch: bool)
- `GET  /api/redteam/prompt-injection` — static prompt injection surface scan (4 rules, SARIF-native)
- `GET  /api/redteam/agent-trust-graph` — multi-agent trust graph analysis (14+ frameworks, cycle detection)
- `POST /api/export/sarif` — convert agent results to SARIF 2.1.0 for GitHub Code Scanning
- `GET  /api/security/cve-reachability` — import-level AST + pip-audit/npm-audit CVE analysis

**AI Output Provenance**
- `GET  /api/provenance/verify` — verify output hash against signed provenance log
- `GET  /api/provenance/chain` — last N provenance records for an agent

**Model Regression**
- `GET  /api/regression/compare` — cosine similarity between baseline and candidate model outputs

**Agent Safety**
- `POST /api/safety/intercept` — pre-classify tool call (safe/reversible/irreversible/destructive)
- `GET  /api/safety/pending` — list pending approval requests
- `POST /api/safety/approve/{token}` — approve destructive action by token
- `POST /api/safety/deny/{token}` — deny destructive action by token
- `POST /api/safety/lease` — create agent scope lease (read/write/delete/execute caps + TTL)
- `GET  /api/safety/lease/{id}` — get lease status
- `DELETE /api/safety/lease/{id}` — revoke lease
- `POST /api/safety/warden/register` — register agent guardrails for persistence monitoring
- `POST /api/safety/warden/check` — check compaction risk + constraint drift
- `GET  /api/safety/warden/prompt` — generate guardrail re-injection block

**Feature Request Pipeline**
- `POST /api/workflow/submit` — submit feature request to queue
- `GET  /api/workflow/queue-status` — pending/in_progress/completed/failed counts
- `GET  /api/workflow/request/{id}` — get request details + lifecycle events
- `GET  /api/workflow/requests` — list all requests with filters

**Observability & Auditing**
- `GET  /api/observability/traces/{id}/audit-report` — forensic compliance artifact with stable audit ID
- `GET  /api/observability/traces/{id}/counterfactuals` — "what should the agent have done?" analysis
- `GET  /api/health/dataflow` — ontology-aware infra health; 503 on critical failure
- `GET  /api/temporal/violations` — temporal violation graph snapshots from Neo4j
- `GET  /api/learning-metrics` — learning metrics history + improvement curves
- `GET  /api/developer-profiles` — per-developer EWMA risk profiles via git blame
- `GET  /api/org-memory` — cross-repo organizational memory and unfixable rules
- `GET  /api/repo-profile` — per-repo EWMA fix rates and run history

**Agent Factory**
- `POST /api/agent-factory/from-prompt` — natural-language description → scaffold → persisted agent

**GitHub Integration**
- `POST /api/github/pr-comment` — post scan results as PR comment (upsert via `--edit-last`)
- `POST /api/github/pr-inline-comments` — post inline review comments with severity icons

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
  │  0. API Security Middleware (3 layers)                    │
  │     BearerToken auth · Origin validation · Response scan │
  ├──────────────────────────────────────────────────────────┤
  │  0b. Constitutional Gate                                 │
  │     pre-action ALLOW/DENY · 6 Tier 1 laws · agent scopes│
  ├──────────────────────────────────────────────────────────┤
  │  0c. OutputScanner (Red Team hardened)                   │
  │     4-pass decode: raw → NFKC → base64 → URL            │
  │     13 danger patterns + learned bypass patterns         │
  ├──────────────────────────────────────────────────────────┤
  │  0d. Agent Safety Modules                                │
  │     DestructiveActionInterceptor · ScopeLeaseManager     │
  │     InstructionPersistenceWarden · token-based approval  │
  ├──────────────────────────────────────────────────────────┤
  │  0e. Static Security Scanners (ComplianceAgent)          │
  │     Legal Risk · HIPAA PHI · Prompt Injection · EU AI Act│
  │     AI Model SBOM · Agent Trust Graph · CVE Reachability │
  │     MCP Scanner (6 languages) · 30+ SARIF rules          │
  ├──────────────────────────────────────────────────────────┤
  │  0f. AI Output Provenance                                │
  │     HMAC-SHA256 sign · tamper detection · chain of custody│
  ├──────────────────────────────────────────────────────────┤
  │  1. CI/CD Pipeline Gate (16 jobs + GitHub Action)        │
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
| **API Security** | BearerTokenMiddleware · OriginValidationMiddleware · ResponseScanMiddleware · CORS lockdown |
| **Agent Safety** | DestructiveActionInterceptor · AgentScopeLeaseManager · InstructionPersistenceWarden |
| **Adversarial Hardening** | RedTeamAgent · AdversarialGenerator · PatternPatcher · OutputScanner (4-pass) |
| **Prompt Injection** | PromptInjectionScanner (4 rules) · SARIF PROMPT_INJECTION_SURFACE=9.5 |
| **Legal & HIPAA** | LegalRiskScanner · HIPAAPHIScanner · SARIF-native · pure-Python |
| **EU AI Act** | AIActComplianceChecker · Annex III classifier · Art.9/13/14/22 checks |
| **AI Model SBOM** | AIModelSBOMScanner · 25+ provider patterns · 50+ model license registry |
| **Trust Graph** | AgentTrustGraphAnalyzer · 14+ frameworks · DFS cycle detection · EU AI Act Art.14 |
| **MCP Scanner** | MCPScanner · DataFlowTracer · 6 languages (Python/TS/JS/Go/Rust/Java) |
| **AI Output Provenance** | OutputProvenanceLogger · HMAC-SHA256 · JSONL chain · verify API |
| **Model Regression** | ModelRegressionTester · GoldenSnapshot · fastembed → TF-IDF cosine fallback |
| **Agent Factory** | NaturalLanguageSpecExtractor · Claude Haiku (spec extraction) · scaffold generator |
| **Feature Pipeline** | WorkerPool · git worktree isolation · atomic SQLite pickup · thread-safe store |
| **Self-Healing CI** | SREAgent._attempt_test_repair · SubprocessRunner sandbox · Haiku-generated patches |
| **TypeScript SRE** | oxlint/ESLint auto-detect · 30+ fix rules · architectural rule exclusions |
| **Infra Health** | DataflowHealthMonitor · ontology-aware probes · Weaviate version detection |
| **Client Preflight** | 7-probe deployment readiness · CLI with JSON output · CI integration |
| **Security Output** | SARIFExporter · SARIF 2.1.0 · GitHub Code Scanning · 30+ severity mappings |
| **Shell Linting** | shellcheck (SC codes) · SREAgent._run_shell_linter |
| **Vector DB** | Qdrant (primary) / Weaviate 1.27.0+ (secondary) |
| **Graph DB** | Neo4j |
| **Relational DB** | SQLite / PostgreSQL |
| **Embeddings** | fastembed (local) / Sentence-Transformers |
| **API** | FastAPI + Pydantic (140+ endpoints) |
| **Dashboard** | Streamlit + Plotly (16 pages) |
| **CI/CD** | GitHub Actions (16 jobs + GitHub Action marketplace, SARIF upload, nightly self-validation) |
| **GitHub Action** | Composite action: one-line CI, SARIF, PR comments, delta scans, security grades |
| **Testing** | Pytest (2308+ unit/integration tests, 6 e2e pipeline tests) |
| **Language** | Python 3.8+ |
| **Landing Page** | Vanilla HTML/CSS/JS · animated CSS grid · futuristic dark minimal UI |
| **Frontend Testing** | Streamlit AppTest · Jest · Vitest · FrontendTestGenerator · FrontendTestRunner |
| **Repo Onboarding** | CoverageMapper · ArchitectureScanner · RepoOnboarder · BaselineDelta |
| **GitHub Integration** | PR comments (upsert) · inline review comments · SARIF upload · artifact caching |

---

## Project Structure

```
AgenticQA/
├── action.yml                   # GitHub Action — one-line CI for any repo (SARIF, PR comments, grades)
├── public/                      # Landing page (served at GET /)
│   └── index.html               # Futuristic dark minimal AI input UI
├── run_demo.py                  # 8-step end-to-end client demo (no API key needed)
├── src/agenticqa/
│   ├── constitution.yaml        # Agent Constitution — versioned, machine-readable law set
│   ├── agent_scopes.yaml        # Per-agent file access scopes (8 agents)
│   ├── constitutional_gate.py   # Pre-action enforcement: ALLOW / REQUIRE_APPROVAL / DENY
│   ├── audit_report.py          # Forensic compliance artifact builder (PR-embeddable)
│   ├── observability.py         # SQLite store: complexity tracking, anomaly detection
│   ├── workflow_requests.py     # Thread-safe PromptWorkflowStore (atomic pickup, full locking)
│   ├── workflow_worker.py       # WorkerPool + WorkflowExecutionWorker (git worktree isolation)
│   ├── client_preflight.py      # 7-probe deployment readiness check + CLI
│   ├── security/                # LegalRiskScanner · HIPAAPHIScanner · PromptInjectionScanner · CVEReachability
│   │   ├── ai_model_sbom.py     #   AI Model SBOM: 25+ provider patterns, license registry
│   │   ├── agent_trust_graph.py #   Multi-agent trust graph: 14+ frameworks, cycle detection
│   │   ├── mcp_scanner.py       #   MCP Scanner: 6 languages (Python/TS/JS/Go/Rust/Java)
│   │   ├── api_middleware.py    #   3-layer API security: bearer auth, origin, response scan
│   │   ├── destructive_action_interceptor.py  # Tool call classification + approval queue
│   │   ├── scope_lease_manager.py             # Hard op caps per agent with TTL
│   │   ├── instruction_persistence_warden.py  # Context compaction risk + drift detection
│   │   └── path_sanitizer.py    #   Path security with GITHUB_WORKSPACE support
│   ├── compliance/              # AIActComplianceChecker (EU AI Act) · ComplianceDriftDetector
│   ├── provenance/              # OutputProvenanceLogger · HMAC-SHA256 signing · verify API
│   ├── regression/              # ModelRegressionTester · GoldenSnapshot · cosine similarity
│   ├── verification/            # Feedback loop, outcome tracker, threshold calibrator, strategy selector
│   ├── graph/                   # Neo4j: delegation store, GraphRAG, temporal violation store
│   ├── rag/                     # Weaviate/Qdrant: vector retrieval, reranking
│   ├── collaboration/           # Agent delegation, registry, guardrails
│   ├── redteam/                 # AdversarialGenerator (20 techniques) · PatternPatcher
│   ├── factory/                 # NaturalLanguageSpecExtractor · agent scaffold generator
│   │   └── sandbox/             # SubprocessRunner · OutputScanner (4-pass decode)
│   ├── monitoring/              # DataflowHealthMonitor · 5 probes · ontology-aware impact
│   ├── onboarding/              # CoverageMapper · RepoOnboarder · BaselineDelta
│   ├── testing/                 # FrontendTestGenerator · FrontendTestRunner (Streamlit/Jest/Vitest)
│   ├── export/                  # SARIFExporter · SARIF 2.1.0 · 30+ severity mappings
│   ├── github/                  # PR commenter (upsert) · inline review comments
│   └── cli.py                   # CLI: bootstrap, doctor, ingest-junit, preflight
├── dashboard/                   # 16-page Streamlit analytics dashboard
├── agent_api.py                 # FastAPI control plane (140+ endpoints, 3-layer security middleware)
├── src/agents.py                # 8 agents: QA, Performance, Compliance, DevOps, SRE, SDET, Fullstack, RedTeam
├── src/data_store/              # PatternAnalyzer, LearningMetrics, RepoProfile, DeveloperProfile, OrgMemory
├── ingest_ci_artifacts.py       # CI data bridge — ESLint, red-team, migration → learning system
├── scripts/                     # github_action_entrypoint.py, post_pr_comment.py, run_custom_agents.py
├── tests/                       # 2308+ tests — unit, integration, e2e pipeline, preflight
│   ├── test_e2e_full_pipeline.py  # 6 e2e integration tests (real SQLite, real WorkerPool, real git)
│   └── test_client_preflight.py   # 17 unit tests for deployment readiness
└── .github/workflows/           # 16-job CI pipeline + feature-request pipeline + nightly self-validation
```

---

## License

MIT
