# Changelog

All notable changes to AgenticQA are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.0.0] - 2026-03-01

### Added

#### Production Infrastructure
- **Dockerfile** — multi-stage Python 3.11 build, non-root user, healthcheck
- **docker-compose.prod.yml** — one-command production stack (API + Qdrant + Neo4j + optional dashboard)
- **Python Client SDK** — `AgenticQAClient` with typed responses, auth support, and all 13 scanner methods
- **API versioning** — `/api/v1/*` prefix (backwards-compatible, `/api/*` still works)
- **Standardized error responses** — `{error: {code, message, request_id, status}}` on all errors
- **OWASP security headers** — CSP, HSTS, X-Frame-Options, X-Content-Type-Options, Referrer-Policy

#### Security Scanners (13 total)
- **Architecture Scanner** — attack surface analysis (env secrets, shell exec, HTTP calls, DB access, file I/O)
- **Legal Risk Scanner** — credential exposure, SSRF risks, missing auth
- **CVE Reachability** — pip-audit/npm-audit integration with import-level AST analysis
- **HIPAA PHI Scanner** — hardcoded PHI, PHI in logs, missing audit controls
- **AI Model SBOM** — 25+ provider patterns, 50+ model license registry, deprecated model detection
- **EU AI Act Compliance** — Annex III classification, Art.9/13/14/22 conformity scoring
- **Agent Trust Graph** — 14 framework detection, cycle detection, missing human-in-loop
- **Prompt Injection Scanner** — direct concat, template injection, unsafe output, role override
- **MCP Security Scanner** — Go/Rust/Java/Kotlin support, 63+ file types
- **Cross-Agent Data Flow Tracer** — credential flow to untrusted sinks
- **Shadow AI Detector** — unapproved models, unauthorized provider imports, AI env vars
- **Bias Detector** — 6 protected attribute categories, decision context analysis, stereotyping patterns
- **Indirect Injection Guard** — 5-pass decode (raw/NFKC/unicode/base64/URL), RAG pipeline safety

#### Safety Modules
- **Destructive Action Interceptor** — pre-execution classification (safe/reversible/irreversible/destructive)
- **Agent Scope Lease Manager** — hard op caps (reads/writes/deletes/executes) with TTL
- **Instruction Persistence Warden** — compaction risk detection, guardrail re-injection
- **PII Redactor** — 10 PII pattern types, recursive dict/list scanning
- **Cost Tracker** — per-model pricing, quota enforcement, circuit breakers
- **AI Output Provenance** — HMAC-SHA256 signing and verification chain

#### API Security
- **Bearer token authentication** — timing-safe `hmac.compare_digest`, auto-generated tokens
- **Origin validation** — DNS rebinding defence, localhost-only
- **Response secret scanning** — OutputScanner on all JSON responses
- **Rate limiting** — 60 req/min per token, 15 for heavy endpoints
- **Input size limits** — 512 KB body, depth-20 JSON nesting
- **Path sanitization** — CWE-22 directory traversal defence
- **Token budget guard** — sponge attack detection

#### Agents (8)
- QA Agent — test execution and coverage analysis
- Performance Agent — regression detection with baseline comparison
- Compliance Agent — data encryption, PII protection, legal/regulatory
- DevOps Agent — CI/CD pipeline validation
- SRE Agent — auto-fix linting errors (Python flake8 + TypeScript oxlint/eslint), self-healing CI
- SDET Agent — coverage gap detection, LLM-generated tests
- Fullstack Agent — JS/TS agent stub
- Red Team Agent — adversarial testing (20 bypass techniques), auto-patching

#### ML Learning Loop
- Closed feedback loop with doc-level boost/penalize/rerank
- Adaptive thresholds via ThresholdCalibrator
- Pattern-driven execution strategies
- GraphRAG-informed delegation via Neo4j
- Adaptive strategy selection (aggressive/standard/conservative)

#### Infrastructure
- Qdrant (primary vector store) + Weaviate (secondary) dual-write
- Neo4j for delegation graphs and temporal violation tracking
- Agent Factory — natural language to governed agent scaffolding
- GitHub PR inline review comments with severity icons
- Cross-repo organizational memory with EWMA fix rates

### Benchmark Results
- Scanned 11 major AI agent frameworks (LangChain, AutoGPT, CrewAI, LlamaIndex, etc.)
- **52,724 findings** including **1,339 critical** across 16,662 files
- **8,438 AI-specific findings** that Snyk/Semgrep/Checkmarx cannot detect
- Every repo classified as EU AI Act high-risk under Annex III
- Full scan of all 11 repos completed in 273 seconds

## [0.1.0] - 2026-01-15

### Added
- Initial release with QA, Performance, Compliance, and DevOps agents
- Weaviate RAG integration
- Streamlit dashboard
- Basic CI/CD pipeline
