Nick Homyk
nickhomyk@gmail.com | +1 914 204 2139
linkedin.com/in/nhomyk | github.com/nhomyk | medium.com/@nickhomyk

SUMMARY

15+ years designing automation systems and data pipelines, with recent focus on agentic AI and compliance automation. Built AgenticQA, a Claude-native platform that converts organizational policies into enforceable code, runs continuous compliance monitoring across CI/CD pipelines, and attributes risk to developers through automated evidence collection. Led a 15-person engineering organization. Strong Python background with hands-on experience building multi-agent systems using the Anthropic API, integrating compliance workflows into GitHub Actions, and designing data pipelines across Weaviate, Neo4j, and PostgreSQL.

CORE SKILLS

Languages: Python, TypeScript, Java, SQL
Agentic AI: Claude API (Haiku/Sonnet), multi-agent orchestration, RAG pipelines (Weaviate + Neo4j), adaptive strategy selection
Compliance Automation: Policy-as-code, continuous monitoring, drift detection, CVE reachability analysis, risk scoring (EWMA), developer attribution via git blame
Integration: REST/FastAPI, GitHub Actions, Azure DevOps, Docker, PostgreSQL, SQLite
Security: Adversarial red-team testing, constitutional gates, PII protection validation, OWASP
Leadership: Engineering org leadership (15 people), technical enablement, cross-functional delivery

PROFESSIONAL EXPERIENCE

Paychex | Remote
Lead Agentic AI Technical Trainer | Mar 2025 – Present
- Led engineering enablement on agentic AI workflows, automation strategy, and CI reliability practices for enterprise teams.
- Built standardized playbooks enabling teams to implement automation-first quality programs at scale.

Tax.com | New York, NY
Contract Automation Engineer | Aug 2024 – Feb 2025
- Designed and implemented Java + Selenium automation for a distributed React/Java platform with Azure DevOps CI integration.
- Partnered with engineering leadership to define test strategy, resolve defects, and improve release confidence.

Blue Bite | New York, NY
Interim Head of Engineering / Senior SDET | Jan 2020 – Dec 2022
- Led a 15-person engineering organization across product, QA, and infrastructure delivery.
- Established CI quality gates, defect triage workflows, and cross-functional reporting practices.
- Coordinated engineering priorities across Product, Engineering, and QA while maintaining release quality and velocity.

Blue Bite | New York, NY
Senior Software Development Engineer in Test | Jan 2017 – Jun 2024
- Owned end-to-end QA automation strategy for web applications and API-level testing.
- Reduced regression cycles from weekly to same-day execution through scalable test framework development.

Blue Bite | New York, NY
Software Development Engineer in Test | Jan 2016 – Dec 2016
- Built and executed automated test suites for distributed services and user-facing web workflows.

PROJECTS

AgenticQA (Open Source) | 2024 – Present
github.com/nhomyk/AgenticQA

Agentic compliance and quality automation platform powered by Anthropic Claude. Eight specialized agents (Compliance, Red Team, SRE, SDET, QA, Performance, DevOps, Fullstack) orchestrated through a hybrid RAG layer (Weaviate + Neo4j + PostgreSQL). 453 unit tests, documented REST API, fully wired into GitHub Actions CI.

Constitutional Gate (Policy-as-Code)
Converts written organizational policies into code that executes on every agent action. Governs destructive operations, deployment controls, and bulk action restrictions. Adversarial red-team findings are routed as proposals for human review before touching constitutional logic; the gate never modifies itself automatically.

Compliance Agent + Drift Detection
Runs data encryption, PII protection, and audit log checks on every pipeline run. Dedicated ComplianceDriftDetector persists violation snapshots per repo and compares consecutive runs, surfacing whether compliance is improving, stable, or worsening and which rule types are trending up. Exposed via REST: GET /api/compliance/drift.

Developer Risk Gate
Attributes violations to authors via git blame and accumulates per-developer EWMA risk scores (alpha=0.3) across CI runs. Blocks PRs when changed files are owned by high-risk authors. Configurable threshold. REST endpoint: GET /api/risk-gate.

CVE Reachability Analysis
Runs pip-audit/npm-audit and cross-references findings against actual import graphs extracted via AST. Surfaces only CVEs reachable through real code paths, not all installed packages. Non-blocking integration in the Compliance Agent.

Claude-Powered Agentic Workflows
Claude Haiku generates targeted pytest files for uncovered modules and proposes lint fixes, validated via subprocess before application. Adaptive strategy selection (aggressive/standard/conservative) based on ML-learned failure patterns across runs.

CI/CD GRC Integration
ESLint violations, CVE findings, red-team scans, and compliance drift snapshots are ingested as artifacts into the learning system through GitHub Actions on every run. Compliance data treated as a first-class pipeline output alongside test results.

EDUCATION

College of Saint Rose
B.S. in Business
