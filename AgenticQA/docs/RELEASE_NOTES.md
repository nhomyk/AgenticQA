# AgenticQA Release Notes

Chronological changelog of significant additions. Each entry includes a "Medium angle" for potential articles.

---

## v1.6 — SARIF Export + Shellcheck Integration
**Commit:** `9cfe5be` | **Date:** 2026-02-25

### What Shipped
- **`SARIFExporter`** (`src/agenticqa/export/sarif.py`) — converts SRE, Compliance, and Red Team findings to SARIF 2.1.0 for GitHub Code Scanning. Security-severity scores mapped per rule: `B602` = 9.5, `SC2086` = 5.0, `reachable_cve` = 9.0. Uploaded via `github/codeql-action/upload-sarif@v3` on every push.
- **Shellcheck integration** in `SREAgent._run_shell_linter()` — runs `shellcheck --format=json` across all `.sh` files; SC codes normalized to AgenticQA rule format; `SC2046`/`SC2206`/`SC2207` added to `ARCHITECTURAL_RULES` (non-fixable by design); `SC2086`/`SC2046`/`SC2006` added to `_SC_SECURITY` class attribute.
- **`POST /api/export/sarif`** endpoint — accepts `{sre, compliance, redteam, repo_root}`, returns SARIF JSON inline.
- **25 new unit tests** (`test_sarif_export.py`, `test_shellcheck_sre.py`); 531 total passing.
- CI `sre-agent` job: shellcheck step → SARIF export step → `upload-sarif@v3` step.

### Why It Matters
Before this, AgenticQA findings lived only inside the platform. Now they surface in the **GitHub Security tab** alongside CodeQL — the same UI security teams already use. Shell scripts were a blind spot in every SRE agent: they don't carry Python type annotations, have no linters in most CI pipelines, and contain real injection risks (unquoted variables, backtick expansion). Connecting shellcheck output to SARIF security-severity means a `rm -rf $UNQUOTED_VAR` shows up as a red finding in Code Scanning, not just a log line.

### Medium Angle
**"Your CI Pipeline Has a Shell Script Problem. Here's How We Fixed It With SARIF."**
Angle: most teams think of static analysis as a Python/Java/Go thing. Shell scripts — the glue of every CI pipeline — are an afterthought. This article walks through adding shellcheck to an agentic CI platform, mapping SC codes to CVSS-like severity scores, and surfacing the results in GitHub Code Scanning without any GitHub App or extra credentials. The punchline: `SC2086` in a deploy script is a word-splitting bug that can be a remote code execution vector if the variable is attacker-controlled.

---

## v1.5 — DataflowHealthMonitor + Weaviate → Qdrant Migration
**Commit:** `02bd32f` | **Date:** 2026-02-24

### What Shipped
- **`DataflowHealthMonitor`** (`src/agenticqa/monitoring/dataflow_health.py`) — 5 infrastructure probes (qdrant, weaviate, neo4j, artifact_store, learning_metrics); reads Task-Agent Ontology to report which specific agents are degraded when a node fails; Weaviate version check flags < 1.27.0 as critical with "RAG writes will be silently discarded" message.
- **`GET /api/health/dataflow`** endpoint — returns `{healthy, broken_nodes, affected_agents, degraded_agents}`; 503 on critical failure.
- **Qdrant promoted to primary vector store** — migrated 786 vector documents from Weaviate 1.24.8 to Qdrant v1.9.0; parity check confirms zero missing records; `AGENTICQA_VECTOR_PROVIDER=qdrant` in CI.
- **Weaviate upgraded 1.24.8 → 1.27.0** — required wiping stale raft cluster state volume; now runs as secondary/fallback.
- **15 unit tests** (`test_dataflow_health.py`); all using injected probe functions, no real infrastructure needed.

### Why It Matters
Weaviate 1.24.8 silently discarded every RAG write because the Python client v4 requires ≥ 1.27.0. The failure produced **no errors, no warnings, no logs** — just zero retrieval hits and degraded agent decision quality. This is the category of failure that kills production AI systems: the data loss is invisible until someone notices the agents are less accurate. The DataflowHealthMonitor was built specifically to catch this class of failure — it doesn't just check "is the server up" but "is the version compatible with the agents that depend on it."

The ontology-aware aspect is genuinely novel: when Neo4j goes down, the monitor knows that SRE_Agent and Performance_Agent are unaffected (they don't use graph traversal), while Compliance_Agent and SDET_Agent are degraded. No other health monitoring system knows which agents depend on which infra components because no other system has a machine-readable Task-Agent Ontology.

### Medium Angle
**"The Silent Data Loss Bug That Took Down Our RAG Layer (And the Monitor We Built to Catch It)"**
Angle: walk through the Weaviate 1.24.8 → 1.27.0 breaking change, explain why it produces zero errors (the Python client connected successfully but discarded writes at the serialization layer), describe discovering the issue via zero retrieval hits, and introduce the DataflowHealthMonitor as the architectural solution. Include the Weaviate version check code and the ontology-to-infra mapping. This is a cautionary tale for anyone running multi-agent platforms with a vector DB.

---

## v1.4 — Five Platform Features
**Commits:** (plan features) | **Date:** 2026-02-20–24

### What Shipped
- **Dependency CVE Reachability** (`src/agenticqa/security/cve_reachability.py`) — `CVEReachabilityAnalyzer` runs `pip-audit` + `npm audit`, extracts Python `import` statements via AST walk and JS `require`/`import` via regex, cross-references vulnerable packages with actual code imports to determine reachability. `risk_score` (0.0–1.0) weighted by severity of *reachable* CVEs only. Integrated into `ComplianceAgent.execute()`.
- **Developer Risk Profiles** (`src/data_store/developer_profile.py`) — per-developer EWMA fix rate tracking stored at `~/.agenticqa/developers/{repo_id}/{dev_hash}.json`; `DeveloperRiskLeaderboard.top_n()` ranks by risk score; `SREAgent` records violation/fix outcome per file author via `git blame`. Dashboard "Agent Learning" page shows risk heatmap.
- **Custom Agent CI Activation** (`run_custom_agents.py`) — discovers `.agenticqa/custom_agents/*.py`, loads each module, calls `run(context)`, captures output, ingests to artifact store. New `custom-agents` CI job runs opt-in custom logic in every pipeline.
- **LLM-Generated Tests** (`SDETAgent._generate_tests_for_gap()`) — Haiku generates pytest files for high-priority coverage gaps; `compile()` gate rejects syntax errors; `pytest --collect-only` gate rejects uncollectable tests; atomic write to `.agenticqa/generated_tests/`; `GET /api/sdet/generated-tests` lists all generated files.
- **GitHub PR Comments** (`src/agenticqa/github/pr_commenter.py`, `post_pr_comment.py`) — `PRCommenter.post_results()` formats a markdown summary of all 8 agent results and upserts (not duplicates) a comment on the triggering PR; new `post-pr-comment` CI job runs after all agent jobs on `pull_request` events.

### Medium Angle
**"We Taught Our CI Pipeline to Comment on Its Own Pull Requests"**
Angle: every CI system tells you *that* tests passed. AgenticQA's post-pr-comment job tells you the QA agent found 3 failing tests, the SDET agent generated 2 new test files for uncovered critical paths, the SRE agent fixed 14 linting errors at 89% fix rate, and the Red Team agent found 0 bypasses. All in a single PR comment that updates itself on re-run. Walk through the upsert logic, the Markdown table rendering, and why formatting CI intelligence as a PR comment is better than a separate dashboard for developer adoption.

---

## v1.3 — Agent Factory + CI Data Ingestion
**Commit:** `33a9cf3`, `e7a2d8e` | **Date:** 2026-02-18

### What Shipped
- **Agent Factory** (`src/agenticqa/factory/spec_extractor.py`) — `NaturalLanguageSpecExtractor` uses Claude Haiku to parse a plain-English description into a typed `AgentSpec`; scaffolds a governed `BaseAgent` subclass; persists to `.agenticqa/custom_agents/`; `register()` auto-inserts capabilities into Task-Agent Ontology. Zero-network keyword fallback when no API key present.
- **CI data ingestion closed loop** — all CI jobs now feed outputs into the learning system: ESLint JSON (`--agent-type sre`), red-team scan results, migration parity log, pip-audit results.
- **`ingest_ci_artifacts.py`** — added `--python-audit`, `--agent-log`, `--pipeline-health` flags.

### Medium Angle
**"Natural Language to Governed Agent: How We Automated the Boilerplate Nobody Wants to Write"**
Angle: the hardest part of building a new agent isn't the logic — it's the scaffolding: `__init__`, `execute()`, input validation, constitution checks, delegation hooks, artifact storage. We automated all of it from a single sentence. Walk through the `AgentSpec` dataclass, the Haiku extraction prompt, the scaffold generator, and the ontology auto-registration. Include the keyword fallback and explain why offline capability is non-negotiable for a CI platform.

---

## v1.2 — Red Team Agent + Constitutional Hardening
**Commit:** `220b418`, `d976107` | **Date:** 2026-02-14

### What Shipped
- **RedTeamAgent** — 8th agent; 20 bypass techniques across 4 categories; `OutputScanner` 4-pass decode (raw → NFKC → base64 → URL); `ConstitutionalGate` semantic aliases + typo-resistance; `PatternPatcher` auto-patches scanner, writes proposals for gate; T1-005 prevents self-modification of `constitutional_gate.py`.
- **Ontology** — `TASK_AGENT_MAP` extended to 20 task types; `RedTeam_Agent: []` in `ALLOWED_DELEGATIONS` (no delegation, T1-005); `AgentOrchestrator` wires all 8 agents.
- **`POST /api/red-team/scan`** with mode/target/auto_patch params.
- **Red Team dashboard page** (#9) — gauge charts, vulnerability table, constitutional proposals.

### Medium Angle
→ Already published: `docs/MEDIUM_RED_TEAM_AGENT.md`

---

## v1.1 — ML Learning Loop (5 Phases)
**Date:** 2026-02-01–14

### What Shipped
All 5 phases of the closed learning loop (feedback loop, adaptive thresholds, pattern-driven execution, GraphRAG delegation, adaptive strategy selection). `ThresholdCalibrator`, `OutcomeTracker`, `StrategySelector`, `PatternAnalyzer`, `RepoProfile` (EWMA per-language fix rates).

### Medium Angle
**"How We Taught 8 AI Agents to Get Smarter Without Retraining (No LLMs Required)"**
Angle: most "learning AI" means fine-tuning. AgenticQA's 5-phase loop learns from deployment outcomes using Case-Based Reasoning, EWMA, and adaptive thresholds — entirely deterministic, explainable, and offline-capable. Walk through each phase with concrete before/after numbers: Phase 2 replaced 3 hardcoded floats with calibration-informed values that converge toward the repo's actual pass rate. Phase 5 activates a conservative strategy when failure rate exceeds 30%.

---

## v1.0 — Constitutional Governance + Hybrid RAG
**Date:** 2026-01-15

### What Shipped
Constitutional Gate (ALLOW/REQUIRE_APPROVAL/DENY), Agent Scopes (T1-006), forensic audit reports, observability store, cross-platform ingestion adapters (LangChain, CrewAI, AutoGen), Hybrid RAG (Weaviate + Neo4j + SQLite), 8-agent orchestrator, 9-page dashboard.

### Medium Angle
**"The Agent Constitution: Machine-Readable Laws That Every AI Agent Enforces Before Acting"**
Angle: GDPR gave us human-readable privacy laws. SOC 2 gave us human-readable security policies. AgenticQA's constitution is the first machine-readable governance document that AI agents enforce *themselves*, in sub-5ms, before every destructive or sensitive action. Walk through the three-tier verdict system, the semantic alias enforcement (why "wipe", "nuke", "clean" all route to the `delete` law), and the counterfactual audit report that answers "what should the agent have done instead?"

---

## Backlog of Medium Angles (Unwritten)

1. **"The Weaviate 1.24.8 Trap: Why Your Vector DB Might Be Silently Losing Data"** — the specific breaking change in the Python client v4, how to detect it, how to migrate to Qdrant without changing a line of agent code. Highly searchable — anyone hitting this bug will find it.

2. **"Ontology-Aware Health Checks: Why 'Is the DB Up?' Is the Wrong Question"** — DataflowHealthMonitor deep dive; how to map infrastructure dependencies to business-level agent capabilities; why a Neo4j failure should alert the delegation team but not the linting team.

3. **"SARIF Without the Ceremony: Putting AI Agent Findings in GitHub Code Scanning"** — the SARIF 2.1.0 schema is well-specified but verbose. Walk through building a minimal `SARIFExporter`, mapping rule IDs to security-severity scores, and wiring `upload-sarif@v3` into an existing CI pipeline. Practical and concrete.

4. **"CVE Reachability vs. CVE Existence: Why Your Dependency Scanner Is Lying To You"** — most `pip-audit` / `npm audit` outputs are noise. A critical CVE in a package you `import` only in a test file that never reaches production is not the same risk as one in your authentication middleware. Walk through AST-based import extraction and the reachability scoring model.

5. **"Developer Risk Profiles: Using Git Blame to Predict Where Your Next Bug Will Be"** — using EWMA-smoothed fix rates per developer to build a risk leaderboard; why this is different from "blame culture" (it's about routing review attention, not punishment); the sha1-hashed email anonymization pattern.
